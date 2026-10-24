"""
Person B — resource matching.

Takes a COMPLETE StructuredRequest (all four fields gathered) and the verified
resource dataset, and returns a MatchResult: the nearest available place that
serves the requested category and can take the group size.

Core principles:
  - NEVER invent availability. Match only against sourced records that serve
    the category, are not closed, and have capacity >= people_count.
  - Medicine category OR high urgency -> coordinator review (no auto-dispatch).
  - If nothing suitable, return matched=False with an honest limitation_note.
  - Flag stale records (older than STALE_HOURS) so the coordinator sees it.
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone

from schema import (
    StructuredRequest, Resource, MatchResult,
    Category, Urgency, ActionType,
)


STALE_HOURS = 24
DATA_PATH = os.path.join(os.path.dirname(__file__), "resources.json")


def load_resources(path: str = DATA_PATH) -> list[Resource]:
    with open(path) as f:
        data = json.load(f)
    return [Resource(**r) for r in data["resources"]]


def match_request(req: StructuredRequest, resources: list[Resource]) -> MatchResult:
    """Decide the next action for a COMPLETE structured request."""

    # Guard: matching should only run on complete requests.
    if not req.is_complete():
        return MatchResult(
            phone=req.phone,
            matched=False,
            action=ActionType.FOLLOW_UP.value,
            reason="Request incomplete: still missing " + ", ".join(req.missing_fields()),
        )

    # Medicine OR high urgency -> human review, never auto-dispatch.
    if req.category == Category.MEDICINE.value or req.urgency == Urgency.HIGH.value:
        reason = (f"Category '{req.category}', urgency '{req.urgency}' requires "
                  f"coordinator review before any dispatch.")
        if req.category == Category.MEDICINE.value:
            mode = "delivery" if req.delivery_mode == "deliver" else "collection"
            reason += f" Requester needs {mode}."
        return MatchResult(
            phone=req.phone,
            matched=False,
            action=ActionType.REVIEW_QUEUE.value,
            reason=reason,
            limitation_note="Flagged for human review. No delivery is confirmed until a coordinator accepts it.",
        )

    # Normal path: places that serve the category, are open/limited, with capacity.
    need = req.people_count or 1
    candidates = [
        r for r in resources
        if req.category in r.categories
        and r.operating_status != "closed"
        and r.capacity >= need
    ]

    if not candidates:
        return MatchResult(
            phone=req.phone,
            matched=False,
            action=ActionType.NO_ACTION.value,
            reason=(f"No open verified place serves '{req.category}' with capacity "
                    f"for {need} right now."),
            limitation_note="No suitable match from current verified records. Flagged for coordinator attention.",
        )

    # Rank: closest first (when coords exist), then most spare capacity.
    def score(r: Resource):
        dist = _distance_km(req, r)
        return (dist if dist is not None else 9999, -r.capacity)

    candidates.sort(key=score)
    best = candidates[0]

    note = None
    if _is_stale(best.last_verified):
        note = (f"Record last verified {best.last_verified} "
                f"(older than {STALE_HOURS}h) — confirm before relying on it.")

    reason = (f"{best.name} is {best.operating_status}, serves '{req.category}', "
              f"and can take {best.capacity} (you need {need}).")
    dist = _distance_km(req, best)
    if dist is not None:
        reason += f" ~{dist:.1f} km away."

    return MatchResult(
        phone=req.phone,
        matched=True,
        resource_id=best.id,
        resource_name=best.name,
        reason=reason,
        action=ActionType.DIRECT_TO_LOCATION.value,
        source=best.source,
        last_verified=best.last_verified,
        is_simulated=best.is_simulated,
        limitation_note=note,
    )


def _is_stale(last_verified: str) -> bool:
    try:
        ts = datetime.fromisoformat(last_verified.replace("Z", "+00:00"))
    except ValueError:
        return True
    age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    return age_hours > STALE_HOURS


def _distance_km(req: StructuredRequest, r: Resource) -> float | None:
    """User address is free text; geocoding is a backend concern. Returns None
    unless the request later carries coordinates."""
    user_lat = getattr(req, "lat", None)
    user_lon = getattr(req, "lon", None)
    if user_lat is None or user_lon is None or r.lat is None or r.lon is None:
        return None
    return _haversine(user_lat, user_lon, r.lat, r.lon)


def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
