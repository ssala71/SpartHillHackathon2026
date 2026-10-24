from enum import Enum
from uuid import UUID

from pydantic import Field

from app.api.schemas.common import RecordTimestamps


class AssignmentStatus(str, Enum):
    PENDING = "Pending"
    ACCEPTED = "Accepted"
    IN_PROGRESS = "InProgress"
    COMPLETED = "Completed"
    DECLINED = "Declined"
    CANCELLED = "Cancelled"


class AssignmentCreate(RecordTimestamps):
    request_id: UUID
    resource_id: UUID
    coordinator_name: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=1000)
    status: AssignmentStatus = AssignmentStatus.PENDING


class Assignment(AssignmentCreate):
    pass
