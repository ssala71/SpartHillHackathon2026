from datetime import date, datetime
from uuid import UUID

from app.api.schemas import (
    ApiError,
    ApiResponse,
    InventoryCategory,
    Incident,
    InventoryItem,
    Request,
    RequestCreate,
    RequestUrgency,
)


def test_records_have_pacific_timestamps() -> None:
    record = Incident(name="Power outage", affected_area="San Jose")

    assert isinstance(record.id, UUID)
    assert isinstance(record.created_at, datetime)
    assert isinstance(record.updated_at, datetime)
    assert record.created_at.tzinfo is not None
    assert record.created_at.utcoffset() is not None
    assert record.created_at.tzname() in {"PST", "PDT"}


def test_urgency_uses_low_medium_high() -> None:
    assert {u.value for u in RequestUrgency} == {"low", "medium", "high"}
    assert RequestCreate(source_phone="+14085551212", message="x").urgency is RequestUrgency.LOW


def test_urgency_accepts_any_case_and_legacy_values() -> None:
    # Lowercase/uppercase and the old Normal/Urgent/Medical labels still validate.
    cases = {"HIGH": "high", "Medium": "medium", "Normal": "low", "Urgent": "high", "medical": "high"}
    for raw, expected in cases.items():
        request = RequestCreate(source_phone="+14085551212", message="x", urgency=raw)
        assert request.urgency.value == expected


def test_contracts_validate_enum_values() -> None:
    request = RequestCreate(
        source_phone="+14085551212",
        message="We need water",
        urgency="high",
    )
    inventory = InventoryItem(
        resource_id="00000000-0000-0000-0000-000000000001",
        item_name="Water",
        quantity=10,
        unit="cases",
        category="Liquids",
        status="Available",
        expiration_date="2027-01-15",
    )

    assert request.urgency is RequestUrgency.HIGH
    assert inventory.status.value == "Available"
    assert inventory.category is InventoryCategory.LIQUIDS
    assert inventory.expiration_date == date(2027, 1, 15)


def test_json_response_envelope() -> None:
    response = ApiResponse[dict[str, str]](data={"status": "ok"})
    error = ApiResponse[None](error=ApiError(code="NOT_FOUND", message="Not found"))

    assert response.model_dump() == {"data": {"status": "ok"}, "error": None}
    assert error.error is not None
    assert error.error.code == "NOT_FOUND"
