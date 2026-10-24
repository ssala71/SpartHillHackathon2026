# =============================================================================
# Configuration and application-startup regression tests
#
# Exercise required settings, identifier formats, limits, and authentication before
# FastAPI starts serving traffic. Environment fixtures disable local .env loading
# so a developer's account settings cannot accidentally influence the results.
# These tests do not create AWS clients or prove that configured resources exist;
# they verify the validation contract and the exposed HTTP schema only.
# =============================================================================
import importlib

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import create_app, expected_token

configuration = importlib.import_module('app.config')
# Import the module object so monkeypatch can replace its dotenv loader independently
# of settings() references already imported by other modules.


@pytest.fixture
def environment(monkeypatch):
    # Supply a complete syntactically valid environment, then let individual cases
    # remove or corrupt exactly one field. All numbers/ARNs here are test fixtures.
    monkeypatch.setattr(configuration, 'load_dotenv', lambda **kwargs: None)
    values = {
        'AWS_REGION': 'us-west-2',
        'ALLOWED_RECIPIENTS': '+14155550100',
        'SMS_PHONE_NUMBER': '+14155550199',
        'SMS_ORIGINATION_ID': 'arn:aws:sms-voice:us-west-2:123456789012:phone-number/phone-123',
        'BEDROCK_MODEL_ID': 'us.amazon.nova-lite-v1:0',
        'TABLE_NAME': 'message-ledger',
        'INBOUND_TOPIC_ARN': 'arn:aws:sns:us-west-2:123456789012:incoming',
        'DAILY_LIMIT_PER_RECIPIENT': '20',
        'SMS_MAX_PRICE_USD': '0.05',
        'API_TOKEN': 'x' * 48,
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    # Force local token resolution so no test attempts to contact Secrets Manager.
    monkeypatch.delenv('API_TOKEN_SECRET_ARN', raising=False)
    configuration.settings.cache_clear()
    expected_token.cache_clear()
    # Cached settings/authentication must not hide changes in later test cases.
    yield values
    configuration.settings.cache_clear()
    expected_token.cache_clear()


@pytest.mark.parametrize('key', ['ALLOWED_RECIPIENTS', 'SMS_PHONE_NUMBER', 'SMS_ORIGINATION_ID',
                                  'BEDROCK_MODEL_ID', 'TABLE_NAME', 'INBOUND_TOPIC_ARN'])
def test_missing_configuration_fails_before_serving(environment, monkeypatch, key):
    # Entering TestClient as a context manager runs the real ASGI startup lifecycle.
    # Failure must occur there, not only after the first message request arrives.
    monkeypatch.delenv(key)
    with pytest.raises(ValueError, match=key):
        with TestClient(create_app()):
            pytest.fail('Server must not start with missing AWS settings')


@pytest.mark.parametrize('key,value', [
    # Cover an effectively empty allowlist, malformed phone, regional mismatches,
    # invalid decimal prices, and an attempt limit that would never permit sends.
    ('ALLOWED_RECIPIENTS', ','), ('SMS_PHONE_NUMBER', '4155550100'),
    ('SMS_ORIGINATION_ID', 'arn:aws:sms-voice:us-east-1:123456789012:phone-number/phone-123'),
    ('INBOUND_TOPIC_ARN', 'arn:aws:sns:us-east-1:123456789012:incoming'),
    ('SMS_MAX_PRICE_USD', 'NaN'), ('SMS_MAX_PRICE_USD', '-1'), ('DAILY_LIMIT_PER_RECIPIENT', '0'),
])
def test_invalid_configuration_rejected(environment, monkeypatch, key, value):
    # Parsing/format errors are configuration failures, before any AWS operation.
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        configuration.settings()


def test_missing_api_authentication_prevents_startup(environment, monkeypatch):
    # Complete AWS settings are insufficient without a usable API authentication
    # source. The expected 503 identifies operator configuration, not bad user input.
    monkeypatch.delenv('API_TOKEN')
    with pytest.raises(HTTPException) as error:
        with TestClient(create_app()):
            pytest.fail('Server must not start without authentication')
    assert error.value.status_code == 503


def test_valid_configuration_health_and_schema(environment):
    # The healthy path performs no AWS send. Assert the exact route set to prevent
    # accidental reintroduction of an HTTP simulation/inbound injection endpoint.
    with TestClient(create_app()) as client:
        assert client.get('/health').json() == {'status': 'ok', 'region': 'us-west-2'}
        assert set(client.get('/openapi.json').json()['paths']) == {'/health', '/sms/send', '/sms/reply'}
