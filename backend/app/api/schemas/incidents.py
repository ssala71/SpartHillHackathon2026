from enum import Enum

from pydantic import Field

from app.api.schemas.common import RecordTimestamps


class IncidentStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class IncidentCreate(RecordTimestamps):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    affected_area: str = Field(min_length=1, max_length=500)
    status: IncidentStatus = IncidentStatus.DRAFT


class Incident(IncidentCreate):
    pass
