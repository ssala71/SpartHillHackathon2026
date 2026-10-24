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
    "- medical_concern: true only if the message mentions medicine or medication, "
    "a medical device (oxygen, CPAP, dialysis), an injury, or a health emergency. "
    "Food, water, shelter, charging a phone, and baby formula are NOT medical "
    "concerns on their own.\n"
    "- delivery_mode: \"deliver\" ONLY if the message explicitly asks for something "
    "to be brought to them or says they cannot travel; \"collect\" ONLY if it "
    "explicitly says they can come or pick it up. If the message does not say, "
    "use null. Never infer it from the need or the person's situation.\n"
    "- missing_information: array naming only fields you returned as null, from "
    "[\"needs\", \"location\", \"people_count\", \"delivery_mode\"]. Include "
    "\"delivery_mode\" only when medical_concern is true and delivery_mode is null.\n"
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
    if "medical" in needs and delivery is None:
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


def _apply_rules(result: AIProcessingResult) -> None:
    """Overwrite fields our rules decide, so model guesses can't change routing.

    * needs_review: medical concern, a medicine need, or high urgency.
    * missing_information: rebuilt from the fields that are actually empty.
      Models often list fields they did fill in, or ones we never ask for.
    """
    medicine = "medical" in normalize_needs(result.needs)
    result.needs_review = result.medical_concern or medicine or result.urgency.value == "high"
    missing = []
    if not result.needs:
        missing.append("needs")
    if not result.location:
        missing.append("location")
    if result.people_count is None:
        missing.append("people_count")
    if medicine and result.delivery_mode is None:
        missing.append("delivery_mode")
    result.missing_information = missing


def _mock_response(request: Request) -> tuple[dict[str, Any], AIProcessingResult]:
    result = _mock_extract(request.message)
    return {"mode": "mock", "output": result.model_dump(mode="json")}, result


def _bedrock_response(request: Request) -> tuple[dict[str, Any], AIProcessingResult]:
    import boto3

    from botocore.exceptions import ClientError

    client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
    call = {
        "modelId": settings.bedrock_model_id,
        "messages": [{"role": "user", "content": [{"text": BEDROCK_PROMPT + request.message}]}],
    }
    try:
        response = client.converse(**call, inferenceConfig={"temperature": 0, "maxTokens": 2000})
    except ClientError as error:
        # Newer Claude models (e.g. Sonnet 5.5) reject `temperature`; retry without it.
        if "temperature" not in str(error):
            raise
        response = client.converse(**call, inferenceConfig={"maxTokens": 2000})
    # Some models return reasoning blocks before the answer; use the text blocks only.
    blocks = response["output"]["message"]["content"]
    output_text = "".join(block["text"] for block in blocks if "text" in block)
    if not output_text.strip():
        kinds = [next(iter(block), "?") for block in blocks]
        raise ValueError(f"Model returned no text (stopReason={response.get('stopReason')}, blocks={kinds})")
    result = _parse_model_json(output_text)
    _apply_rules(result)
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
