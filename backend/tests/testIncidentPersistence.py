from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_incident_can_be_created() -> None:
    response = client.post(
        "/api/incidents",
        json={
            "name": "Power outage",
            "description": "Shelter coordination incident",
            "affected_area": "San Jose",
        },
    )

    assert response.status_code == 201
    assert response.json()["data"]["name"] == "Power outage"
    assert response.json()["data"]["status"] == "Draft"
