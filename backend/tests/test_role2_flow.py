"""Role 2 end-to-end: Bedrock result -> geocoding -> matching -> next action.

Covers the demo checklist items owned by Role 2: normal match, medicine review
with deliver/collect, one combined follow-up, honest no-match, inventory change
altering the result, and follow-up replies merging into the first message.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.schemas.requests import RequestStatus
from app.db.base import Base
from app.db.models import ProcessingAttempt, Request, StoredAIResult
from app.resource_matching.adapter import build_follow_up, merge_follow_up, normalize_needs
from app.resource_matching.matcher import Matcher
from app.resource_matching.models import InventoryItem
from app.resource_matching.store import ResourceStore
from app.services import ai_processing
from app.services.geocoding import GAZETTEER_SOURCE, geocode
from app.services.request_matching import build_match_result

MONDAY_NOON = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
TULLY = geocode("near Tully Road")


def ai_result(**overrides):
    """A stored AI result with every field present (override per test)."""
    base = dict(
        needs=["water"],
        urgency="low",
        location="near Tully Road",
        latitude=TULLY.latitude,
        longitude=TULLY.longitude,
        location_source=TULLY.source,
        people_count=3,
        household_size=None,
        medical_concern=False,
        delivery_mode=None,
        missing_information=[],
        needs_review=False,
        summary="test",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def matcher():
    return Matcher(ResourceStore.from_json())


def decide(result, matcher):
    return build_match_result(uuid4(), result, matcher=matcher, when=MONDAY_NOON)


# --- geocoding -------------------------------------------------------------

def test_text_address_is_geocoded_to_coordinates():
    assert TULLY is not None
    assert TULLY.source == GAZETTEER_SOURCE
    assert geocode("Story and King") .label == "Story Rd & King Rd"


def test_unknown_location_is_not_guessed():
    assert geocode("somewhere downtown") is None
    assert geocode(None) is None


# --- normal matching -------------------------------------------------------

def test_normal_request_is_directed_to_nearest_verified_place(matcher):
    match = decide(ai_result(), matcher)
    assert match.action.value == "direct_to_location"
    assert match.matched is True
    assert match.needs_review is False
    assert match.resource.resource_id == "res-0001"  # not unverified res-0003 or closed res-0004
    assert match.resource.source == "demo_seed"
    assert match.resource.simulated is True
    assert match.resource.distance_km > 0


def test_need_synonyms_map_to_inventory_categories():
    assert normalize_needs(["Medicine", "charging", "formula", "Water", "water"]) == [
        "medical", "power", "baby_formula", "water",
    ]


def test_inventory_update_changes_the_match():
    store = ResourceStore.from_json()
    store.get("res-0001").inventory["water"] = InventoryItem(available=0, unit="liters", updated_at="2026-10-23T10:00:00Z")
    match = decide(ai_result(), Matcher(store))
    assert match.matched is True
    assert match.resource.resource_id == "res-0002"  # next nearest verified place with water


def test_opening_hours_use_pacific_time(matcher):
    # 18:30 Monday in San Jose is 01:30 Tuesday UTC. Tully (08:00-20:00) is
    # open locally, so it must win over the 24-hour shelter farther away.
    from zoneinfo import ZoneInfo

    evening = datetime(2026, 10, 19, 18, 30, tzinfo=ZoneInfo("America/Los_Angeles"))
    match = build_match_result(uuid4(), ai_result(), matcher=matcher, when=evening)
    assert match.resource.resource_id == "res-0001"


def test_out_of_stock_category_is_an_honest_no_match(matcher):
    match = decide(ai_result(needs=["baby_formula"]), matcher)
    assert match.action.value == "no_match"
    assert match.matched is False
    assert match.resource is None
    assert match.needs_review is True


# --- medicine and urgency --------------------------------------------------

def test_medicine_delivery_goes_to_coordinator_with_suggestion(matcher):
    match = decide(ai_result(needs=["medicine"], medical_concern=True, urgency="high", delivery_mode="deliver"), matcher)
    assert match.action.value == "coordinator_review"
    assert match.matched is False
    assert match.needs_review is True
    assert match.delivery_mode.value == "deliver"
    assert "delivery" in match.reason
    assert match.resource.resource_id == "res-0005"  # suggestion for the coordinator only
    assert "No resource or delivery is confirmed" in match.disclaimer


def test_low_urgency_medicine_still_reviewed_with_collect(matcher):
    match = decide(ai_result(needs=["medical"], medical_concern=True, urgency="low", delivery_mode="collect"), matcher)
    assert match.action.value == "coordinator_review"
    assert "collect" in match.reason


def test_high_urgency_non_medical_goes_to_review(matcher):
    match = decide(ai_result(urgency="high"), matcher)
    assert match.action.value == "coordinator_review"
    assert match.delivery_mode is None


# --- one combined follow-up ------------------------------------------------

def test_medicine_without_delivery_mode_asks_only_for_it(matcher):
    match = decide(ai_result(needs=["medical"], medical_concern=True, urgency="high"), matcher)
    assert match.action.value == "follow_up"
    assert match.missing_fields == ["delivery_mode"]
    assert match.needs_review is True  # still visible to coordinators while waiting
    assert "deliver or collect" in match.follow_up_message


def test_all_missing_fields_are_asked_in_one_message(matcher):
    match = decide(
        ai_result(location="somewhere", latitude=None, longitude=None, people_count=None),
        matcher,
    )
    assert match.action.value == "follow_up"
    assert match.missing_fields == ["location", "people_count"]
    assert match.follow_up_message.count("please reply") == 1
    assert "cross street" in match.follow_up_message
    assert "how many people" in match.follow_up_message


def test_food_requests_never_ask_delivery_mode(matcher):
    match = decide(ai_result(needs=["food"], people_count=None), matcher)
    assert "delivery_mode" not in match.missing_fields


def test_no_follow_up_when_nothing_is_missing():
    assert build_follow_up([]) is None


def test_follow_up_reply_fills_gaps_without_downgrading():
    first = {"needs": ["medical"], "urgency": "high", "location": None, "people_count": None,
             "medical_concern": True, "delivery_mode": None, "missing_information": ["location", "people_count", "delivery_mode"]}
    reply = {"needs": [], "urgency": "low", "location": "Tully Rd", "people_count": 2,
             "medical_concern": False, "delivery_mode": "deliver", "missing_information": ["needs"]}
    merged = merge_follow_up(first, reply)
    assert merged["needs"] == ["medical"]
    assert merged["urgency"] == "high"
    assert merged["location"] == "Tully Rd"
    assert merged["people_count"] == 2
    assert merged["delivery_mode"] == "deliver"
    assert merged["medical_concern"] is True
    assert merged["missing_information"] == []


# --- full backend flow (mock Bedrock) --------------------------------------

@pytest.fixture
def session_factory(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(ai_processing, "create_session_factory", lambda *args, **kwargs: factory)
    monkeypatch.setattr(ai_processing.settings, "bedrock_enabled", False)
    return factory


def _new_attempt(factory, message):
    with factory() as db:
        request = Request(person_id="0" * 64, source_phone="+15550001", message=message)
        db.add(request)
        db.flush()
        attempt = ProcessingAttempt(request_id=request.id, attempt_number=1, status="Processing", model_id="mock", is_active=True)
        db.add(attempt)
        db.commit()
        return request.id, attempt.id


def test_processing_stores_coordinates_and_flags_medicine(session_factory):
    request_id, attempt_id = _new_attempt(session_factory, "I need insulin near Tully Rd, 2 of us, please deliver")
    ai_processing.process_attempt(attempt_id)

    with session_factory() as db:
        stored = db.scalar(select(StoredAIResult).where(StoredAIResult.request_id == request_id))
        request = db.get(Request, request_id)
        assert stored.needs == ["medical"]
        assert stored.urgency.value == "high"
        assert stored.delivery_mode == "deliver"
        assert stored.latitude == pytest.approx(TULLY.latitude)
        assert stored.location_source == GAZETTEER_SOURCE
        assert request.status is RequestStatus.NEEDS_REVIEW
        assert request.message == "I need insulin near Tully Rd, 2 of us, please deliver"  # original kept


def test_bedrock_failure_is_saved_for_retry(session_factory, monkeypatch):
    def boom(_request):
        raise RuntimeError("Bedrock unavailable")

    monkeypatch.setattr(ai_processing, "_process", boom)
    request_id, attempt_id = _new_attempt(session_factory, "we need water near Tully Rd, 3 people")
    ai_processing.process_attempt(attempt_id)

    with session_factory() as db:
        attempt = db.get(ProcessingAttempt, attempt_id)
        assert attempt.status.value == "Failed"
        assert "Bedrock unavailable" in attempt.error_message
        assert attempt.is_active is False
        assert db.get(Request, request_id).status is RequestStatus.NEEDS_REVIEW
