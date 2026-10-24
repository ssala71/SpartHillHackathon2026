# California SMS service

FastAPI application for sending SMS with AWS End User Messaging SMS and receiving messages through SNS → Lambda → Amazon Bedrock → SMS. The application uses real AWS clients and a DynamoDB ledger. Missing configuration stops startup. There is no simulation mode, fake reply, or public inbound webhook.

The deployment region defaults to `us-west-2` (Oregon), with US recipients. The code has not yet been deployed or verified against your AWS account or a carrier. AWS account authentication, an approved dedicated SMS number, and Bedrock access are still required.

## Deploy

Prerequisites: Python 3.12, AWS CLI v2, AWS SAM CLI, and Docker for the container build. Use the AWS account and role authorized by your team to deploy CloudFormation, create/pass Lambda execution roles, and manage the resources in `template.yaml`.

1. Authenticate with your AWS profile and verify the intended account:

   ```powershell
   aws sso login --profile hackathon
   aws sts get-caller-identity --profile hackathon
   ```

   Use your organization's configured profile name. If your account uses console-based CLI sign-in instead of IAM Identity Center, use `aws login --profile hackathon`.

2. In AWS End User Messaging SMS in **us-west-2**, obtain an active US dedicated phone number supporting two-way SMS. Complete the applicable registration. Record its phone-number ARN and E.164 number. If your account remains in the SMS sandbox, verify each intended destination number. Sender registration and sandbox verification are separate requirements.

3. Confirm access to Bedrock inference profile `us.amazon.nova-lite-v1:0` from `us-west-2`. The template scopes model permissions to Nova Lite; changing models requires changing both `BEDROCK_MODEL_ID` and the corresponding IAM resources. This profile can process requests in other US regions.

4. Build and deploy from this directory:

   ```powershell
   sam build --use-container
   sam deploy --guided --profile hackathon --region us-west-2
   ```

   Use stack name `california-sms`. Supply `OriginationArn`, `PhoneNumber`, `AllowedRecipients`, and `DailyLimit`. `AllowedRecipients` is a comma-separated list of actual consenting recipients. Review the CloudFormation changeset and IAM role creation.

   The template creates API Gateway, two Lambda functions, an SNS topic, a DynamoDB table, an API token in Secrets Manager, and an SQS failure queue. It does not buy a phone number or submit its registration. Deployment and use incur AWS charges.

5. In the dedicated number's **Two-way messaging** settings, enable incoming SMS and select the stack's `InboundTopicArn` using **SNS topic policies**. Leave **self-managed opt-outs disabled**. AWS handles keyword responses and opt-out suppression; the application does not send model-generated keyword replies.

6. Retrieve the bearer token from the Secrets Manager secret identified by the stack's `ApiTokenSecretArn`. Keep it in your backend's secret storage. The application reads this secret using its Lambda execution role. This token authenticates a trusted backend; add user/tenant authorization before exposing messaging to individual application users.

7. Call `POST /sms/send` at the stack's `ApiUrl` with the bearer token and a consenting recipient. Send an incoming text to your dedicated number to exercise the SNS/Lambda/Bedrock reply flow. Inspect CloudWatch and the failure queue if processing fails.

Lambda uses IAM role credentials automatically. You do not need an AWS coding-assistant integration or access keys embedded in the source.

## Local development against AWS

First deploy the infrastructure, then run the API locally against those resources. Local sends are real and billable.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Create `.env` from `.env.example` if it does not exist. If it already exists, edit it in place. Fill the following values:

| Variable | Value |
| --- | --- |
| `AWS_PROFILE` | Your authenticated local AWS profile. Omit in Lambda. |
| `AWS_REGION` | `us-west-2`, matching the deployed number and resources. |
| `ALLOWED_RECIPIENTS` | Comma-separated consenting recipients in +1 E.164 format. |
| `SMS_PHONE_NUMBER` | Your actual AWS dedicated number in E.164 format. |
| `SMS_ORIGINATION_ID` | Its full `arn:aws:sms-voice:...:phone-number/...` ARN. |
| `BEDROCK_MODEL_ID` | `us.amazon.nova-lite-v1:0`, matching the IAM policy. |
| `TABLE_NAME` | Stack output `LedgerTable`. |
| `INBOUND_TOPIC_ARN` | Stack output `InboundTopicArn`. |
| `API_TOKEN_SECRET_ARN` | Stack output `ApiTokenSecretArn`; local identity needs GetSecretValue. |
| `API_TOKEN` | Optional local alternative: a random token of at least 32 characters. Secret ARN takes precedence. |
| `DAILY_LIMIT_PER_RECIPIENT` | Maximum daily send attempts per recipient; default 20. |
| `SMS_MAX_PRICE_USD` | AWS message-part price guard; default 0.05, not an account spending cap. |

