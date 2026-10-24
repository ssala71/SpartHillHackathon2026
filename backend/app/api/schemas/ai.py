from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from app.api.schemas.common import RecordTimestamps
from app.api.schemas.requests import DeliveryMode, RequestStatus, RequestUrgency


class ProcessingStatus(str, Enum):
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"


class AIProcessingResult(BaseModel):
    """What Bedrock returns for one message (the shared Role 2 request format).

    ``needs`` should use the canonical categories in
    ``app.resource_matching.adapter.CANONICAL_NEEDS``; the adapter also maps
    common synonyms. Coordinates are never produced by the model; they are
    filled in by the geocoder after validation.
    """

    needs: list[str] = Field(default_factory=list)
    urgency: RequestUrgency
    location: str | None = None
    people_count: int | None = Field(default=None, ge=1)
    household_size: int | None = Field(default=None, ge=1)
    medical_concern: bool = False
    delivery_mode: DeliveryMode | None = None
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
    latitude: float | None = None
    longitude: float | None = None
    location_source: str | None = None
    people_count: int | None = None
    household_size: int | None = None
    medical_concern: bool = False
    delivery_mode: DeliveryMode | None = None
    missing_information: list[str]
    needs_review: bool
    summary: str


class MatchAction(str, Enum):
    DIRECT_TO_LOCATION = "direct_to_location"
    COORDINATOR_REVIEW = "coordinator_review"
    FOLLOW_UP = "follow_up"
    NO_MATCH = "no_match"
    NOT_PROCESSED = "not_processed"


class MatchedResource(BaseModel):
    """Every field is copied from a sourced resource record, never from AI output."""

    resource_id: str
    name: str
    address: str
    distance_km: float
    matched_needs: list[str]
    source: str
    last_verified_at: str | None = None
    simulated: bool


class MatchResult(BaseModel):
    request_id: UUID
    matched: bool = False
    needs_review: bool = True
    action: MatchAction = MatchAction.NOT_PROCESSED
    reason: str
    resource: MatchedResource | None = None
    follow_up_message: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    delivery_mode: DeliveryMode | None = None
    location_source: str | None = None
    disclaimer: str | None = None
