from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.schemas.ai import MatchResult, ProcessingAttempt, ProcessingJob, ProcessingStatus, StoredAIResult
from app.api.schemas.common import ApiError, ApiResponse
from app.api.schemas.requests import RequestStatus
from app.core.config import settings
from app.db.models import ProcessingAttempt as ProcessingAttemptModel
from app.db.models import Request as RequestModel
from app.db.models import StoredAIResult as StoredAIResultModel
from app.db.session import get_db
from app.services.ai_processing import process_attempt
from app.services.request_matching import build_match_result

router = APIRouter(prefix="/api/requests", tags=["ai-processing"])


def _error(code: str, message: str, response_status: int) -> HTTPException:
    return HTTPException(
        status_code=response_status,
        detail=ApiError(code=code, message=message).model_dump(),
    )


def _start_attempt(request_id: UUID, db: Session) -> ProcessingAttemptModel:
    request = db.get(RequestModel, request_id)
    if request is None:
        raise _error("REQUEST_NOT_FOUND", "Request was not found", status.HTTP_404_NOT_FOUND)

    active_attempt = db.scalar(
        select(ProcessingAttemptModel).where(
            ProcessingAttemptModel.request_id == request_id,
            ProcessingAttemptModel.is_active.is_(True),
        )
    )
    if active_attempt is not None:
        raise _error("PROCESSING_IN_PROGRESS", "A processing attempt is already active", status.HTTP_409_CONFLICT)

    attempt_number = (db.scalar(
        select(func.coalesce(func.max(ProcessingAttemptModel.attempt_number), 0)).where(
            ProcessingAttemptModel.request_id == request_id
        )
    ) or 0) + 1
    attempt = ProcessingAttemptModel(
        request_id=request_id,
        attempt_number=attempt_number,
        status=ProcessingStatus.PROCESSING,
        model_id=settings.bedrock_model_id,
        is_active=True,
    )
    request.status = RequestStatus.PROCESSING
    db.add(attempt)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise _error("PROCESSING_IN_PROGRESS", "A processing attempt is already active", status.HTTP_409_CONFLICT) from error
    db.refresh(attempt)
    return attempt


@router.post("/{request_id}/process", response_model=ApiResponse[ProcessingJob], status_code=status.HTTP_202_ACCEPTED)
def process_request(
    request_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ApiResponse[ProcessingJob]:
    attempt = _start_attempt(request_id, db)
    background_tasks.add_task(process_attempt, attempt.id)
    return ApiResponse(
        data=ProcessingJob(
            request_id=request_id,
            attempt_id=attempt.id,
            request_status=RequestStatus.PROCESSING,
            processing_status=ProcessingStatus.PROCESSING,
        )
    )


@router.get("/{request_id}/processing", response_model=ApiResponse[ProcessingAttempt])
def get_processing_status(request_id: UUID, db: Session = Depends(get_db)) -> ApiResponse[ProcessingAttempt]:
    attempt = db.scalar(
        select(ProcessingAttemptModel)
        .where(ProcessingAttemptModel.request_id == request_id)
        .order_by(ProcessingAttemptModel.attempt_number.desc())
    )
    if attempt is None:
        raise _error("PROCESSING_NOT_FOUND", "No processing attempt exists", status.HTTP_404_NOT_FOUND)
    return ApiResponse(data=ProcessingAttempt.model_validate(attempt))


@router.post("/{request_id}/retry", response_model=ApiResponse[ProcessingJob], status_code=status.HTTP_202_ACCEPTED)
def retry_request(
    request_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ApiResponse[ProcessingJob]:
    latest = db.scalar(
        select(ProcessingAttemptModel)
        .where(ProcessingAttemptModel.request_id == request_id)
        .order_by(ProcessingAttemptModel.attempt_number.desc())
    )
    if latest is None or latest.status != ProcessingStatus.FAILED:
        raise _error("RETRY_NOT_AVAILABLE", "Only failed processing attempts can be retried", status.HTTP_409_CONFLICT)
    attempt = _start_attempt(request_id, db)
    background_tasks.add_task(process_attempt, attempt.id)
    return ApiResponse(
        data=ProcessingJob(
            request_id=request_id,
            attempt_id=attempt.id,
            request_status=RequestStatus.PROCESSING,
            processing_status=ProcessingStatus.PROCESSING,
        )
    )


@router.get("/{request_id}/match", response_model=ApiResponse[MatchResult])
def get_match_result(request_id: UUID, db: Session = Depends(get_db)) -> ApiResponse[MatchResult]:
    """Next action for a request: direct to a place, coordinator review,
    one combined follow-up question, or an honest no-match."""
    request = db.get(RequestModel, request_id)
    if request is None:
        raise _error("REQUEST_NOT_FOUND", "Request was not found", status.HTTP_404_NOT_FOUND)
    latest_result = db.scalar(
        select(StoredAIResultModel)
        .where(StoredAIResultModel.request_id == request_id)
        .order_by(StoredAIResultModel.created_at.desc())
    )
    return ApiResponse(data=build_match_result(request_id, latest_result))


@router.get("/{request_id}/result", response_model=ApiResponse[StoredAIResult])
def get_ai_result(request_id: UUID, db: Session = Depends(get_db)) -> ApiResponse[StoredAIResult]:
    result = db.scalar(
        select(StoredAIResultModel)
        .where(StoredAIResultModel.request_id == request_id)
        .order_by(StoredAIResultModel.created_at.desc())
    )
    if result is None:
        raise _error("AI_RESULT_NOT_FOUND", "No validated AI result exists", status.HTTP_404_NOT_FOUND)
    return ApiResponse(data=StoredAIResult.model_validate(result))
