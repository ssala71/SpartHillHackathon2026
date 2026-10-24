from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas.common import ApiError, ApiResponse
from app.api.schemas.incidents import Incident, IncidentCreate
from app.db.models import Incident as IncidentModel
from app.db.session import get_db

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=ApiError(code="INCIDENT_NOT_FOUND", message="Incident was not found").model_dump(),
    )


@router.post("", response_model=ApiResponse[Incident], status_code=status.HTTP_201_CREATED)
def create_incident(payload: IncidentCreate, db: Session = Depends(get_db)) -> ApiResponse[Incident]:
    incident = IncidentModel(
        name=payload.name,
        description=payload.description,
        affected_area=payload.affected_area,
        status=payload.status,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return ApiResponse(data=Incident.model_validate(incident))


@router.get("", response_model=ApiResponse[list[Incident]])
def list_incidents(
    include_cancelled: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> ApiResponse[list[Incident]]:
    query = select(IncidentModel).order_by(IncidentModel.created_at.desc())
    if not include_cancelled:
        query = query.where(IncidentModel.status != "Cancelled")
    incidents = db.scalars(query).all()
    return ApiResponse(data=[Incident.model_validate(incident) for incident in incidents])


@router.get("/{incident_id}", response_model=ApiResponse[Incident])
def get_incident(incident_id: UUID, db: Session = Depends(get_db)) -> ApiResponse[Incident]:
    incident = db.get(IncidentModel, incident_id)
    if incident is None:
        raise _not_found()
    return ApiResponse(data=Incident.model_validate(incident))
