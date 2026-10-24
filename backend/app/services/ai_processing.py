import json
import re
from typing import Any
from uuid import UUID

from app.api.schemas.ai import AIProcessingResult, MatchAction, ProcessingStatus
from app.api.schemas.common import now_pacific
from app.api.schemas.requests import RequestStatus
from app.core.config import settings
from app.db.models import ProcessingAttempt, Request, StoredAIResult
from app.db.session import create_session_factory
from app.resource_matching.adapter import CANONICAL_NEEDS, normalize_needs
from app.services.geocoding import geocode

BEDROCK_PROMPT = (
    "You read one SMS from a resident during an outage or disaster. Extract only "
    "what the message says; never invent facts. Return ONLY a JSON object (no "
    "prose, no markdown) with these fields:\n"
    f"- needs: array of strings from {list(CANONICAL_NEEDS)}. Use \"medical\" for "
    "medicine, medication, or medical supplies and \"power\" for charging.\n"
    "- urgency: \"low\", \"medium\", or \"high\". Use \"high\" for medical devices, "
    "medication running out, injury, immediate danger, or a vulnerable person at risk.\n"
    "- location: the location text exactly as described (cross street, landmark, "
    "address), or null.\n"
    "- people_count: integer or null.\n"
    "- household_size: integer or null.\n"
    "- medical_concern: true if the message mentions medicine, a medical device, "
    "or a health need; otherwise false.\n"
    "- delivery_mode: \"deliver\" if they say they need it brought to them, "
    "\"collect\" if they say they can travel to pick it up, otherwise null.\n"
    "- missing_information: array naming what is not stated, from "
    "[\"needs\", \"location\", \"people_count\", \"delivery_mode\"]. Include "
    "\"delivery_mode\" only for medicine requests.\n"
    "- needs_review: true if a coordinator should review it.\n"
    "- summary: one short sentence.\n\n"
    "Message:\n"
)


def _parse_model_json(text: str) -> AIProcessingResult:
    """Models sometimes wrap JSON in prose or code fences; extract the object."""
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    else:
        brace = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if brace:
            cleaned = brace.group(0)
    return AIProcessingResult.model_validate_json(cleaned)


# ---------------------------------------------------------------------------
# Offline mock: simple keyword rules so the full flow runs without AWS.
# Clearly labeled as mock output; it is not Bedrock.
# ---------------------------------------------------------------------------

_MOCK_NEEDS = [
    ("medical", re.compile(r"insulin|medicine|medication|prescription|oxygen|dialysis|inhaler|pills|medical", re.I)),
    ("water", re.compile(r"\bwater\b|thirst|\bagua\b", re.I)),
    ("food", re.compile(r"\bfood\b|hungry|\beat\b|\bmeals?\b|groceries|comida", re.I)),
    ("shelter", re.compile(r"shelter|place to (stay|sleep)|nowhere to (go|stay)", re.I)),
    ("power", re.compile(r"charg|battery|\bpower\b(?! is out| outage)", re.I)),
    ("baby_formula", re.compile(r"formula|baby food", re.I)),
]
_MOCK_HIGH = re.compile(r"urgent|emergency|asap|right now|running out|critical|\bhigh\b|can'?t breathe|injur", re.I)
_MOCK_MEDIUM = re.compile(r"\bmedium\b|soon|today", re.I)
_MOCK_LOW = re.compile(r"\blow\b|not urgent|whenever", re.I)
_MOCK_DELIVER = re.compile(r"deliver|bring (it|them)|can'?t (travel|leave|walk)|bedridden|homebound", re.I)
_MOCK_COLLECT = re.compile(r"collect|pick ?up|come get|can (travel|come|walk)", re.I)
_MOCK_LOCATION = re.compile(
    r"\b(?:near|at|on|by)\s+([A-Za-z0-9 .&']+?)(?=[,.!?]|\s+(?:with|for|we|i|need|needs|and we|and i)\b|$)", re.I
)
_MOCK_PEOPLE = re.compile(r"(\d+)\s*(?:people|persons|of us|ppl|adults|family members|kids)", re.I)
_MOCK_ALONE = re.compile(r"just me|only me|myself|alone|\b1 person\b", re.I)


