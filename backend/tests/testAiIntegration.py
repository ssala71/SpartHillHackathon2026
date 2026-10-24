from fastapi.testclient import TestClient

from app.api.schemas.ai import AIProcessingResult
from app.main import app
from app.services.ai_processing import _mock_extract, _parse_model_json


client = TestClient(app)


def test_ai_result_contract_validates() -> None:
    result = AIProcessingResult(
        needs=["water"],
        urgency="low",
        location="San Jose",
        missing_information=[],
        needs_review=True,
        summary="Water request requires review.",
    )

    assert result.needs == ["water"]
    assert result.needs_review is True
    assert result.delivery_mode is None


def test_unprocessed_request_is_not_matched() -> None:
    created = client.post(
        "/api/requests",
        json={"source_phone": "+14085551214", "message": "We need food."},
    ).json()["data"]

    response = client.get(f"/api/requests/{created['id']}/match")

    assert response.status_code == 200
    match = response.json()["data"]
    assert match["matched"] is False
    assert match["needs_review"] is True
    assert match["action"] == "not_processed"


def test_model_json_inside_code_fence_is_parsed() -> None:
    text = 'Here you go:\n```json\n{"needs": ["water"], "urgency": "HIGH", "summary": "s"}\n```'
    result = _parse_model_json(text)
    assert result.urgency.value == "high"


def test_mock_extracts_medicine_and_delivery_mode() -> None:
    result = _mock_extract("I need insulin near Tully Rd, just me, please deliver")
    assert "medical" in result.needs
    assert result.medical_concern is True
    assert result.urgency.value == "high"
    assert result.delivery_mode.value == "deliver"
    assert result.people_count == 1
    assert result.location == "Tully Rd"
    assert result.missing_information == []


def test_mock_keeps_intersections_and_stops_before_needs() -> None:
    assert _mock_extract("I need medication near Story and King, just me").location == "Story and King"
    assert _mock_extract("3 people near Tully Rd need water").location == "Tully Rd"


def test_mock_reports_missing_fields() -> None:
    result = _mock_extract("we need water")
    assert result.needs == ["water"]
    assert set(result.missing_information) == {"location", "people_count"}
