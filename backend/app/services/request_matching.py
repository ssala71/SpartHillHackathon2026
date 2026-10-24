"""Connects a processed request to Role 2 resource matching.

Decision order (one place, so the API, SMS replies, and dashboard agree):

1. No validated AI result yet          -> not_processed
2. Required fields missing             -> follow_up, with ONE combined SMS
   (needs, a location we can geocode, people_count, and delivery_mode for
   medicine). High-urgency or medical requests are still flagged for review.
3. Medicine or high urgency            -> coordinator_review. The nearest
   verified, open, in-stock place is attached as a SUGGESTION for the
   coordinator; nothing is confirmed until a coordinator accepts it.
4. Otherwise run the matcher           -> direct_to_location or no_match

Inventory is checked per category (the matcher's rule): a place qualifies only
if it is verified, open now, and has stock of the requested category.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from functools import lru_cache
from uuid import UUID

from app.api.schemas.ai import MatchAction, MatchedResource, MatchResult
from app.api.schemas.common import now_pacific
from app.api.schemas.requests import DeliveryMode, RequestUrgency
from app.resource_matching import adapter
from app.resource_matching.matcher import OUTCOME_MATCHED, Matcher
from app.resource_matching.store import ResourceStore

_REVIEW_DISCLAIMER = (
    "Flagged for coordinator review. No resource or delivery is confirmed "
    "until a coordinator accepts it."
)


@lru_cache
def get_matcher() -> Matcher:
    """Matcher over the sourced resource records (JSON seed for the demo)."""
    return Matcher(ResourceStore.from_json())


def build_match_result(
    request_id: UUID,
    ai_result,
    matcher: Matcher | None = None,
    when: datetime | None = None,
) -> MatchResult:
    """Decide the next action for one request from its stored AI result."""
    if ai_result is None:
        return MatchResult(
            request_id=request_id,
            matched=False,
            needs_review=True,
            action=MatchAction.NOT_PROCESSED,
            reason="The request has not been processed by Bedrock yet.",
        )

    matcher = matcher or get_matcher()
    # Resource hours are local San Jose times, so compare in Pacific time.
    # (The matcher's own default is UTC, which shifts hours by 7-8 hours.)
    when = when or now_pacific()
    needs = list(ai_result.needs or [])
    medical = adapter.is_medicine_request(needs, bool(ai_result.medical_concern))
    urgency = RequestUrgency(ai_result.urgency)
    delivery_mode = DeliveryMode(ai_result.delivery_mode) if ai_result.delivery_mode else None
    has_coordinates = ai_result.latitude is not None and ai_result.longitude is not None
    review = medical or urgency is RequestUrgency.HIGH

    missing = adapter.missing_fields(
        needs=needs,
        has_coordinates=has_coordinates,
        people_count=ai_result.people_count,
        medical_concern=bool(ai_result.medical_concern),
        delivery_mode=delivery_mode,
        reported_missing=list(ai_result.missing_information or []),
    )
    if missing:
        return MatchResult(
            request_id=request_id,
            matched=False,
            needs_review=review,
            action=MatchAction.FOLLOW_UP,
            reason="Missing " + ", ".join(missing) + "; asking the person in one follow-up message.",
            follow_up_message=adapter.build_follow_up(missing),
            missing_fields=missing,
            delivery_mode=delivery_mode,
            location_source=ai_result.location_source,
            disclaimer=_REVIEW_DISCLAIMER if review else None,
        )

    extraction = adapter.to_extraction(
        needs=needs,
        urgency=urgency.value,
        location_text=ai_result.location,
        latitude=ai_result.latitude,
        longitude=ai_result.longitude,
        people_count=ai_result.people_count,
        medical_concern=bool(ai_result.medical_concern),
        summary=ai_result.summary,
    )

    if review:
        suggestion = _nearest_suggestion(matcher, extraction, when)
        if medical:
            mode = "delivery" if delivery_mode is DeliveryMode.DELIVER else "to collect it"
            reason = f"Medicine request ({urgency.value} urgency); the person needs {mode}. A coordinator must review."
        else:
            reason = "High-urgency request; a coordinator must review before any response is arranged."
        if suggestion is None:
            reason += " No verified, open place currently has this in stock."
        return MatchResult(
            request_id=request_id,
            matched=False,
            needs_review=True,
            action=MatchAction.COORDINATOR_REVIEW,
            reason=reason,
            resource=suggestion,
            delivery_mode=delivery_mode,
            location_source=ai_result.location_source,
            disclaimer=_REVIEW_DISCLAIMER,
        )

    result = matcher.match(extraction, when=when)
    if result.outcome == OUTCOME_MATCHED and result.match is not None:
        return MatchResult(
            request_id=request_id,
            matched=True,
            needs_review=False,
            action=MatchAction.DIRECT_TO_LOCATION,
            reason=result.match.selection_reason,
            resource=_to_matched_resource(result.match),
            location_source=ai_result.location_source,
            disclaimer=result.disclaimer,
        )

    return MatchResult(
        request_id=request_id,
        matched=False,
        needs_review=True,
        action=MatchAction.NO_MATCH,
        reason=_NO_MATCH_REASONS.get(result.no_match_reason or "", "No suitable verified resource was found."),
        location_source=ai_result.location_source,
        disclaimer="No match was invented. A coordinator has been flagged.",
    )


def _nearest_suggestion(matcher: Matcher, extraction, when: datetime | None) -> MatchedResource | None:
    """Run normal matching (review flags off) only to suggest a place to the coordinator."""
    probe = replace(extraction, urgency="low", requires_human_review=False)
    result = matcher.match(probe, when=when)
    if result.outcome == OUTCOME_MATCHED and result.match is not None:
        return _to_matched_resource(result.match)
    return None


def _to_matched_resource(match) -> MatchedResource:
    return MatchedResource(
        resource_id=match.resource_id,
        name=match.name,
        address=match.address,
        distance_km=match.distance_km,
        matched_needs=list(match.matched_needs),
        source=match.source,
        last_verified_at=match.last_verified_at,
        simulated=match.simulated,
    )


_NO_MATCH_REASONS = {
    "no_needs_in_request": "The request did not include a need we can match.",
    "no_usable_location": "The location could not be turned into coordinates.",
    "no_verified_open_in_stock_resource": "No verified, open place currently has the requested items in stock.",
}
