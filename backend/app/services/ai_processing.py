import json
from typing import Any
from uuid import UUID

from app.api.schemas.ai import AIProcessingResult, ProcessingStatus
from app.api.schemas.common import now_pacific
from app.api.schemas.requests import RequestStatus
from app.core.config import settings
from app.db.models import ProcessingAttempt, Request, StoredAIResult
from app.db.session import create_session_factory


def _mock_response(request: Request) -> tuple[dict[str, Any], AIProcessingResult]:
    result = AIProcessingResult(
        needs=request.needs,
        urgency=request.urgency,
        location=request.location_description,
        people_count=request.people_count,
        household_size=request.household_size,
        missing_information=[],
        needs_review=True,
        summary="Mock Bedrock processing completed; human review is still required.",
    )
    return {"mode": "mock", "output": result.model_dump(mode="json")}, result


def _bedrock_response(request: Request) -> tuple[dict[str, Any], AIProcessingResult]:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
    prompt = (
        "Return only valid JSON with these fields: needs (array of strings), urgency "
        "(Normal, Urgent, or Medical), location (string or null), people_count (integer "
        "or null), household_size (integer or null), missing_information (array of strings), "
        "needs_review (boolean), and summary (string). Never invent facts. Original request:\n\n"
        f"{request.message}"
    )
    response = client.converse(
        modelId=settings.bedrock_model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
    )
    output_text = response["output"]["message"]["content"][0]["text"]
    result = AIProcessingResult.model_validate_json(output_text)
    safe_response = json.loads(json.dumps(response, default=str))
    return safe_response, result


def _process(request: Request) -> tuple[dict[str, Any], AIProcessingResult]:
    if settings.bedrock_enabled:
        return _bedrock_response(request)
    return _mock_response(request)


def process_attempt(attempt_id: UUID) -> None:
    """Process one request attempt in a background task.

    The original request is loaded but never modified. Only its processing
    status changes after the AI result is validated or the attempt fails.
    """
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
            attempt.raw_response = raw_response
            attempt.status = ProcessingStatus.COMPLETED
            attempt.is_active = False
            attempt.completed_at = now_pacific()
            request.status = RequestStatus.NEEDS_REVIEW
            db.add(
                StoredAIResult(
                    request_id=request.id,
                    attempt_id=attempt.id,
                    model_id=attempt.model_id,
                    needs=result.needs,
                    urgency=result.urgency,
                    location=result.location,
                    people_count=result.people_count,
                    household_size=result.household_size,
                    missing_information=result.missing_information,
                    needs_review=result.needs_review,
                    summary=result.summary,
                )
            )
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
