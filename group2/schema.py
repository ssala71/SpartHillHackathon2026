"""
Shared data contract for the SMS Disaster Resource Coordinator.

THIS IS THE CONTRACT between Group 2 (us), Group 1 (backend/storage/SMS),
and Group 3 (dashboard). Freeze these shapes early. If a field changes,
tell the whole team before changing it here.

Flow this supports:
  1. User texts freeform: "I need xyz"
  2. We classify category: food / medicine / other
  3. We gather the four required fields across follow-up SMS (asking for all
     missing fields in ONE message):
        category, address, urgency, people_count
  4. When complete, we match to the nearest available place.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
import json


class Category(str, Enum):
    FOOD = "food"
    MEDICINE = "medicine"
    OTHER = "other"


class Urgency(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"      # not yet provided -> triggers a follow-up


class DeliveryMode(str, Enum):
    DELIVER = "deliver"      # needs someone to bring the medicine to them
    COLLECT = "collect"      # can travel to collect it themselves
    UNKNOWN = "unknown"      # not yet provided


# Base fields we always collect before matching.
REQUIRED_FIELDS = ("category", "address", "urgency", "people_count")
# delivery_mode is ALSO required, but ONLY when category == medicine.


class RequestStatus(str, Enum):
    RECEIVED = "received"            # saved before AI ran (reliability anchor)
    GATHERING = "gathering"          # waiting on follow-up answers
    COMPLETE = "complete"            # all required fields gathered
    NEEDS_REVIEW = "needs_review"    # medicine / high urgency -> coordinator
    MATCHED = "matched"              # a place was suggested
    NO_MATCH = "no_match"            # honest: nothing suitable available
    FAILED = "failed"               # AI/processing error -> stays visible for retry


class ActionType(str, Enum):
    DIRECT_TO_LOCATION = "direct_to_location"
    REVIEW_QUEUE = "review_queue"
    FOLLOW_UP = "follow_up"
    NO_ACTION = "no_action"


@dataclass
class StructuredRequest:
    """What the conversation builds up from one or more SMS messages.
    AI interpretation ONLY — resource availability lives in the dataset."""
    phone: str
    raw_messages: list[str] = field(default_factory=list)  # every text, in order
    category: Optional[str] = None            # Category value
    address: Optional[str] = None
    urgency: str = Urgency.UNKNOWN.value
    people_count: Optional[int] = None
    delivery_mode: str = DeliveryMode.UNKNOWN.value  # only required for medicine
    model_notes: Optional[str] = None

    def missing_fields(self) -> list[str]:
        """Which required fields are still unknown. delivery_mode is only
        required when the category is medicine."""
        missing = []
        if not self.category:
            missing.append("category")
        if not self.address:
            missing.append("address")
        if self.urgency == Urgency.UNKNOWN.value:
            missing.append("urgency")
        if self.people_count is None:
            missing.append("people_count")
        # Ask delivery mode only once we know it's a medicine request.
        if self.category == Category.MEDICINE.value and \
                self.delivery_mode == DeliveryMode.UNKNOWN.value:
            missing.append("delivery_mode")
        return missing

    def is_complete(self) -> bool:
        return not self.missing_fields()

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class Resource:
    """A verified resource record. 'source' and 'last_verified' are REQUIRED —
    they are the trust story. Never fabricate availability."""
    id: str
    name: str
    location_text: str
    lat: Optional[float]
    lon: Optional[float]
    categories: list[str]            # Category values this place serves
    capacity: int                    # how many people it can currently take
    operating_status: str            # "open" | "closed" | "limited"
    source: str
    last_verified: str               # ISO timestamp
    is_simulated: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MatchResult:
    """Honest by design: if nothing suitable, matched=False and we explain why.
    We never invent a match."""
    phone: Optional[str]
    matched: bool
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    reason: Optional[str] = None
    action: str = ActionType.NO_ACTION.value
    source: Optional[str] = None
    last_verified: Optional[str] = None
    is_simulated: Optional[bool] = None
    limitation_note: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
