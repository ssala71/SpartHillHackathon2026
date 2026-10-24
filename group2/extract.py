"""
Person A — Bedrock request processing.

Reads ONE SMS message and pulls out whatever of the four required fields it
contains: category (food/medicine/other), address, urgency, people_count.
The conversation layer merges results across messages and asks for whatever
is still missing in a single follow-up.

  - We ask Bedrock for STRICT JSON and parse defensively.
  - On any failure we raise ExtractionError so the caller can mark the
    request FAILED and keep it visible for retry (reliability requirement).
  - We never invent a field the user didn't express; unknown stays null.

Local dev: set USE_FAKE_BEDROCK=1 to run without AWS credentials.
"""

from __future__ import annotations

import json
import os
import re

from schema import Category, Urgency, DeliveryMode


BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
)
USE_FAKE_BEDROCK = os.environ.get("USE_FAKE_BEDROCK", "0") == "1"


class ExtractionError(Exception):
    """Raised when we cannot interpret a message at all."""


SYSTEM_PROMPT = """You read a single SMS from a resident during an outage and \
extract ONLY what the message actually says. Do not invent anything. If a field \
is not stated, return null.

Return STRICT JSON ONLY (no prose, no markdown) with exactly these keys:
{
  "category": one of ["food","medicine","other"] or null,
  "address": string or null,            // location, cross street, or landmark
  "urgency": one of ["high","medium","low"] or null,
  "people_count": integer or null,
  "delivery_mode": one of ["deliver","collect"] or null,
  "model_notes": short string explaining your reasoning
}

Rules:
- category "medicine" = medication, medical device/supplies, health needs.
- category "food" = food, water, baby formula, meals.
- category "other" = shelter, charging, information, anything else.
- delivery_mode "deliver" = they need it brought to them; "collect" = they can
  travel to pick it up. Only set if the message clearly says so.
- Only set a field if the message clearly states it. Otherwise null.
"""


def extract_fields(raw_message: str) -> dict:
    """Return a dict with keys category/address/urgency/people_count/model_notes.
    Any field the message doesn't state is None."""
    if not raw_message or not raw_message.strip():
        raise ExtractionError("Empty message")

    if USE_FAKE_BEDROCK:
        data = _fake_bedrock(raw_message)
    else:
        data = _call_bedrock(raw_message)

    return _clean(data)


def _call_bedrock(raw_message: str) -> dict:
    try:
        import boto3
    except ImportError as e:
        raise ExtractionError(
            "boto3 not installed; pip install boto3 or set USE_FAKE_BEDROCK=1"
        ) from e

    client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 400,
        "temperature": 0,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": raw_message}]}
        ],
    }
    try:
        resp = client.invoke_model(modelId=BEDROCK_MODEL_ID, body=json.dumps(body))
        payload = json.loads(resp["body"].read())
        text = payload["content"][0]["text"]
    except Exception as e:
        raise ExtractionError(f"Bedrock call failed: {e}") from e

    return _parse_json_block(text)


def _parse_json_block(text: str) -> dict:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            text = brace.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ExtractionError(f"Model did not return valid JSON: {e}") from e


VALID_CATEGORIES = {c.value for c in Category}
VALID_URGENCY = {Urgency.HIGH.value, Urgency.MEDIUM.value, Urgency.LOW.value}


def _clean(data: dict) -> dict:
    cat = data.get("category")
    if cat not in VALID_CATEGORIES:
        cat = None

    urg = data.get("urgency")
    if urg not in VALID_URGENCY:
        urg = None

    people = data.get("people_count")
    if isinstance(people, str) and people.strip().isdigit():
        people = int(people.strip())
    if not isinstance(people, int):
        people = None

    addr = data.get("address")
    if isinstance(addr, str) and not addr.strip():
        addr = None

    dm = data.get("delivery_mode")
    if dm not in (DeliveryMode.DELIVER.value, DeliveryMode.COLLECT.value):
        dm = None

    return {
        "category": cat,
        "address": addr,
        "urgency": urg,
        "people_count": people,
        "delivery_mode": dm,
        "model_notes": data.get("model_notes"),
    }


# Offline fake — keyword rules so the team can build without AWS.
def _fake_bedrock(raw_message: str) -> dict:
    msg = raw_message.lower()

    category = None
    if any(w in msg for w in ["insulin", "medicine", "medication", "oxygen",
                              "dialysis", "medical", "pills", "prescription"]):
        category = Category.MEDICINE.value
    elif any(w in msg for w in ["food", "water", "formula", "eat", "hungry",
                                "meal", "thirsty"]):
        category = Category.FOOD.value
    elif any(w in msg for w in ["shelter", "charge", "charging", "power",
                                "stay", "sleep", "information"]):
        category = Category.OTHER.value

    urgency = None
    if any(w in msg for w in ["high", "urgent", "emergency", "now", "asap",
                              "running out", "critical"]):
        urgency = Urgency.HIGH.value
    elif "medium" in msg:
        urgency = Urgency.MEDIUM.value
    elif "low" in msg:
        urgency = Urgency.LOW.value

    # Stop the address capture at a comma, period, "for", or a number so it
    # does not swallow the people count ("near Story Rd for 50 people").
    address = None
    m = re.search(r"near ([a-z0-9 .]+?)(?=\.|,|$| with| and| for |\s*\d)", msg)
    if m:
        address = m.group(1).strip().title()
    else:
        m2 = re.search(r"on ([a-z0-9 .]+ (?:road|rd|street|st|ave|avenue|blvd))", msg)
        if m2:
            address = m2.group(1).strip().title()

    people = None
    m3 = re.search(r"(\d+)\s*(?:people|persons|of us|ppl|adults|family members)", msg)
    if m3:
        people = int(m3.group(1))
    elif any(p in msg for p in ["just me", "only me", "myself", "alone", "1 person"]):
        people = 1
    elif "grandmother" in msg or "grandma" in msg:
        people = 2

    delivery_mode = None
    if any(w in msg for w in ["deliver", "bring it", "bring them", "come to me",
                              "can't travel", "cannot travel", "bedridden"]):
        delivery_mode = DeliveryMode.DELIVER.value
    elif any(w in msg for w in ["collect", "pick up", "pickup", "come get",
                                "i can travel", "we can travel", "can come"]):
        delivery_mode = DeliveryMode.COLLECT.value

    return {
        "category": category,
        "address": address,
        "urgency": urgency,
        "people_count": people,
        "delivery_mode": delivery_mode,
        "model_notes": "FAKE keyword extraction (offline dev mode, not real Bedrock).",
    }
