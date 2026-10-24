# California SMS service

FastAPI application for sending SMS with AWS End User Messaging SMS and receiving messages through SNS → Lambda → Amazon Bedrock → SMS. The application uses real AWS clients and a DynamoDB ledger. Missing configuration stops startup. There is no simulation mode, fake reply, or public inbound webhook.

The deployment region defaults to `us-east-1` (N. Virginia), with US recipients. The code has not yet been deployed or verified against your AWS account or a carrier. AWS account authentication, an approved dedicated SMS number, and Bedrock access are still required.

## Deploy

Prerequisites: Python 3.12, AWS CLI v2, AWS SAM CLI, and Docker for the container build. Use the AWS account and role authorized by your team to deploy CloudFormation, create/pass Lambda execution roles, and manage the resources in `template.yaml`.

1. Authenticate with your AWS profile and verify the intended account:

   ```powershell
   aws sso login --profile hackathon
   aws sts get-caller-identity --profile hackathon
   ```

   Use your organization's configured profile name. If your account uses console-based CLI sign-in instead of IAM Identity Center, use `aws login --profile hackathon`.

2. In AWS End User Messaging SMS in **us-east-1**, obtain an active US dedicated phone number supporting two-way SMS. Complete the applicable registration. Record its phone-number ARN and E.164 number. If your account remains in the SMS sandbox, verify each intended destination number. Sender registration and sandbox verification are separate requirements.

3. Confirm access to Bedrock inference profile `us.amazon.nova-lite-v1:0` from `us-east-1`. The template scopes model permissions to Nova Lite; changing models requires changing both `BEDROCK_MODEL_ID` and the corresponding IAM resources. This profile can process requests in other US regions.

4. Build and deploy from this directory:

   ```powershell
   sam build --use-container
   sam deploy --guided --profile hackathon --region us-east-1
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
| `AWS_REGION` | `us-east-1`, matching the deployed number and resources. |
| `ALLOWED_RECIPIENTS` | Comma-separated consenting recipients in +1 E.164 format. |
| `SMS_PHONE_NUMBER` | Your actual AWS dedicated number in E.164 format. |
| `SMS_ORIGINATION_ID` | Its full `arn:aws:sms-voice:...:phone-number/...` ARN. |
| `BEDROCK_MODEL_ID` | `us.amazon.nova-lite-v1:0`, matching the IAM policy. |
| `TABLE_NAME` | Stack output `LedgerTable`. Not needed when `DATABASE_URL` is set. |
| `DATABASE_URL` | Optional. A PostgreSQL URL such as `postgresql://localhost/waypoint`. When set, the ledger uses PostgreSQL (table `sms_ledger`, created automatically) instead of DynamoDB. |
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
| `POST /sms/reply` | Authenticated. Returns Bedrock's Waypoint reply for `{ "sender", "body" }` without sending anything. Used by the iPhone Shortcut relay, which sends the reply from the phone. |

`POST /sms/send` requires `Authorization: Bearer <your token>` and a JSON object containing:

- `to`: an allowlisted E.164 phone number.
- `body`: nonempty text of at most 500 characters.
- `request_id`: a UUID generated by your caller for this message.

Successful responses are HTTP 202 with `status: submitted` and the AWS `message_id`. This confirms submission, not carrier delivery. Reuse the same request ID and body when retrying a timed-out HTTP call. Changing the body or recipient while reusing the ID returns 409.

Incoming messages use the SNS Lambda handler and validate the SNS topic and destination number. No HTTP route accepts fabricated inbound events.

## Waypoint replies

Bedrock answers as Waypoint. It may only recommend the verified locations in `src/app/resources.json`, replies in the sender's language, accepts a street address, cross street, neighborhood, or landmark as the location, asks for the need or location when either is missing, and tells medical or life-threatening messages to call 911 and that a coordinator will follow up. Edit `resources.json` to change the list, then redeploy. The instructions live in `src/app/waypoint.py`.

## Demo: iPhone relay

The hackathon AWS account cannot create IAM roles, so the SAM deploy fails, and a real SMS number needs carrier registration that takes days. For the demo, the API runs on a laptop and an iPhone relays the texts. Replies are still written by Amazon Bedrock with the Waypoint instructions above:

