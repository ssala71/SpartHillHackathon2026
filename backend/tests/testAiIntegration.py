from fastapi.testclient import TestClient

from app.api.schemas.ai import AIProcessingResult
from app.main import app


client = TestClient(app)


def test_ai_result_contract_validates() -> None:
    result = AIProcessingResult(
        needs=["Water"],
        urgency="Normal",
        location="San Jose",
        missing_information=[],
        needs_review=True,
        summary="Water request requires review.",
    )

    assert result.needs == ["Water"]
    assert result.needs_review is True


def test_matching_is_not_automatic_before_role_two_logic_exists() -> None:
    created = client.post(
        "/api/requests",
        json={"source_phone": "+14085551214", "message": "We need food."},
    ).json()["data"]

    response = client.get(f"/api/requests/{created['id']}/match")

    assert response.status_code == 200
    match = response.json()["data"]
    assert match["matched"] is False
    assert match["needs_review"] is True
