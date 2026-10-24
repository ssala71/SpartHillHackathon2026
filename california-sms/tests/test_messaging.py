# =============================================================================
# Messaging service, HTTP API, and Lambda boundary tests
#
# Test the real orchestration code with injected SMS/Bedrock clients and a test-only
# ledger. HTTP cases use FastAPI's TestClient; Lambda cases supply representative
# API Gateway and SNS envelopes. No carrier messages or model requests are made.
# Coverage focuses on authorization, idempotency, quotas, keyword suppression,
# uncertain sends, and event routing. Configuration validation and DynamoDB adapter
# requests are covered in the two neighboring test modules.
# =============================================================================
import json
from dataclasses import replace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.main import create_app, expected_token
from app.service import MessagingError, MessagingService, service
from tests.fakes import MemoryStore

# Fictional numbers and a deterministic token are fixtures only. They are not
# runtime defaults, credentials, or values suitable for a live deployment.
PHONE = '+14155550100'
ORIGIN = '+14155550199'
TOKEN = 'test-token-' + 'x' * 40


@pytest.fixture
def config():
    # Construct Settings directly to isolate service rules from environment parsing.
    # Placeholder resource names are intentional: test_config.py verifies real ARN
    # formats separately, and these tests never submit identifiers to AWS.
    return Settings('us-west-2', frozenset({PHONE}), ORIGIN,
                    'phone-number-id', 'test-model', 'test-table', 'test-topic', 20, '0.05')


@pytest.fixture
def client(monkeypatch, config):
    # Replace only dependency factories: route validation/authentication and the
    # service's sending/idempotency logic still execute as they do in deployment.
    sms = Mock()
    sms.send_text_message.return_value = {'MessageId': 'aws-message-123'}
    backend = MessagingService(config, MemoryStore(), sms)
    monkeypatch.setattr('app.main.settings', lambda: config)
    monkeypatch.setattr('app.main.service', lambda: backend)
    monkeypatch.setenv('API_TOKEN', TOKEN)
    monkeypatch.setenv('ALLOWED_RECIPIENTS', PHONE)
    monkeypatch.setenv('SMS_PHONE_NUMBER', ORIGIN)
    monkeypatch.delenv('API_TOKEN_SECRET_ARN', raising=False)
    # Clear process-level caches so one test's authentication or clients cannot
    # leak into another. monkeypatch restores patched globals/environment afterward.
    settings.cache_clear()
    service.cache_clear()
    expected_token.cache_clear()
    with TestClient(create_app()) as value:
        # The context runs startup/shutdown, exercising authentication initialization.
        yield value
    settings.cache_clear()
    service.cache_clear()
    expected_token.cache_clear()


def message(**changes):
    # Mirror the INNER SMS JSON object, not its outer SNS event envelope. Each call
    # starts with a unique ID unless a test deliberately reuses the same dict.
    return {'originationNumber': PHONE, 'destinationNumber': ORIGIN,
            'messageBody': 'What can you help with?', 'inboundMessageId': str(uuid4()), **changes}


def test_api_requires_auth_and_does_not_send(client):
    # Missing credentials and a wrong token must both fail at the API boundary.
    data = {'to': PHONE, 'body': 'Hello', 'request_id': str(uuid4())}
    assert client.post('/sms/send', json=data).status_code == 401
    assert client.post('/sms/send', json=data,
                       headers={'Authorization': 'Bearer wrong'}).status_code == 401


def test_authenticated_send_is_idempotent(client):
    # Submit an identical logical message twice. Both calls acknowledge submission,
    # but the second must return the stored AWS ID and an explicit duplicate marker.
    data = {'to': PHONE, 'body': 'Hello', 'request_id': str(uuid4())}
    headers = {'Authorization': 'Bearer ' + TOKEN}
    one = client.post('/sms/send', json=data, headers=headers)
    two = client.post('/sms/send', json=data, headers=headers)
    assert one.status_code == two.status_code == 202
    assert one.json()['status'] == 'submitted'
    assert 'mock' not in one.json()
    assert two.json()['duplicate'] is True
    assert one.json()['message_id'] == two.json()['message_id']
    conflict = client.post('/sms/send', json={**data, 'body': 'Changed'}, headers=headers)
    # An ID cannot be recycled for different content, even with valid credentials.
    assert conflict.status_code == 409


