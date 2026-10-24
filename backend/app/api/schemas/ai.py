from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from app.api.schemas.common import RecordTimestamps
from app.api.schemas.requests import RequestStatus, RequestUrgency


class ProcessingStatus(str, Enum):
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"


class AIProcessingResult(BaseModel):
    needs: list[str] = Field(default_factory=list)
    urgency: RequestUrgency
    location: str | None = None
    people_count: int | None = Field(default=None, ge=1)
    household_size: int | None = Field(default=None, ge=1)
    missing_information: list[str] = Field(default_factory=list)
    needs_review: bool = True
    summary: str = Field(min_length=1, max_length=2000)


class ProcessingAttempt(RecordTimestamps):
    request_id: UUID
    attempt_number: int = Field(ge=1)
    status: ProcessingStatus
    model_id: str
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class ProcessingJob(BaseModel):
    request_id: UUID
    attempt_id: UUID
    request_status: RequestStatus
    processing_status: ProcessingStatus


class StoredAIResult(RecordTimestamps):
    request_id: UUID
    attempt_id: UUID
    model_id: str
    needs: list[str]
    urgency: RequestUrgency
    location: str | None = None
    people_count: int | None = None
    household_size: int | None = None
    missing_information: list[str]
    needs_review: bool
    summary: str


class MatchResult(BaseModel):
    request_id: UUID
    matched: bool = False
    needs_review: bool = True
    reason: str
