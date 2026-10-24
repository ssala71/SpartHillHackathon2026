# =============================================================================
# Shared SMS and Bedrock orchestration
#
# HTTP submissions and incoming SNS messages meet in this module. The service
# checks recipient authorization, reserves an idempotency record, consumes quota,
# optionally asks Bedrock for a reply, and submits a real SMS through AWS.
# The runtime factory supplies real Boto3 clients and DynamoDB storage. Constructor
# injection lets unit tests verify the same logic without contacting AWS.
# A successful API submission is not a delivery receipt. Uncertain or failed
# attempts require review; there is no exactly-once carrier-delivery guarantee.
# =============================================================================
import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from functools import lru_cache

import boto3
from botocore.config import Config

from app.config import settings
from app.waypoint import system_prompt
from app.store import DynamoStore, QuotaExceeded

log = logging.getLogger(__name__)
# Do not let the model answer administrative keywords. This is an application
# guard, not a substitute for keeping AWS-managed keyword/opt-out handling enabled.
KEYWORDS = {'STOP', 'STOPALL', 'UNSUBSCRIBE', 'CANCEL', 'END', 'QUIT',
            'REVOKE', 'OPTOUT', 'HELP', 'INFO', 'START', 'UNSTOP', 'YES'}

# /sms/reply conversation memory: exchanges kept per sender, and for how long.
HISTORY_TURNS = 3
HISTORY_TTL = 30 * 60


class MessagingError(Exception):
    # Domain error understood by the HTTP exception handler. SNS invocations let
    # it propagate so Lambda can apply its configured failure handling instead.
    def __init__(self, code, status=400):
        # code is a stable public identifier; never put a raw AWS exception here.
        self.code, self.status = code, status
        super().__init__(code)