def test_api_rejects_unapproved_recipient(client):
    # A well-formed number is insufficient: authorization also requires allowlisting.
    result = client.post('/sms/send', json={'to': '+12125550101', 'body': 'Hello',
                         'request_id': str(uuid4())}, headers={'Authorization': 'Bearer ' + TOKEN})
    assert result.status_code == 403


def test_blank_message_rejected(client):
    # Three spaces meet schema length requirements but fail semantic validation.
    result = client.post('/sms/send', json={'to': PHONE, 'body': '   ',
                         'request_id': str(uuid4())}, headers={'Authorization': 'Bearer ' + TOKEN})
    assert result.status_code == 400


def test_simulated_inbound_route_is_absent(client):
    # Regression check: even authenticated callers cannot inject inbound messages
    # through the old simulation endpoint. Actual inbound traffic is SNS-only.
    result = client.post('/demo/inbound', json=message(),
                         headers={'Authorization': 'Bearer ' + TOKEN})
    assert result.status_code == 404


def test_api_gateway_lambda_adapter(client):
    # Go through Mangum, not just TestClient, to verify API Gateway v2 parsing and
    # the enabled lifespan behavior used by the deployed HTTP Lambda function.
    from app.main import handler
    payload = {'to': PHONE, 'body': 'Hello', 'request_id': str(uuid4())}
    event = {
        # The adapter expects the outer HTTP API envelope, with body still a string.
        'version': '2.0', 'routeKey': 'ANY /{proxy+}',
        'rawPath': '/sms/send', 'rawQueryString': '', 'isBase64Encoded': False,
        'headers': {'authorization': 'Bearer ' + TOKEN, 'content-type': 'application/json',
                    'host': 'example.execute-api.us-west-2.amazonaws.com'},
        'requestContext': {'stage': '$default', 'http': {'method': 'POST', 'path': '/sms/send',
                           'sourceIp': '127.0.0.1', 'protocol': 'HTTP/1.1'}},
        'body': json.dumps(payload),
    }
    result = handler(event, None)
    assert result['statusCode'] == 202
    assert json.loads(result['body'])['message_id'] == 'aws-message-123'


@pytest.mark.parametrize('keyword', ['STOP', 'STOP please', 'HELP', 'UNSUBSCRIBE', 'START'])
def test_keywords_never_reach_bedrock_or_sms(config, keyword):
    # Administrative keywords bypass both billable operations. Parameterization
    # also checks a keyword followed by text, matching the first-word guard.
    sms, bedrock = Mock(), Mock()
    svc = MessagingService(config, MemoryStore(), sms, bedrock)
    assert svc.receive(message(messageBody=keyword))['status'] == 'managed_keyword'
    sms.send_text_message.assert_not_called()
    bedrock.converse.assert_not_called()


def test_real_adapter_and_duplicate_inbound(config):
    # Exercise the orchestration's AWS-shaped request/response contract. A duplicate
    # inbound ID must neither invoke the model twice nor submit a second reply.
    sms, bedrock = Mock(), Mock()
    sms.send_text_message.return_value = {'MessageId': 'aws-message-123'}
    bedrock.converse.return_value = {'output': {'message': {'content': [{'text': 'Hello!'}]}}}
    svc = MessagingService(config, MemoryStore(), sms, bedrock)
    data = message()
    assert svc.receive(data)['status'] == 'submitted'
    assert svc.receive(data)['duplicate'] is True
    sms.send_text_message.assert_called_once_with(
        # The response must go back to the sender using our configured origination
        # identity, not to the inbound destination number or a model-chosen recipient.
        DestinationPhoneNumber=PHONE, OriginationIdentity=config.origin,
        MessageBody='Hello!', MessageType='TRANSACTIONAL', MaxPrice='0.05')
    bedrock.converse.assert_called_once()


