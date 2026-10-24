#!/usr/bin/env bash
# Runs the Waypoint backend API (backend/ on the role2-unified-matching branch) on
# this computer with PostgreSQL, real Bedrock extraction, and Amazon Location
# geocoding (falls back to the offline San Jose list).
# Usage: bash scripts/run-backend.sh <path to that branch's backend folder>
set -euo pipefail

cd "${1:?Pass the backend folder, for example ../backend-work/backend}"
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt

export AWS_REGION=us-east-1
# Same database as scripts/run-local.sh; SQLAlchemy needs the +psycopg driver form.
DB=${DATABASE_URL:-postgresql://localhost/waypoint}
export DATABASE_URL=$(echo "$DB" | sed 's#^postgresql://#postgresql+psycopg://#')
export BEDROCK_ENABLED=true
export BEDROCK_MODEL_ID=${BEDROCK_MODEL_ID:-us.amazon.nova-lite-v1:0}
export GEOCODING_PROVIDER=${GEOCODING_PROVIDER:-aws_location}

# Create or update the backend tables.
alembic upgrade head

echo "Backend on http://127.0.0.1:8001 (API docs at /docs). Ctrl+C to stop."
exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
