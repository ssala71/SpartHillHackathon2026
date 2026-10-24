"""Matcher — turns an extracted request into a sourced match or an explicit
no-match.

Rules enforced here (from the spec, Person B's half):
  * Only verified + open + in-hours + in-stock resources are candidates.
  * The nearest candidate wins; ties break on "covers most needs", then on most
    recently verified.
  * Every field in the returned match is copied from the resource record — the
    matcher never invents a name, location, phone, or availability.
  * When nothing qualifies, an explicit no_match with a reason is returned.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .models import ExtractionResult, Resource
from .store import ResourceStore


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

# The three possible outcomes of the matcher.
OUTCOME_MATCHED = "matched"
OUTCOME_NO_MATCH = "no_match"
OUTCOME_DELIVERY_REVIEW = "needs_delivery_review"


@dataclass
class Match:
    resource_id: str
    name: str
    distance_km: float
    matched_needs: list[str]
    address: str
    lat: float
    lon: float
    contact: dict
    # provenance — "return the match, its source, and a short reason"
    source: str
    last_verified_at: Optional[str]
    simulated: bool
    selection_reason: str


@dataclass
class DeliveryReview:
    """Returned for high-urgency / human-review requests instead of a direct
    match. The system never promises a resource here — a coordinator decides."""

    urgency: str
    reason: str
    needs: list[str]
    people_count: Optional[int]


@dataclass
class MatchResult:
    outcome: str                         # matched | no_match | needs_delivery_review
    match: Optional[Match] = None
    no_match_reason: Optional[str] = None
    delivery_review: Optional[DeliveryReview] = None
    considered_count: int = 0
    disclaimer: str = ""


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------

class Matcher:
    def __init__(self, store: ResourceStore):
        self._store = store

    def match(
        self,
        extraction: ExtractionResult,
        when: Optional[datetime] = None,
    ) -> MatchResult:
        when = when or datetime.now(timezone.utc)

        needs = extraction.need_categories()
        if not needs:
            return MatchResult(
                outcome=OUTCOME_NO_MATCH,
                no_match_reason="no_needs_in_request",
                disclaimer=_DISCLAIMER,
            )

        # High urgency OR a human-review flag (medical device, medication,
        # injury, immediate danger, serious health concern) must go to human
        # delivery review — never a direct automatic match. This check runs
        # before matching so we never promise a resource for these cases.
        if extraction.needs_review():
            return MatchResult(
                outcome=OUTCOME_DELIVERY_REVIEW,
                delivery_review=DeliveryReview(
                    urgency=extraction.urgency,
                    reason=_review_reason(extraction),
                    needs=needs,
                    people_count=extraction.people_count,
                ),
                disclaimer=_REVIEW_DISCLAIMER,
            )

        if not extraction.has_location():
            return MatchResult(
                outcome=OUTCOME_NO_MATCH,
                no_match_reason="no_usable_location",
                disclaimer=_DISCLAIMER,
            )

        req_lat = extraction.location.lat
        req_lon = extraction.location.lon

        # 1. Build candidate set from VERIFIED resources only.
        candidates: list[tuple[Resource, list[str], float]] = []
        for res in self._store.verified_only():
            covered = [c for c in needs if res.is_eligible(c, when)]
            if not covered:
                continue
            dist = _haversine_km(req_lat, req_lon, res.location.lat, res.location.lon)
            candidates.append((res, covered, dist))

        considered = len(candidates)

        # 2. No eligible verified/open/in-stock resource → explicit no_match.
        if not candidates:
            return MatchResult(
                outcome=OUTCOME_NO_MATCH,
                no_match_reason="no_verified_open_in_stock_resource",
                considered_count=0,
                disclaimer=_DISCLAIMER,
            )

        # 3. Rank: nearest, then most needs covered, then most recently verified.
        candidates.sort(
            key=lambda c: (c[2], -len(c[1]), -_verified_at(c[0]).timestamp())
        )
        best_res, best_covered, best_dist = candidates[0]

        reason = (
            f"Nearest verified, open resource ({best_dist:.1f} km) with available "
            f"{', '.join(best_covered)} in stock."
        )

        match = Match(
            resource_id=best_res.resource_id,
            name=best_res.name,
            distance_km=round(best_dist, 2),
            matched_needs=best_covered,
            address=best_res.location.address,
            lat=best_res.location.lat,
            lon=best_res.location.lon,
            contact=best_res.contact,
            source=best_res.source,
            last_verified_at=best_res.last_verified_at,
            simulated=best_res.simulated,
            selection_reason=reason,
        )
        return MatchResult(
            outcome=OUTCOME_MATCHED,
            match=match,
            considered_count=considered,
            disclaimer=_DISCLAIMER,
        )


_DISCLAIMER = (
    "Match is informational and sourced from current records; it is not a "
    "delivery confirmation."
)

_REVIEW_DISCLAIMER = (
    "Flagged for human delivery review. No resource or delivery is confirmed "
    "until a coordinator accepts it."
)


def _review_reason(extraction: ExtractionResult) -> str:
    if extraction.requires_human_review:
        return (
            "Request flagged as a medical device, medication, injury, immediate "
            "danger, or serious health concern — routed to a coordinator."
        )
    return "High-urgency request — routed to a coordinator for delivery review."


def _verified_at(res: Resource) -> datetime:
    """Parse last_verified_at for tie-breaking. Missing timestamps sort as oldest."""
    if res.last_verified_at is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(res.last_verified_at.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        # Assume UTC when no offset is given, so every machine sorts the same way.
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
