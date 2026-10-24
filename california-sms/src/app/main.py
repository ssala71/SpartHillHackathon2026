# =============================================================================
# FastAPI HTTP application and API Gateway/Lambda adapter
#
# Exposes process health and authenticated SMS submission. It validates deployment
# settings and bearer-token configuration at startup, then delegates sending to
# service.py. Authentication is a shared trusted-backend token, not a multi-user
# authorization system. Incoming texts use the separate SNS Lambda entry point.
# Uvicorn runs app; SAM invokes handler through Mangum. No route simulates SMS.
# =============================================================================
import os
import secrets
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Annotated

import boto3
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from mangum import Mangum

from app.config import settings
from app.models import OutgoingSMS
from app.service import MessagingError, service


# Parse the Authorization header without letting the helper choose the response;
# require_token() consistently returns 401 and the Bearer authentication challenge.
security = HTTPBearer(auto_error=False)


@lru_cache
def expected_token():
    # Resolve once per process to avoid a Secrets Manager request for every SMS.
    # Rotating the secret requires restarting/recycling processes to clear this
    # cache; this implementation does not periodically refresh a rotated token.
    config = settings()
    arn = os.getenv('API_TOKEN_SECRET_ARN')
    if arn:
        # The deployed secret holds the raw token in SecretString, not a JSON object.
        # AWS credentials come from the normal SDK chain, including Lambda's role.
        value = boto3.client('secretsmanager', region_name=config.region).get_secret_value(
            SecretId=arn)['SecretString']
    else:
        # A local token is supported for development against actual AWS resources.
        # When an ARN is present, failures reading it never fall back to this value.
        value = os.getenv('API_TOKEN', '')
    if len(value) < 32 or value.startswith('replace-with-'):
        raise HTTPException(503, 'Configure a random API token of at least 32 characters')
    return value


def require_token(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)]):
    # Authenticate before route business logic can consume quota or submit a text.
    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise HTTPException(401, 'Bearer token required', headers={'WWW-Authenticate': 'Bearer'})
    # Constant-time comparison avoids ordinary string equality's early-exit timing.
    if not secrets.compare_digest(credentials.credentials.encode(), expected_token().encode()):
        raise HTTPException(401, 'Invalid token', headers={'WWW-Authenticate': 'Bearer'})


@asynccontextmanager
async def lifespan(app):
    # Refuse to serve requests if deployment configuration or authentication is missing.
    settings()
    expected_token()
    # Reaching yield tells the ASGI server that startup completed. There is no
    # background worker or per-process resource requiring shutdown cleanup here.
    yield


def create_app():
    # A factory allows tests to create isolated ASGI applications while deployment
    # imports the single app instance below. Dependencies remain resolved at use.
    app = FastAPI(title='California SMS API', version='1.0.0', lifespan=lifespan,
                  description='FastAPI + AWS End User Messaging SMS + Amazon Bedrock')

    @app.exception_handler(MessagingError)
    async def handle_message_error(request, error):
        # Translate controlled service failures into stable API codes. Raw AWS
        # exceptions and internal details are not included in this response.
        return JSONResponse(status_code=error.status, content={'detail': error.code})

    @app.get('/health')
    def health():
        # This is process/configuration health, not an AWS connectivity or delivery
        # probe. Returning ok does not prove SMS registration or model access.
        return {'status': 'ok', 'region': settings().region}

    @app.post('/sms/send', status_code=202, dependencies=[Depends(require_token)])
    def send(body: OutgoingSMS):
        # A synchronous route lets FastAPI use its worker thread for blocking Boto3
        # calls. HTTP 202 acknowledges submission, not delivery to the recipient.
        return service().send(body.to, body.body, str(body.request_id))

    return app


app = create_app()
# Run the same startup validation for Lambda invocations as for a local server.
# SNS calls app.inbound.handler directly and does not pass through this adapter.
handler = Mangum(app, lifespan='on')
