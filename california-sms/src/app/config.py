# =============================================================================
# AWS environment configuration and validation
#
# Both entry points obtain their settings here. Local development may supply a
# .env file; Lambda supplies variables through template.yaml. Required resource
# identifiers are validated before use, with no simulated or in-memory fallback.
# Validation checks format and consistency, not resource existence or IAM access.
# Successful settings are cached for the process lifetime; restart after changing
# configuration. Secrets are resolved separately by main.expected_token().
# =============================================================================
import os
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    # Immutable configuration prevents one request from changing another's AWS
    # routing or recipient permissions. These fields contain resource names and
    # limits, never AWS access keys or the application's bearer token.
    region: str
    # A frozen set gives fast membership checks and removes duplicate recipients.
    allowed: frozenset[str]
    # phone is the E.164 address used to validate inbound destinations; origin is
    # the AWS phone-number ARN used when submitting outbound messages.
    phone: str
    origin: str
    model: str
    table: str
    topic: str
    daily_limit: int
    # Keep price as a string because the SMS API accepts a decimal string.
    max_price: str


@lru_cache
def settings() -> Settings:
    # Existing process variables take precedence over a local .env file. In AWS,
    # src/ contains no .env, so deployment-provided variables remain authoritative.
    load_dotenv(override=False)
    # Report names of missing values together without including any secret or
    # user-supplied value in the error. Empty and whitespace-only values are absent.
    required = ('ALLOWED_RECIPIENTS', 'SMS_PHONE_NUMBER', 'SMS_ORIGINATION_ID',
                'BEDROCK_MODEL_ID', 'TABLE_NAME', 'INBOUND_TOPIC_ARN')
    missing = [name for name in required if not os.getenv(name, '').strip()]
    if missing:
        raise ValueError('Missing required AWS configuration: ' + ', '.join(missing))
    result = Settings(
        region=os.getenv('AWS_REGION', 'us-west-2'),
        allowed=frozenset(x.strip() for x in os.getenv('ALLOWED_RECIPIENTS', '').split(',') if x.strip()),
        phone=os.environ['SMS_PHONE_NUMBER'].strip(),
        origin=os.getenv('SMS_ORIGINATION_ID', ''),
        model=os.getenv('BEDROCK_MODEL_ID', ''),
        table=os.getenv('TABLE_NAME', ''),
        topic=os.getenv('INBOUND_TOPIC_ARN', ''),
        daily_limit=int(os.getenv('DAILY_LIMIT_PER_RECIPIENT', '20')),
        max_price=os.getenv('SMS_MAX_PRICE_USD', '0.05'),
    )
    # This is an attempt limit, shared by outgoing API requests and AI replies.
    # A failed send can still consume an attempt; service.py explains that choice.
    if result.daily_limit < 1:
        raise ValueError('DAILY_LIMIT_PER_RECIPIENT must be positive')
    # This validates basic North American numbering-plan syntax. +1 also serves
    # countries outside the US; the operator must choose the intended recipients.
    if not result.allowed or any(not re.fullmatch(r'\+1[2-9]\d{2}[2-9]\d{6}', value)
                                 for value in (*result.allowed, result.phone)):
        raise ValueError('SMS_PHONE_NUMBER and ALLOWED_RECIPIENTS must use valid +1 E.164 format')
    # Require resources in the configured region to catch mismatched deployments
    # early. ARN syntax alone cannot establish ownership, approval, or availability.
    if not re.fullmatch(r'arn:aws:sms-voice:' + re.escape(result.region) +
                        r':\d{12}:phone-number/[A-Za-z0-9-]+', result.origin):
        raise ValueError('SMS_ORIGINATION_ID must be a phone-number ARN in AWS_REGION')
    # Restrict inbound routing to a standard SNS topic; FIFO names are not accepted.
    if not re.fullmatch(r'arn:aws:sns:' + re.escape(result.region) +
                        r':\d{12}:[A-Za-z0-9_-]+', result.topic):
        raise ValueError('INBOUND_TOPIC_ARN must be a standard SNS topic ARN in AWS_REGION')
    try:
        # Decimal avoids binary floating-point rounding. Reject NaN and infinity
        # as well as nonpositive amounts before passing the price guard to AWS.
        price = Decimal(result.max_price)
        if not price.is_finite() or price <= 0:
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise ValueError('SMS_MAX_PRICE_USD must be a positive finite number') from None
    return result