The application validates required fields before serving requests. Configuration values do not prove resources exist or that credentials grant access. `/health` indicates the process/configuration is ready; it does not probe every AWS service.

```powershell
.venv\Scripts\python -m uvicorn app.main:app --app-dir src --host 127.0.0.1 --port 8000
```

Use `/docs` to inspect the API schema and authorize requests. Never put the service token in a public frontend. Incoming SMS continues to invoke the deployed Lambda function; a local FastAPI server does not receive SNS events.

## API contract

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Process health and configured AWS region. |
| `POST /sms/send` | Authenticated submission of a real outbound SMS. |

`POST /sms/send` requires `Authorization: Bearer <your token>` and a JSON object containing:

- `to`: an allowlisted E.164 phone number.
- `body`: nonempty text of at most 500 characters.
- `request_id`: a UUID generated by your caller for this message.

Successful responses are HTTP 202 with `status: submitted` and the AWS `message_id`. This confirms submission, not carrier delivery. Reuse the same request ID and body when retrying a timed-out HTTP call. Changing the body or recipient while reusing the ID returns 409.

Incoming messages use the SNS Lambda handler and validate the SNS topic and destination number. No HTTP route accepts fabricated inbound events.

## Processing behavior

- DynamoDB tracks request hashes, IDs, and status for approximately seven days. Daily quota counters expire after approximately two days. There is no in-memory runtime fallback.
- The per-recipient quota applies to API sends and bot replies and resets by UTC date. Failed processing can consume quota. API Gateway also throttles requests.
- Recipient authorization uses an explicit allowlist. +1 is shared by several countries; include only your intended US recipients. AWS-managed opt-outs remain enabled.
- Bedrock generates single-turn replies capped at 300 characters. It has no application tools and cannot perform account actions. Unicode and long texts may use multiple billable SMS segments.
- Failed attempts are marked FAILED; hard timeouts can leave PROCESSING. Subsequent attempts with that ID require review instead of automatically resending an uncertain SMS. Inbound failures ultimately go to SQS. Review delivery evidence before retrying; this does not guarantee exactly-once carrier delivery.
- Failure-queue payloads may contain the original incoming text. Restrict access; queue retention is 14 days. Successful SMS bodies are not retained by this application's ledger.
- There is no conversation history, delivery-receipt dashboard, ordering guarantee, frontend, or multi-user account system. The current authentication is intended for a trusted backend integration.

## Tests

```powershell
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest -q
```

Tests inject isolated AWS test doubles without sending texts or contacting AWS. They live under `tests/` and are outside the Lambda deployment package. `src/` contains only real AWS behavior. See `VALIDATION.md` for performed checks and remaining account-level verification.

## Implementation files

- `src/app/main.py`: startup validation, FastAPI routes, and bearer authentication.
- `src/app/models.py`: outgoing and incoming message schemas.
- `src/app/service.py`: AWS sending, Bedrock responses, and idempotency.
- `src/app/inbound.py`: SNS Lambda entry point.
- `src/app/store.py`: DynamoDB ledger and atomic quota enforcement.
- `template.yaml`: infrastructure and IAM permissions.

## AWS references

- [Two-way SMS](https://docs.aws.amazon.com/sms-voice/latest/userguide/two-way-sms.html)
- [Incoming payload](https://docs.aws.amazon.com/sms-voice/latest/userguide/two-way-sms-payload.html)
- [Registration](https://docs.aws.amazon.com/sms-voice/latest/userguide/registration-help.html)
- [Managed opt-outs](https://docs.aws.amazon.com/sms-voice/latest/userguide/opt-out-list-self-managed.html)
- [Nova Lite](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-lite.html)
