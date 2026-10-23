from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

PACIFIC_TIMEZONE = ZoneInfo("America/Los_Angeles")
DataT = TypeVar("DataT")


def now_pacific() -> datetime:
    """Return a timezone-aware timestamp in Pacific time."""
    return datetime.now(PACIFIC_TIMEZONE)


class ApiError(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: list[dict[str, str]] = Field(default_factory=list)


class ApiResponse(BaseModel, Generic[DataT]):
    data: DataT | None = None
    error: ApiError | None = None


class RecordTimestamps(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=now_pacific)
    updated_at: datetime = Field(default_factory=now_pacific)