class MessagingService:
    # Keep transport/storage dependencies explicit so the business rules do not
    # depend on FastAPI, Lambda event envelopes, or global AWS credentials.
    def __init__(self, config, store, sms=None, bedrock=None):
        # Production service() always supplies both AWS clients. Tests may omit a
        # client when exercising a validation path that must fail before using it.
        self.config, self.store = config, store
        self.sms, self.bedrock = sms, bedrock

    def check_recipient(self, phone):
        # Formatting is checked even for non-HTTP callers such as the SNS handler.
        # This basic NANP pattern cannot determine the subscriber's actual country.
        if not re.fullmatch(r'\+1[2-9]\d{2}[2-9]\d{6}', phone):
            raise MessagingError('invalid_nanp_phone_number')
        if phone not in self.config.allowed:
            # An inbound sender is not automatically authorized to receive an AI
            # response: they must also appear in the operator-managed allowlist.
            raise MessagingError('recipient_not_allowlisted', 403)

    def send(self, phone, text, request_id):
        # Whitespace-only bodies pass Pydantic's length check, so reject them here.
        self.check_recipient(phone)
        if not text.strip() or len(text) > 500:
            raise MessagingError('message_must_be_1_to_500_characters')
        # Separate out:/in: namespaces prevent HTTP and inbound IDs from colliding.
        # A deferred factory gives plain messages and AI replies one sending path.
        return self._once('out:' + request_id, [phone, text], phone, lambda: text)

    def receive(self, message):
        # A correctly routed SNS topic can still contain an unexpected destination.
        # Bind this deployment to exactly the dedicated number in its configuration.
        if message['destinationNumber'] != self.config.phone:
            raise MessagingError('unexpected_destination', 403)
        phone, text = message['originationNumber'], message['messageBody'].strip()
        # Leave automatic keyword replies and suppression to AWS-managed opt-outs.
        # Keep self-managed opt-outs disabled for this integration.
        first_word = re.split(r'\W+', text.upper(), maxsplit=1)[0]
        if first_word in KEYWORDS:
            # Return without invoking Bedrock, sending an extra reply, or consuming
            # application quota. AWS remains responsible for the keyword response.
            return {'status': 'managed_keyword'}
        self.check_recipient(phone)
        if not text or len(text) > 1600:
            raise MessagingError('invalid_incoming_message')
        return self._once('in:' + message['inboundMessageId'],
                          [phone, self.config.phone, text], phone,
                          lambda: self._reply(text))

    def draft_reply(self, sender, text):
        # Used by the iPhone Shortcut relay: the phone receives the text and sends the
        # reply itself, so this only asks Bedrock and returns the reply. No SMS is sent
        # through AWS, which is why the recipient allowlist does not apply here.
        text = text.strip()
        if not text or len(text) > 1600:
            raise MessagingError('invalid_incoming_message')
        # A bare opt-out word gets no reply. HELP is allowed through on purpose:
        # people in a disaster text "help", and Bedrock answers with a follow-up.
        if text.upper().strip('.! ') in KEYWORDS - {'HELP', 'INFO', 'START', 'UNSTOP', 'YES'}:
            return {'reply': ''}
        # Share the per-sender daily quota so one number cannot run up Bedrock costs.
        day = datetime.now(timezone.utc).date().isoformat()
        sender_hash = hashlib.sha256(sender.encode()).hexdigest()
        try:
            self.store.consume(day + ':reply:' + sender_hash, self.config.daily_limit)
        except QuotaExceeded as error:
            raise MessagingError('daily_limit_reached', 429) from error
        # Keep the last few exchanges for 30 minutes so answers to Waypoint's
        # follow-up question ("which cross street?") are understood.
        key = 'chat:' + sender_hash
        turns = self.store.history(key)
        reply = self._reply(text, turns)
        self.store.save_history(key, (turns + [[text, reply]])[-HISTORY_TURNS:], HISTORY_TTL)
        return {'reply': reply}

    def _reply(self, text, turns=()):
        # No tools. Earlier [text, reply] pairs, if any, come first so Converse sees an
        # alternating user/assistant conversation. The Waypoint instructions limit
        # recommendations to the verified list in resources.json.
        messages = []
        for said, answered in turns:
            messages += [{'role': 'user', 'content': [{'text': said}]},
                         {'role': 'assistant', 'content': [{'text': answered}]}]
        messages.append({'role': 'user', 'content': [{'text': text}]})
        response = self.bedrock.converse(
            modelId=self.config.model,
            system=[{'text': system_prompt()}],
            messages=messages,
            inferenceConfig={'maxTokens': 150},
        )
        # Converse returns content blocks. Collect only text blocks and treat an
        # empty response as a failure rather than sending an empty SMS to AWS.
        reply = ''.join(block.get('text', '')
                        for block in response['output']['message']['content']).strip()
        if not reply:
            raise RuntimeError('Empty model response')
        # Character cap is NOT an SMS segment count. Unicode may cost more segments.
        return reply if len(reply) <= 300 else reply[:297].rstrip() + '...'

    def _once(self, key, payload, phone, text_factory):
        # The fingerprint ties an idempotency key to its original recipient/body.
        # Store a digest instead of SMS text, but do not treat this unsalted hash
        # as encryption: short or predictable messages may still be guessable.
        fingerprint = hashlib.sha256(json.dumps(payload).encode()).hexdigest()
        previous = self.store.claim(key, fingerprint)
        # claim() atomically reserves new work; existing work returns its ledger
        # record. Only the first caller is allowed to proceed toward an AWS send.
        if previous:
            if previous['fingerprint'] != fingerprint:
                raise MessagingError('idempotency_key_reused_with_different_message', 409)
            if previous['status'] == 'COMPLETED':
                # Return the original AWS ID without another quota charge or model
                # request. "duplicate" means the request, not the SMS, was repeated.
                return {**previous['result'], 'duplicate': True}
            # A timeout after SendTextMessage may mean it already sent the SMS.
            # Do not automatically retry an uncertain send. Inspect the ledger/DLQ.
            raise MessagingError('previous_attempt_requires_review', 409)
        try:
            # Share one UTC-day counter across API sends and inbound AI replies.
            # Hashing keeps a raw phone number out of the quota key; it is not a
            # strong anonymization measure for a small enumerable phone-number space.
            day = datetime.now(timezone.utc).date().isoformat()
            recipient_hash = hashlib.sha256(phone.encode()).hexdigest()
            self.store.consume(day + ':' + recipient_hash, self.config.daily_limit)
            # Reserve quota before generating text so exhausted recipients cannot
            # trigger billable Bedrock calls. Later failures do not refund quota.
            text = text_factory()
            sent = self.sms.send_text_message(
                DestinationPhoneNumber=phone,
                OriginationIdentity=self.config.origin,
                MessageBody=text,
                MessageType='TRANSACTIONAL',
                MaxPrice=self.config.max_price,
            )
            # Record only submission status and provider ID, never the reply body.
            # If saving completion fails after AWS accepted the SMS, the attempt is
            # uncertain; the exception path deliberately prevents an automatic resend.
            result = {'status': 'submitted', 'message_id': sent['MessageId']}
            self.store.finish(key, 'COMPLETED', result)
            return result
        except QuotaExceeded as error:
            # Keep a failed ledger record for this request ID. The caller must not
            # reuse that same ID next day expecting it to represent a new message.
            self.store.finish(key, 'FAILED', {'error': 'daily_limit_reached'})
            raise MessagingError('daily_limit_reached', 429) from error
        except Exception as error:
            # Failure can precede sending, occur during an uncertain network timeout,
            # or happen after submission. This conservative policy treats all as
            # review-required. A process crash may instead leave PROCESSING behind.
            self.store.finish(key, 'FAILED', {'error': 'processing_failed'})
            log.error('SMS processing failed; type=%s', type(error).__name__)
            # Log only the exception class; raw errors may include sensitive input.
            raise MessagingError('processing_failed_requires_review', 502) from error


@lru_cache
def service():
    # Reuse clients within a process/warm Lambda environment. Boto3 resolves local
    # profiles or execution-role credentials through its standard provider chain.
    # No credentials are embedded in settings or passed explicitly to these calls.
    config = settings()
    table = boto3.resource('dynamodb', region_name=config.region).Table(config.table)
    # SendTextMessage has no client idempotency token: don't SDK-retry uncertain sends.
    sms = boto3.client('pinpoint-sms-voice-v2', region_name=config.region,
                      config=Config(retries={'total_max_attempts': 1},
                                    connect_timeout=5, read_timeout=15))
    bedrock = boto3.client('bedrock-runtime', region_name=config.region,
                          # Model retries can cost extra inference, but they do not
                          # themselves send SMS. Keep their attempts/timeouts bounded.
                          config=Config(retries={'total_max_attempts': 2},
                                        connect_timeout=5, read_timeout=30))
    return MessagingService(config, DynamoStore(table), sms, bedrock)
