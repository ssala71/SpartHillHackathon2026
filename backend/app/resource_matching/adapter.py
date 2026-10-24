"""Adapter: the agreed mapping between Bedrock output and the matcher input.

Role 2 had three request shapes:
  1. Conversation prototype (AWS-Bedrock branch): category, address, urgency,
     people_count, delivery_mode.
  2. Matcher (this package): ``ExtractionResult`` with a list of needs,
     latitude/longitude, low/medium/high urgency, requires_human_review.
  3. Backend API: ``AIProcessingResult`` / ``StoredAIResult``.

The shared format is the backend ``AIProcessingResult``. This module converts
it (plus geocoded coordinates) into the matcher's ``ExtractionResult``, so the
matcher stays unchanged. Field mapping:

    AIProcessingResult.needs           -> Need(category) via normalize_need()
    AIProcessingResult.location (text) -> geocode() -> ExtractedLocation(lat, lon)
    AIProcessingResult.urgency         -> urgency (low | medium | high)
    AIProcessingResult.medical_concern -> requires_human_review
    AIProcessingResult.people_count    -> people_count
    AIProcessingResult.delivery_mode   -> used only for medicine requests

It also builds the single combined follow-up SMS from the conversation
prototype: every missing field is requested in ONE message.
"""

from __future__ import annotations

from typing import Any

from .models import ExtractedLocation, ExtractionResult, Need, Urgency

# Inventory categories the matcher understands (keys in resources.json).
CANONICAL_NEEDS = ("water", "food", "shelter", "medical", "baby_formula", "power", "hygiene", "other")

_NEED_SYNONYMS = {
    "medicine": "medical",
    "medication": "medical",
    "medications": "medical",
    "prescription": "medical",
    "insulin": "medical",
    "oxygen": "medical",
    "first aid": "medical",
    "charging": "power",
    "charge": "power",
    "electricity": "power",
    "battery": "power",
    "formula": "baby_formula",
    "baby food": "baby_formula",
    "baby supplies": "baby_formula",
    "baby_supplies": "baby_formula",
    "infant formula": "baby_formula",
    "drinking water": "water",
    "bottled water": "water",
    "liquids": "water",
    "meals": "food",
    "groceries": "food",
    "housing": "shelter",
    "place to stay": "shelter",
    "diapers": "hygiene",
    "toiletries": "hygiene",
}

# Field order and wording for the single combined follow-up message.
_FOLLOW_UP_PROMPTS = {
    "needs": "what you need (for example food, water, medicine, or shelter)",
    "location": "your location (a cross street or landmark)",
    "people_count": "how many people need help",
    "urgency": "how urgent it is (reply high, medium, or low)",
    "delivery_mode": "whether you need the medicine delivered or can collect it (reply deliver or collect)",
}
FOLLOW_UP_FIELDS = tuple(_FOLLOW_UP_PROMPTS)

_MISSING_ALIASES = {
    "need": "needs",
    "needs": "needs",
    "location": "location",
    "address": "location",
    "people": "people_count",
    "people_count": "people_count",
    "household_size": "people_count",
    "urgency": "urgency",
    "delivery_mode": "delivery_mode",
}


def normalize_need(raw: str) -> str:
    """Map a free-form need label to a canonical inventory category."""
    value = raw.strip().lower().replace("-", " ")
    if value in CANONICAL_NEEDS:
        return value
    if value.replace(" ", "_") in CANONICAL_NEEDS:
        return value.replace(" ", "_")
    return _NEED_SYNONYMS.get(value, "other")


def normalize_needs(raw_needs: list[str]) -> list[str]:
    seen: list[str] = []
    for raw in raw_needs:
        need = normalize_need(raw)
        if need not in seen:
            seen.append(need)
    return seen


def is_medicine_request(needs: list[str], medical_concern: bool) -> bool:
    return medical_concern or "medical" in normalize_needs(needs)