text to the iPhone → Shortcuts automation → `POST /sms/reply` (through a tunnel to the laptop) → Bedrock → the iPhone texts the reply back.

`POST /sms/reply` takes `{"sender": "...", "body": "..."}` and returns `{"reply": "..."}`. It needs the bearer token, sends nothing itself, skips the recipient allowlist, and allows 20 replies per sender per UTC day. It returns an empty reply for a bare opt-out keyword such as STOP. It remembers each sender's last 3 exchanges for 30 minutes (in the ledger, keyed by a hash of the number), so an answer to Waypoint's follow-up question such as "Story and King" is understood.

### Prerequisites (macOS)

- Python 3.12+ and the packages in `requirements-dev.txt`.
- AWS CLI v2 and cloudflared: `brew install awscli cloudflared`.
- PostgreSQL, shared by this service and the backend:
  ```bash
  brew install postgresql@16 && brew services start postgresql@16
  createdb waypoint
  ```
  To use a hosted database (for example Amazon RDS) instead, `export DATABASE_URL=postgresql://user:password@host:5432/waypoint` in each tab before starting the scripts. Never commit that URL.
- AWS credentials for the us-east-1 account. In Workshop Studio, open **Get AWS CLI credentials** and paste the macOS/Linux `export` lines into the terminal. Never commit them. They expire, so paste fresh ones if replies stop.
- Bedrock access to Amazon Nova Lite. Check it with:
  ```bash
  aws bedrock-runtime converse --region us-east-1 --model-id us.amazon.nova-lite-v1:0 \
    --messages '[{"role":"user","content":[{"text":"say hi"}]}]' \
    --query 'output.message.content[0].text' --output text
  ```
- An End User Messaging phone number, which the config check requires even though the iPhone sends the texts. The script defaults to the simulator number requested for this project. To request another, run the command below, then export `SMS_PHONE_NUMBER` and `SMS_ORIGINATION_ID` before starting the script:
  ```bash
  aws pinpoint-sms-voice-v2 request-phone-number --region us-east-1 --iso-country-code US \
    --message-type TRANSACTIONAL --number-capabilities SMS --number-type SIMULATOR \
    --query '[PhoneNumber,PhoneNumberArn]' --output text
  ```

### 1. Start the API

```bash
cd california-sms
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
bash scripts/run-local.sh
```

On first run, the script creates the `sms_ledger` table in the `waypoint` database and a random token in `~/.waypoint-token`, outside the repository. Leave it running.

### 2. Open a public tunnel

In a second terminal tab:

```bash
cloudflared tunnel --url http://localhost:8000
```

Copy the `https://<name>.trycloudflare.com` link. It changes every time cloudflared restarts. Test it from a third tab:

```bash
curl -s -X POST https://<name>.trycloudflare.com/sms/reply \
  -H "Authorization: Bearer $(cat ~/.waypoint-token)" -H "Content-Type: application/json" \
  -d '{"sender":"test","body":"3 of us near McLaughlin, we need water"}'
```

The reply should name Tully Community Center.

### 3. Build the iPhone Shortcut

Copy the token with `cat ~/.waypoint-token | pbcopy` and get it onto the iPhone (Universal Clipboard or AirDrop). Then, on the iPhone, open **Shortcuts → Automation → + → Message**:

1. **Message Contains** a single space (so follow-up answers without the word "help" also trigger it), **Run Immediately**, **Notify When Run** off, then **Create New Shortcut**. Because this answers every text the phone receives, use a phone set aside for the demo and turn the automation off afterwards.
2. **Get Contents of URL**: URL `https://<name>.trycloudflare.com/sms/reply`, Method **POST**.
   - Headers: `Authorization` = `Bearer <token>`, `Content-Type` = `application/json`.
   - Request Body **JSON**, two Text fields: `sender` = Shortcut Input → **Sender**, `body` = Shortcut Input → **Content**.
3. **Get Dictionary Value** for key `reply` in Contents of URL.
4. **If** Dictionary Value **has any value**.
5. Inside the If, **Send Message**: Dictionary Value to Shortcut Input → **Sender**. Expand it and turn **Show Compose Sheet** (Show When Run on older iOS) off.

