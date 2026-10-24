from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.api.schemas.common import RecordTimestamps


class RequestUrgency(str, Enum):
    NORMAL = "Normal"
    URGENT = "Urgent"
    MEDICAL = "Medical"


class RequestStatus(str, Enum):
    RECEIVED = "Received"
    PROCESSING = "Processing"
    NEEDS_REVIEW = "NeedsReview"
    MATCHED = "Matched"
    ASSIGNED = "Assigned"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class RequestChannel(str, Enum):
    FRONTEND = "Frontend"
    SMS = "SMS"


class RequestCreate(BaseModel):
    incident_id: UUID | None = None
    source_phone: str = Field(min_length=1, max_length=30)
    message: str = Field(min_length=1, max_length=2000)
    location_description: str | None = Field(default=None, max_length=500)
    needs: list[str] = Field(default_factory=list)
    people_count: int | None = Field(default=None, ge=1)
    household_size: int | None = Field(default=None, ge=1)
    urgency: RequestUrgency = RequestUrgency.NORMAL
    channel: RequestChannel = RequestChannel.FRONTEND

    @field_validator("source_phone")
    @classmethod
    def phone_must_contain_digits(cls, value: str) -> str:
        if not any(character.isdigit() for character in value):
            raise ValueError("source_phone must contain at least one digit")
        return value


class RequestStatusUpdate(BaseModel):
    status: RequestStatus
    admin_user_id: UUID


class Request(RecordTimestamps):
    incident_id: UUID | None = None
    person_id: str = Field(min_length=64, max_length=64)
    source_phone: str = Field(min_length=1, max_length=30)
    message: str = Field(min_length=1, max_length=2000)
    location_description: str | None = Field(default=None, max_length=500)
    needs: list[str] = Field(default_factory=list)
    people_count: int | None = Field(default=None, ge=1)
    household_size: int | None = Field(default=None, ge=1)
    urgency: RequestUrgency = RequestUrgency.NORMAL
    channel: RequestChannel
    status: RequestStatus
    status_updated_by_admin_id: UUID | None = None


class RequestList(BaseModel):
    items: list[Request]
    total: int
    limit: int
    offset: int