def to_extraction(
    *,
    needs: list[str],
    urgency: str,
    location_text: str | None,
    latitude: float | None,
    longitude: float | None,
    people_count: int | None,
    medical_concern: bool,
    summary: str | None = None,
) -> ExtractionResult:
    """Build the matcher's input from the shared request fields."""
    urgency_value = urgency.value if hasattr(urgency, "value") else str(urgency)
    if urgency_value not in {u.value for u in Urgency}:
        urgency_value = Urgency.LOW.value
    canonical = normalize_needs(needs)
    return ExtractionResult(
        needs=[Need(category=need, raw_text=need) for need in canonical],
        location=ExtractedLocation(
            text=location_text,
            lat=latitude,
            lon=longitude,
            confidence=1.0 if latitude is not None else 0.0,
        ),
        people_count=people_count,
        urgency=urgency_value,
        requires_human_review=is_medicine_request(needs, medical_concern),
        model_notes=summary,
    )


def missing_fields(
    *,
    needs: list[str],
    has_coordinates: bool,
    people_count: int | None,
    medical_concern: bool,
    delivery_mode: Any,
    reported_missing: list[str],
) -> list[str]:
    """Fields still needed before matching, in the follow-up message order.

    ``location`` counts as missing when there are no coordinates, because a
    text address that cannot be geocoded cannot be used to find the nearest
    place. ``delivery_mode`` is required only for medicine requests.
    """
    missing: set[str] = set()
    for item in reported_missing:
        key = _MISSING_ALIASES.get(str(item).strip().lower())
        if key:
            missing.add(key)
    if not needs:
        missing.add("needs")
    else:
        missing.discard("needs")
    if not has_coordinates:
        missing.add("location")
    else:
        missing.discard("location")
    if people_count is None:
        missing.add("people_count")
    else:
        missing.discard("people_count")
    if is_medicine_request(needs, medical_concern) and delivery_mode is None:
        missing.add("delivery_mode")
    else:
        missing.discard("delivery_mode")
    return [field for field in FOLLOW_UP_FIELDS if field in missing]


def build_follow_up(missing: list[str]) -> str | None:
    """One SMS asking for every missing field at once."""
    parts = [_FOLLOW_UP_PROMPTS[field] for field in FOLLOW_UP_FIELDS if field in missing]
    if not parts:
        return None
    if len(parts) == 1:
        body = parts[0]
    else:
        body = ", ".join(parts[:-1]) + ", and " + parts[-1]
    return f"To find help near you, please reply with {body}."


def merge_follow_up(earlier: dict[str, Any], later: dict[str, Any]) -> dict[str, Any]:
    """Combine an earlier extraction with the extraction of a follow-up reply.

    Only blank fields are filled, so a short reply ("2 of us, collect") cannot
    erase what the first message already said. Needs are unioned. Urgency takes
    the higher of the two levels so a request is never downgraded by a reply.
    The SMS endpoint calls this when a reply arrives from the same person.
    """
    merged = dict(earlier)
    for key in ("location", "latitude", "longitude", "location_source", "people_count", "household_size", "delivery_mode"):
        if merged.get(key) in (None, "") and later.get(key) not in (None, ""):
            merged[key] = later[key]
    merged["needs"] = normalize_needs(list(earlier.get("needs") or []) + list(later.get("needs") or []))
    merged["medical_concern"] = bool(earlier.get("medical_concern")) or bool(later.get("medical_concern"))
    order = {"low": 0, "medium": 1, "high": 2}
    first = _urgency_value(earlier.get("urgency"))
    second = _urgency_value(later.get("urgency"))
    merged["urgency"] = max(first, second, key=lambda value: order.get(value, 0))
    still_missing = set(earlier.get("missing_information") or []) & set(later.get("missing_information") or [])
    merged["missing_information"] = sorted(still_missing)
    return merged


def _urgency_value(value: Any) -> str:
    if value is None:
        return Urgency.LOW.value
    text = value.value if hasattr(value, "value") else str(value)
    return text if text in {u.value for u in Urgency} else Urgency.LOW.value
