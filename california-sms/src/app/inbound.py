# =============================================================================
# Incoming SMS Lambda entry point: app.inbound.handler
#
# AWS End User Messaging publishes a JSON message inside an SNS event. This handler
# verifies the event source/topic, parses that inner payload, and delegates to the
# messaging service, which validates the destination and generates/sends a reply.
# It has no HTTP endpoint. Lambda invocation permissions in template.yaml provide
# the access boundary; a matching TopicArn string alone is not authentication.
# Exceptions propagate to Lambda's asynchronous retry/failure-destination handling.
# =============================================================================
import json

from app.config import settings
from app.models import IncomingSMS
from app.service import service


def handler(event, context):
    """Only invoked by the SNS topic granted permission in template.yaml."""
    # Lambda supplies context, but this implementation does not need it. Process
    # each record sequentially; one failure aborts the invocation, so the ledger
    # must recognize records that were already completed during a previous attempt.
    results = []
    for record in event['Records']:
        sns = record['Sns']
        if record.get('EventSource') != 'aws:sns':
            raise ValueError('Expected an SNS event')
        if not settings().topic or sns.get('TopicArn') != settings().topic:
            raise ValueError('Unexpected SNS topic')
        # SNS.Message is a JSON string, not the SMS text itself. Parse it once and
        # validate the message schema before forwarding only the needed fields.
        message = IncomingSMS.model_validate(json.loads(sns['Message']))
        results.append(service().receive(message.model_dump()))
    return {'results': results}