def test_uncertain_send_is_not_retried(config):
    # A timeout does not tell us whether AWS accepted the first message. The second
    # call with that ID must require review rather than risk duplicate delivery.
    sms = Mock()
    sms.send_text_message.side_effect = TimeoutError()
    svc = MessagingService(config, MemoryStore(), sms)
    with pytest.raises(MessagingError, match='processing_failed_requires_review'):
        svc.send(PHONE, 'Hello', 'same-id')
    with pytest.raises(MessagingError, match='previous_attempt_requires_review'):
        svc.send(PHONE, 'Hello', 'same-id')
    assert sms.send_text_message.call_count == 1


def test_daily_limit_applies_to_send_and_reply(config):
    # Consume the sole attempt via HTTP-style sending, then attempt an AI reply for
    # the same recipient. Both directions share one quota budget in the service.
    sms = Mock()
    sms.send_text_message.return_value = {'MessageId': 'aws-message-123'}
    svc = MessagingService(replace(config, daily_limit=1), MemoryStore(), sms)
    svc.send(PHONE, 'Hello', 'one')
    with pytest.raises(MessagingError, match='daily_limit_reached'):
        svc.receive(message())


def test_wrong_inbound_destination_rejected(config):
    # Reject a message addressed to another AWS number before any client is needed.
    svc = MessagingService(config, MemoryStore())
    with pytest.raises(MessagingError, match='unexpected_destination'):
        svc.receive(message(destinationNumber='+12125550101'))


def test_sns_handler_checks_topic_and_parses_inner_json(monkeypatch, config):
    # Exercise the actual SNS handler with a JSON-encoded Message field. This
    # complements service-only tests that pass an already-decoded SMS dictionary.
    from app import inbound
    sms, bedrock = Mock(), Mock()
    sms.send_text_message.return_value = {'MessageId': 'aws-message-123'}
    bedrock.converse.return_value = {'output': {'message': {'content': [{'text': 'Hello!'}]}}}
    svc = MessagingService(config, MemoryStore(), sms, bedrock)
    monkeypatch.setattr(inbound, 'settings', lambda: config)
    monkeypatch.setattr(inbound, 'service', lambda: svc)
    record = {'EventSource': 'aws:sns', 'Sns': {'TopicArn': 'test-topic',
              'Message': json.dumps(message())}}
    result = inbound.handler({'Records': [record]}, None)
    assert result['results'][0]['status'] == 'submitted'
    record['Sns']['TopicArn'] = 'wrong-topic'
    # A valid payload from an unexpected topic must not reach business processing.
    with pytest.raises(ValueError, match='Unexpected SNS topic'):
        inbound.handler({'Records': [record]}, None)


def test_reply_uses_waypoint_instructions(config):
    # The model must be grounded in the verified list and the medical rule.
    sms, bedrock = Mock(), Mock()
    sms.send_text_message.return_value = {'MessageId': 'aws-message-123'}
    bedrock.converse.return_value = {'output': {'message': {'content': [{'text': 'Go to Tully.'}]}}}
    svc = MessagingService(config, MemoryStore(), sms, bedrock)
    svc.receive(message())
    prompt = bedrock.converse.call_args.kwargs['system'][0]['text']
    assert 'Tully Community Center' in prompt
    assert '911' in prompt
    assert 'same language' in prompt


