"""Focused Phase 6 checks for the two real intake paths and their shared data."""

from backend.api.incidents import run_automatic_incident_pipeline
from backend.database.models import ResponsePlanDB


def test_community_report_enters_shared_disaster_pipeline(client, db_session):
    token = client.post("/api/v1/auth/user/login", json={"email": "community@aitam.local", "phone": "9000000000"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/api/v1/incidents", headers=headers, json={
        "incident_type": "weather",
        "disaster_type": "landslide",
        "description": "Landslide risk increasing near Nepal mountain route.",
        "location": "N-14 (DEMO/SIMULATION)",
        "zone_id": "DEMO-N14",
        "region_id": "DEMO-NEPAL-MOUNTAIN",
        "severity": "high",
        "injured_count": None,
        "evidence_source": "community_mobile",
        "image_url": "photo:route-evidence.jpg",
        "reported_by": "Community Reporter",
        "latitude": 28.21,
        "longitude": 84.02,
    })
    assert response.status_code == 201, response.text
    incident = response.json()
    assert incident["disaster_type"] == "landslide"
    assert incident["latitude"] == 28.21
    assert incident["image_url"] == "photo:route-evidence.jpg"

    # The test fixture disables automatic background work, so invoke the same
    # production callback explicitly and verify the common LangGraph boundary.
    run_automatic_incident_pipeline(incident["incident_id"])
    updated = client.get(f"/api/v1/incidents/{incident['incident_id']}", headers=headers)
    assert updated.status_code == 200
    assert updated.json()["status"] == "awaiting_approval"
    assert db_session.query(ResponsePlanDB).filter_by(incident_id=incident["incident_id"]).count() >= 1


def test_sensor_status_exposes_truthful_health_fields(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/sensors/status", headers=headers)
    assert response.status_code == 200
    for sensor in response.json():
        assert {"sensor_id", "value", "status", "threshold", "received_at"} <= set(sensor)