Text `help, 3 of us near McLaughlin need water` to the iPhone from another phone. The Bedrock reply arrives in a few seconds.

### Optional: connect to the Waypoint backend

With the backend running, every text is saved as a request, Bedrock extracts the need, urgency and location, and the backend's matcher picks a verified, open, in-stock site. The reply writer then words that decision in the sender's language. Coordinators see the request in the backend (`GET /api/requests`, or `/docs` in a browser), and both services keep their data in the same PostgreSQL database. If the backend is down, replies fall back to `src/app/resources.json`.

The matching code is on the `role2-unified-matching` branch. In a third terminal tab, from the repository root:

```bash
git fetch origin role2-unified-matching
git worktree add ../backend-work origin/role2-unified-matching
bash california-sms/scripts/run-backend.sh ../backend-work/backend
```

Paste the AWS `export` lines into that tab first: the backend calls Bedrock and Amazon Location Service. It uses the same `waypoint` database and creates its tables with the Alembic migrations. Then restart the SMS service with the link turned on:

```bash
WAYPOINT_BACKEND_URL=http://127.0.0.1:8001 bash scripts/run-local.sh
```

The matcher checks opening hours in Pacific time, so at night it may skip sites that are closed and pick an open one further away.

### On demo day

- Paste fresh AWS credentials, then start `scripts/run-local.sh` and cloudflared again. If the tunnel link changed, update the URL in the Shortcut.
- Keep the laptop awake (`caffeinate -d`) and the iPhone charging, unlocked, and on Wi-Fi.
- Tell judges: "Text what you need and your nearest cross street to (iPhone number)."
- To send everything as SMS rather than iMessage, turn off iMessage on the relay iPhone (Settings → Apps → Messages).
- The token lives only in `~/.waypoint-token` and the Shortcut. Never put it in the website or the repository.

### Cleanup

Delete the Shortcut automation, then drop the database if you no longer need it:

```bash
dropdb waypoint
```

## Processing behavior

- The ledger (DynamoDB, or PostgreSQL with `DATABASE_URL`) tracks request hashes, IDs, and status for approximately seven days. Daily quota counters expire after approximately two days. There is no in-memory runtime fallback.
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

Tests inject isolated AWS test doubles without sending texts or contacting AWS. They live under `tests/` and are outside the Lambda deployment package. The PostgreSQL ledger tests run only when `TEST_DATABASE_URL` points at a disposable database, for example `TEST_DATABASE_URL=postgresql://localhost/waypoint_test`. `src/` contains only real AWS behavior. See `VALIDATION.md` for performed checks and remaining account-level verification.

## Implementation files

- `src/app/main.py`: startup validation, FastAPI routes, and bearer authentication.
- `src/app/models.py`: outgoing and incoming message schemas.
- `src/app/service.py`: AWS sending, Bedrock responses, and idempotency.
- `src/app/waypoint.py` and `src/app/resources.json`: Waypoint reply instructions and the verified location list.
- `src/app/inbound.py`: SNS Lambda entry point.
- `src/app/store.py`: DynamoDB ledger and atomic quota enforcement.
- `src/app/pgstore.py`: the same ledger in PostgreSQL, used when `DATABASE_URL` is set.
- `template.yaml`: infrastructure and IAM permissions.
- `scripts/run-local.sh`: runs the API on a laptop for the iPhone relay demo.
- `src/app/backend.py` and `scripts/run-backend.sh`: optional link to the Waypoint backend's request storage and resource matcher.

## AWS references

- [Two-way SMS](https://docs.aws.amazon.com/sms-voice/latest/userguide/two-way-sms.html)
- [Incoming payload](https://docs.aws.amazon.com/sms-voice/latest/userguide/two-way-sms-payload.html)
- [Registration](https://docs.aws.amazon.com/sms-voice/latest/userguide/registration-help.html)
- [Managed opt-outs](https://docs.aws.amazon.com/sms-voice/latest/userguide/opt-out-list-self-managed.html)
- [Nova Lite](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-lite.html)
