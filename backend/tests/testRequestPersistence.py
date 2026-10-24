from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_request_is_created_with_hashed_person_id() -> None:
    response = client.post(
        "/api/requests",
        json={
            "source_phone": "+1 (408) 555-1212",
            "message": "We need bottled water.",
            "channel": "Frontend",
        },
    )

    assert response.status_code == 201
    request = response.json()["data"]
    assert len(request["person_id"]) == 64
    assert request["status"] == "Received"
    assert request["message"] == "We need bottled water."


def test_completed_requests_remain_in_default_list() -> None:
    response = client.get("/api/requests")

    assert response.status_code == 200
    assert response.json()["data"]["total"] >= 1


def test_admin_can_update_status_without_changing_original_message() -> None:
    created = client.post(
        "/api/requests",
        json={"source_phone": "+14085551213", "message": "We need milk."},
    ).json()["data"]
    admin_id = uuid4()

    response = client.patch(
        f"/api/requests/{created['id']}/status",
        json={"status": "Completed", "admin_user_id": str(admin_id)},
    )

    assert response.status_code == 200
    updated = response.json()["data"]
    assert updated["status"] == "Completed"
    assert updated["message"] == "We need milk."
    assert updated["status_updated_by_admin_id"] == str(admin_id)
