from enum import Enum
from uuid import UUID

from pydantic import Field

from app.api.schemas.common import RecordTimestamps


class RequestUrgency(str, Enum):
    NORMAL = "normal"
    URGENT = "urgent"
    MEDICAL = "medical"


class RequestStatus(str, Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    NEEDS_REVIEW = "needs_review"
    MATCHED = "matched"
    ASSIGNED = "assigned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RequestCreate(RecordTimestamps):
    incident_id: UUID | None = None
    source_phone: str = Field(min_length=1, max_length=30)
    message: str = Field(min_length=1, max_length=2000)
    location_description: str | None = Field(default=None, max_length=500)
    needs: list[str] = Field(default_factory=list)
    people_count: int | None = Field(default=None, ge=1)
    urgency: RequestUrgency = RequestUrgency.NORMAL
    status: RequestStatus = RequestStatus.RECEIVED


class Request(RequestCreate):
    pass
