"""Pydantic request and response contracts for the API."""

from app.api.schemas.assignments import Assignment, AssignmentCreate, AssignmentStatus
from app.api.schemas.ai import AIProcessingResult, MatchResult, ProcessingAttempt, ProcessingJob, ProcessingStatus, StoredAIResult
from app.api.schemas.common import ApiError, ApiResponse, RecordTimestamps
from app.api.schemas.incidents import Incident, IncidentCreate, IncidentStatus
from app.api.schemas.inventory import (
    InventoryCategory,
    InventoryItem,
    InventoryItemCreate,
    InventoryStatus,
)
from app.api.schemas.requests import (
    Request,
    RequestChannel,
    RequestCreate,
    RequestList,
    RequestStatus,
    RequestStatusUpdate,
    RequestUrgency,
)
from app.api.schemas.resources import Resource, ResourceCreate, ResourceStatus

__all__ = [
    "ApiError",
    "ApiResponse",
    "AIProcessingResult",
    "Assignment",
    "AssignmentCreate",
    "AssignmentStatus",
    "Incident",
    "IncidentCreate",
    "IncidentStatus",
    "InventoryItem",
    "InventoryItemCreate",
    "InventoryCategory",
    "InventoryStatus",
    "MatchResult",
    "RecordTimestamps",
    "Request",
    "RequestChannel",
    "RequestCreate",
    "RequestList",
    "RequestStatus",
    "RequestStatusUpdate",
    "RequestUrgency",
    "ProcessingAttempt",
    "ProcessingJob",
    "ProcessingStatus",
    "Resource",
    "ResourceCreate",
    "ResourceStatus",
    "StoredAIResult",
]
