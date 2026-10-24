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


def test_bedrock_call_handles_reasoning_blocks_and_no_temperature(monkeypatch) -> None:
    """Sonnet 5.5 rejects `temperature` and returns a reasoning block first."""
    import sys
    from types import SimpleNamespace

    from botocore.exceptions import ClientError

    from app.services import ai_processing

    calls = []

    class FakeClient:
        def converse(self, **kwargs):
            calls.append(kwargs["inferenceConfig"])
            if "temperature" in kwargs["inferenceConfig"]:
                raise ClientError({"Error": {"Code": "ValidationException", "Message": "`temperature` is deprecated for this model."}}, "Converse")
            return {
                "output": {"message": {"content": [
                    {"reasoningContent": {"reasoningText": {"text": "thinking"}}},
                    {"text": '{"needs": ["water"], "urgency": "low", "location": "Tully Rd", "people_count": 2, "summary": "s"}'},
                ]}},
                "stopReason": "end_turn",
            }

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *a, **k: FakeClient()))
    _, result = ai_processing._bedrock_response(SimpleNamespace(message="water near Tully Rd, 2 of us"))

    assert len(calls) == 2 and "temperature" not in calls[1]
    assert result.needs == ["water"]
    assert result.missing_information == []


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
