#!/usr/bin/env bash
# Runs the API on this computer for the iPhone relay demo (see README, "Demo:
# iPhone relay"). Needs the venv active and AWS credentials in this terminal.
# Usage, from california-sms:  bash scripts/run-local.sh
set -euo pipefail

export AWS_REGION=us-east-1
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
TABLE=${TABLE_NAME:-waypoint-sms-ledger}

# Ledger table for the per-sender daily limit, created on first run.
if ! aws dynamodb describe-table --table-name "$TABLE" >/dev/null 2>&1; then
  aws dynamodb create-table --table-name "$TABLE" \
    --attribute-definitions AttributeName=pk,AttributeType=S \
    --key-schema AttributeName=pk,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST >/dev/null
  aws dynamodb wait table-exists --table-name "$TABLE"
  echo "Created table $TABLE"
fi

# The token stays outside the repository and is reused on every run.
TOKEN_FILE="$HOME/.waypoint-token"
[ -f "$TOKEN_FILE" ] || openssl rand -hex 24 > "$TOKEN_FILE"
export API_TOKEN=$(cat "$TOKEN_FILE")

# Simulator number requested for the demo. Override both to use another number.
export SMS_PHONE_NUMBER=${SMS_PHONE_NUMBER:-+12065557813}
export SMS_ORIGINATION_ID=${SMS_ORIGINATION_ID:-arn:aws:sms-voice:us-east-1:$ACCOUNT:phone-number/phone-59fce6467741437e9d78643321f89a6e}
export ALLOWED_RECIPIENTS=${ALLOWED_RECIPIENTS:-+14254147755,+14254147167}
export BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0
export TABLE_NAME=$TABLE
# /sms/reply never publishes to SNS; this only satisfies the config format check.
export INBOUND_TOPIC_ARN=arn:aws:sns:us-east-1:$ACCOUNT:waypoint-unused
export DAILY_LIMIT_PER_RECIPIENT=${DAILY_LIMIT_PER_RECIPIENT:-20}

echo "Token: $TOKEN_FILE"
echo "Listening on http://localhost:8000 (Ctrl+C to stop)"
exec python -m uvicorn app.main:app --app-dir src --host 127.0.0.1 --port 8000