def test_draft_reply_returns_text_without_sending(config):
    # The Shortcut relay gets Bedrock's reply back; AWS SMS is never called, and
    # senders outside the allowlist (judges' phones) are still answered.
    sms, bedrock = Mock(), Mock()
    bedrock.converse.return_value = {'output': {'message': {'content': [{'text': 'Go to Tully.'}]}}}
    svc = MessagingService(config, MemoryStore(), sms, bedrock)
    assert svc.draft_reply('+14085550123', 'need water near Tully') == {'reply': 'Go to Tully.'}
    sms.send_text_message.assert_not_called()


def test_draft_reply_skips_keywords_and_enforces_quota(config):
    bedrock = Mock()
    bedrock.converse.return_value = {'output': {'message': {'content': [{'text': 'ok'}]}}}
    svc = MessagingService(replace(config, daily_limit=1), MemoryStore(), Mock(), bedrock)
    assert svc.draft_reply('judge', 'STOP') == {'reply': ''}
    bedrock.converse.assert_not_called()
    svc.draft_reply('judge', 'help')  # "help" is a real request here, not a keyword
    with pytest.raises(MessagingError, match='daily_limit_reached'):
        svc.draft_reply('judge', 'need food')


def test_draft_reply_remembers_the_previous_exchange(config):
    # A follow-up answer must reach Bedrock with the earlier question in context.
    bedrock = Mock()
    bedrock.converse.return_value = {'output': {'message': {'content': [{'text': 'Which cross street?'}]}}}
    svc = MessagingService(config, MemoryStore(), Mock(), bedrock)
    svc.draft_reply('+14085550123', 'we need food')
    svc.draft_reply('+14085550123', 'Story and King')
    messages = bedrock.converse.call_args.kwargs['messages']
    assert [m['role'] for m in messages] == ['user', 'assistant', 'user']
    assert messages[0]['content'][0]['text'] == 'we need food'
    assert messages[1]['content'][0]['text'] == 'Which cross street?'
    # Other senders do not see this conversation.
    svc.draft_reply('+14085550199', 'water')
    assert len(bedrock.converse.call_args.kwargs['messages']) == 1


def test_draft_reply_uses_backend_match_when_configured(config, monkeypatch):
    # The backend's matcher decision reaches Bedrock as a system instruction, and
    # the whole conversation so far is sent to the backend as one request.
    from app import backend
    seen = {}
    monkeypatch.setenv('WAYPOINT_BACKEND_URL', 'http://backend.test')
    monkeypatch.setattr(backend, 'match', lambda sender, message: seen.update(message=message) or {
        'action': 'direct_to_location',
        'resource': {'name': 'Tully Community Center (SIM)', 'address': '1580 Tully Rd, San Jose (SIM)',
                     'distance_km': 1.24}})
    bedrock = Mock()
    bedrock.converse.return_value = {'output': {'message': {'content': [{'text': 'Go to Tully.'}]}}}
    svc = MessagingService(config, MemoryStore(), Mock(), bedrock)
    svc.draft_reply('+14085550123', 'we need water')
    svc.draft_reply('+14085550123', 'near Tully')
    assert seen['message'] == 'we need water / near Tully'
    system = bedrock.converse.call_args.kwargs['system']
    assert 'Tully Community Center, 1580 Tully Rd, San Jose (about 1.2 km away)' in system[1]['text']


def test_draft_reply_falls_back_when_backend_fails(config, monkeypatch):
    from app import backend
    monkeypatch.setenv('WAYPOINT_BACKEND_URL', 'http://backend.test')
    monkeypatch.setattr(backend, 'match', Mock(side_effect=OSError('connection refused')))
    bedrock = Mock()
    bedrock.converse.return_value = {'output': {'message': {'content': [{'text': 'Go to Tully.'}]}}}
    svc = MessagingService(config, MemoryStore(), Mock(), bedrock)
    assert svc.draft_reply('+14085550123', 'need water') == {'reply': 'Go to Tully.'}
    assert len(bedrock.converse.call_args.kwargs['system']) == 1


def test_reply_route_requires_token(client):
    assert client.post('/sms/reply', json={'sender': 'x', 'body': 'help'}).status_code == 401
