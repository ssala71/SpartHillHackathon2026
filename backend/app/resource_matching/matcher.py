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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .models import ExtractionResult, Resource
from .store import ResourceStore


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

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
class MatchResult:
    outcome: str                         # "matched" | "no_match"
    match: Optional[Match] = None
    no_match_reason: Optional[str] = None
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
                outcome="no_match",
                no_match_reason="no_needs_in_request",
                disclaimer=_DISCLAIMER,
            )
        if not extraction.has_location():
            return MatchResult(
                outcome="no_match",
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
                outcome="no_match",
                no_match_reason="no_verified_open_in_stock_resource",
                considered_count=0,
                disclaimer=_DISCLAIMER,
            )

        # 3. Rank: nearest, then most needs covered, then most recently verified.
        candidates.sort(
            key=lambda c: (c[2], -len(c[1]), _verified_sort_key(c[0]))
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
            outcome="matched",
            match=match,
            considered_count=considered,
            disclaimer=_DISCLAIMER,
        )


_DISCLAIMER = (
    "Match is informational and sourced from current records; it is not a "
    "delivery confirmation."
)


def _verified_sort_key(res: Resource) -> str:
    # Most recent last_verified_at first → invert by returning negated ordinal.
    # Simpler: sort descending means we want larger timestamp first, so we
    # return a value that sorts ascending for "more recent". We use the raw
    # string reversed via a sentinel for None.
    return "" if res.last_verified_at is None else _invert(res.last_verified_at)


def _invert(s: str) -> str:
    # ISO-8601 strings sort lexicographically; to get "most recent first" under
    # an ascending sort, invert each char. Cheap and dependency-free.
    return "".join(chr(0x10FFFF - ord(ch)) if ord(ch) < 0x10FFFF else ch for ch in s)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
