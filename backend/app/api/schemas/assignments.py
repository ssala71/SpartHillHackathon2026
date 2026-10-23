from enum import Enum
from uuid import UUID

from pydantic import Field

from app.api.schemas.common import RecordTimestamps


class AssignmentStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class AssignmentCreate(RecordTimestamps):
    request_id: UUID
    resource_id: UUID
    coordinator_name: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=1000)
    status: AssignmentStatus = AssignmentStatus.PENDING


class Assignment(AssignmentCreate):
    pass
