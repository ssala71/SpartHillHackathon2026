from enum import Enum

from pydantic import Field

from app.api.schemas.common import RecordTimestamps


class ResourceStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    TEMPORARILY_CLOSED = "TemporarilyClosed"
    NEEDS_VERIFICATION = "NeedsVerification"


class ResourceCreate(RecordTimestamps):
    name: str = Field(min_length=1, max_length=200)
    resource_type: str = Field(min_length=1, max_length=100)
    address: str = Field(min_length=1, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    status: ResourceStatus = ResourceStatus.NEEDS_VERIFICATION


class Resource(ResourceCreate):
    pass
