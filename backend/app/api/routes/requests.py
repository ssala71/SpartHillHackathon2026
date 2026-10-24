from hashlib import sha256
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas.common import ApiError, ApiResponse
from app.api.schemas.requests import Request, RequestCreate, RequestList, RequestStatus, RequestStatusUpdate
from app.db.models import Request as RequestModel
from app.db.session import get_db

router = APIRouter(prefix="/api/requests", tags=["requests"])


def _person_id(phone_number: str) -> str:
    normalized_phone = "".join(character for character in phone_number if character.isdigit())
    return sha256(normalized_phone.encode("utf-8")).hexdigest()


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=ApiError(code="REQUEST_NOT_FOUND", message="Request was not found").model_dump(),
    )


@router.post("", response_model=ApiResponse[Request], status_code=status.HTTP_201_CREATED)
def create_request(payload: RequestCreate, db: Session = Depends(get_db)) -> ApiResponse[Request]:
    request = RequestModel(
        incident_id=payload.incident_id,
        person_id=_person_id(payload.source_phone),
        source_phone=payload.source_phone,
        message=payload.message,
        location_description=payload.location_description,
        people_count=payload.people_count,
        household_size=payload.household_size,
        urgency=payload.urgency,
        channel=payload.channel,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return ApiResponse(data=Request.model_validate(request))


@router.get("", response_model=ApiResponse[RequestList])
def list_requests(
    request_status: RequestStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ApiResponse[RequestList]:
    query = select(RequestModel).order_by(RequestModel.created_at.desc()).limit(limit).offset(offset)
    count_query = select(func.count()).select_from(RequestModel)
    if request_status is not None:
        query = query.where(RequestModel.status == request_status)
        count_query = count_query.where(RequestModel.status == request_status)

    records = db.scalars(query).all()
    total = db.scalar(count_query) or 0
    result = RequestList(
        items=[Request.model_validate(record) for record in records],
        total=total,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(data=result)


@router.get("/{request_id}", response_model=ApiResponse[Request])
def get_request(request_id: UUID, db: Session = Depends(get_db)) -> ApiResponse[Request]:
    request = db.get(RequestModel, request_id)
    if request is None:
        raise _not_found()
    return ApiResponse(data=Request.model_validate(request))


@router.patch("/{request_id}/status", response_model=ApiResponse[Request])
def update_request_status(
    request_id: UUID,
    payload: RequestStatusUpdate,
    db: Session = Depends(get_db),
) -> ApiResponse[Request]:
    request = db.get(RequestModel, request_id)
    if request is None:
        raise _not_found()

    request.status = payload.status
    request.status_updated_by_admin_id = payload.admin_user_id
    db.commit()
    db.refresh(request)
    return ApiResponse(data=Request.model_validate(request))