def _mock_extract(message: str) -> AIProcessingResult:
    needs = [need for need, pattern in _MOCK_NEEDS if pattern.search(message)]
    medical = "medical" in needs or bool(re.search(r"medical device|cpap|concentrator", message, re.I))
    if _MOCK_HIGH.search(message):
        urgency = "high"
    elif _MOCK_MEDIUM.search(message):
        urgency = "medium"
    elif _MOCK_LOW.search(message):
        urgency = "low"
    else:
        urgency = "high" if medical else "low"

    location_match = _MOCK_LOCATION.search(message)
    location = re.sub(r"\s+and$", "", location_match.group(1).strip(), flags=re.I) if location_match else None

    people_match = _MOCK_PEOPLE.search(message)
    if people_match:
        people = int(people_match.group(1))
    elif _MOCK_ALONE.search(message):
        people = 1
    else:
        people = None

    delivery = "deliver" if _MOCK_DELIVER.search(message) else "collect" if _MOCK_COLLECT.search(message) else None

    missing = []
    if not needs:
        missing.append("needs")
    if not location:
        missing.append("location")
    if people is None:
        missing.append("people_count")
    if medical and delivery is None:
        missing.append("delivery_mode")

    return AIProcessingResult(
        needs=needs,
        urgency=urgency,
        location=location,
        people_count=people,
        medical_concern=medical,
        delivery_mode=delivery,
        missing_information=missing,
        needs_review=medical or urgency == "high",
        summary="MOCK keyword extraction (Bedrock disabled); a coordinator should verify.",
    )


def _mock_response(request: Request) -> tuple[dict[str, Any], AIProcessingResult]:
    result = _mock_extract(request.message)
    return {"mode": "mock", "output": result.model_dump(mode="json")}, result


def _bedrock_response(request: Request) -> tuple[dict[str, Any], AIProcessingResult]:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
    response = client.converse(
        modelId=settings.bedrock_model_id,
        messages=[{"role": "user", "content": [{"text": BEDROCK_PROMPT + request.message}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 600},
    )
    output_text = response["output"]["message"]["content"][0]["text"]
    result = _parse_model_json(output_text)
    safe_response = json.loads(json.dumps(response, default=str))
    return safe_response, result


def _process(request: Request) -> tuple[dict[str, Any], AIProcessingResult]:
    if settings.bedrock_enabled:
        return _bedrock_response(request)
    return _mock_response(request)


def _status_after_match(action: MatchAction) -> RequestStatus:
    if action is MatchAction.DIRECT_TO_LOCATION:
        return RequestStatus.MATCHED
    return RequestStatus.NEEDS_REVIEW


def process_attempt(attempt_id: UUID) -> None:
    """Process one request attempt in a background task.

    The original request is loaded but never modified. Only its processing
    status changes after the AI result is validated or the attempt fails.
    """
    # Imported here to avoid a circular import at module load.
    from app.services.request_matching import build_match_result

    session_factory = create_session_factory()
    with session_factory() as db:
        attempt = db.get(ProcessingAttempt, attempt_id)
        if attempt is None:
            return
        request = db.get(Request, attempt.request_id)
        if request is None:
            attempt.status = ProcessingStatus.FAILED
            attempt.error_message = "The request no longer exists"
            attempt.is_active = False
            attempt.completed_at = now_pacific()
            db.commit()
            return

        try:
            raw_response, result = _process(request)
            location_text = result.location or request.location_description
            point = geocode(location_text)
            attempt.raw_response = raw_response
            attempt.status = ProcessingStatus.COMPLETED
            attempt.is_active = False
            attempt.completed_at = now_pacific()
            stored = StoredAIResult(
                request_id=request.id,
                attempt_id=attempt.id,
                model_id=attempt.model_id,
                needs=normalize_needs(result.needs),
                urgency=result.urgency,
                location=location_text,
                latitude=point.latitude if point else None,
                longitude=point.longitude if point else None,
                location_source=point.source if point else None,
                people_count=result.people_count,
                household_size=result.household_size,
                medical_concern=result.medical_concern,
                delivery_mode=result.delivery_mode.value if result.delivery_mode else None,
                missing_information=result.missing_information,
                needs_review=result.needs_review,
                summary=result.summary,
            )
            db.add(stored)
            match = build_match_result(request.id, stored)
            request.status = _status_after_match(match.action)
            db.commit()
        except Exception as error:  # noqa: BLE001 - failures are persisted for retry
            db.rollback()
            attempt = db.get(ProcessingAttempt, attempt_id)
            request = db.get(Request, attempt.request_id) if attempt else None
            if attempt is not None:
                attempt.status = ProcessingStatus.FAILED
                attempt.error_message = str(error)[:2000]
                attempt.is_active = False
                attempt.completed_at = now_pacific()
            if request is not None:
                request.status = RequestStatus.NEEDS_REVIEW
            db.commit()
