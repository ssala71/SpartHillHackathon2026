"""Data models for Person B.

Two kinds of models live here:

1. The *input* Person B receives from Person A: ``ExtractionResult`` and its
   nested parts. Person B treats this as untrusted AI interpretation — it is
   used only to decide WHAT to look for, never as a source of resource facts.

2. The *resource facts* Person B owns: ``Resource``, ``InventoryItem``,
   ``OperatingHours``. These come from a sourced store and are the only thing
   allowed to appear in a match result.

Plain dataclasses are used so the package has no third-party dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Input from Person A (AI interpretation — never a source of resource facts)
# ---------------------------------------------------------------------------

class Urgency(str, Enum):
    """The ONLY urgency levels in the system — matches the shared data contract
    and the Bedrock extraction output. There is deliberately no separate
    "medical" level: a medical concern is expressed as HIGH urgency plus
    ``requires_human_review``."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Need:
    """A single requested resource category extracted from the message."""

    category: str  # water | food | shelter | medical | baby_formula | power | hygiene | other
    raw_text: str = ""
    quantity: Optional[float] = None


@dataclass
class ExtractedLocation:
    text: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    confidence: float = 0.0


@dataclass
class ExtractionResult:
    """What Person A hands to Person B. Matching reads this; it never trusts it
    as a source of resource availability."""

    needs: list[Need] = field(default_factory=list)
    location: ExtractedLocation = field(default_factory=ExtractedLocation)
    people_count: Optional[int] = None
    urgency: str = Urgency.LOW.value          # one of low | medium | high
    requires_human_review: bool = False       # set true for medical/danger cases
    model_notes: Optional[str] = None

    def has_location(self) -> bool:
        loc = self.location
        return loc.lat is not None and loc.lon is not None

    def need_categories(self) -> list[str]:
        return [n.category for n in self.needs]

    def is_high_urgency(self) -> bool:
        return self.urgency == Urgency.HIGH.value

    def needs_review(self) -> bool:
        """A request goes to human delivery review when it is high urgency OR
        when Person A flagged it (medical device, medication, injury, immediate
        danger, serious health concern all map to high + this flag)."""
        return self.is_high_urgency() or self.requires_human_review


# ---------------------------------------------------------------------------
# Resource facts owned by Person B (the ONLY valid source of a match)
# ---------------------------------------------------------------------------

@dataclass
class InventoryItem:
    available: int
    unit: str
    updated_at: str  # ISO-8601

    def in_stock(self) -> bool:
        return self.available > 0


@dataclass
class OperatingHours:
    day: str          # mon | tue | wed | thu | fri | sat | sun
    open: str         # "HH:MM"
    close: str        # "HH:MM"

    def covers_time_on_day(self, t: time) -> bool:
        """True if time `t` falls inside this entry's window on its own day.
        For overnight entries (e.g. 22:00-02:00) this means 22:00 onward."""
        o = _parse_hhmm(self.open)
        c = _parse_hhmm(self.close)
        if o <= c:
            return o <= t <= c
        return t >= o

    def covers_after_midnight(self, t: time) -> bool:
        """True if time `t` falls in the tail of an overnight entry, i.e. the
        part that continues into the following day (up to the close time)."""
        o = _parse_hhmm(self.open)
        c = _parse_hhmm(self.close)
        return o > c and t <= c


@dataclass
class Location:
    lat: float
    lon: float
    address: str


@dataclass
class Resource:
    resource_id: str
    name: str
    verified: bool
    status: str                       # open | closed | full
    location: Location
    operating_hours: list[OperatingHours]
    inventory: dict[str, InventoryItem]
    handles_medical: bool = False
    verified_by: Optional[str] = None
    last_verified_at: Optional[str] = None  # ISO-8601, "source" provenance
    source: str = "unknown"                 # where this record came from
    simulated: bool = False                 # TRUE for demo/fake data
    contact: dict = field(default_factory=dict)

    # --- eligibility helpers (mirror the spec's matching rules) ---

    def is_open_at(self, when: datetime) -> bool:
        if self.status != "open":
            return False
        t = when.time()
        today = _DAYS[when.weekday()]
        yesterday = _DAYS[(when.weekday() - 1) % 7]
        return any(
            (h.day == today and h.covers_time_on_day(t))
            or (h.day == yesterday and h.covers_after_midnight(t))
            for h in self.operating_hours
        )

    def available_for(self, category: str) -> int:
        item = self.inventory.get(category)
        return item.available if item else 0

    def is_eligible(self, category: str, when: datetime) -> bool:
        """A record is eligible for normal matching only when verified, open,
        in operating hours, and holding stock of the requested category."""
        return (
            self.verified
            and self.is_open_at(when)
            and self.available_for(category) > 0
        )


_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _parse_hhmm(value: str) -> time:
    hh, mm = value.split(":")
    return time(hour=int(hh), minute=int(mm))
