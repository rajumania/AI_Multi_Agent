import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database.database import SessionLocal
from backend.database.seed import reset_seed_resources


@pytest.fixture
def client():
    db = SessionLocal()
    try:
        reset_seed_resources(db)
    finally:
        db.close()
    with TestClient(app) as c:
        yield c
    db2 = SessionLocal()
    try:
        reset_seed_resources(db2)
    finally:
        db2.close()


def test_resources_have_valid_spatial_coordinates(client):
    """Verify all seeded campus emergency assets have accurate GPS coordinates."""
    res = client.get("/api/v1/resources")
    assert res.status_code == 200
    resources = res.json()
    assert len(resources) >= 12

    for r in resources:
        assert r["latitude"] is not None
        assert r["longitude"] is not None
        # Campus GPS bounding box check (Hyderabad / Campus vicinity)
        assert 17.0 <= r["latitude"] <= 18.0
        assert 78.0 <= r["longitude"] <= 79.0


def test_spatial_query_by_resource_type(client):
    """Verify spatial queries for specific resource categories (e.g. ambulances, security)."""
    amb_res = client.get("/api/v1/resources?type=ambulance")
    assert amb_res.status_code == 200
    ambulances = amb_res.json()
    assert len(ambulances) >= 2
    assert all(a["resource_type"] == "ambulance" for a in ambulances)
    assert all(a["latitude"] > 0 and a["longitude"] > 0 for a in ambulances)

    sec_res = client.get("/api/v1/resources?type=security")
    assert sec_res.status_code == 200
    security = sec_res.json()
    assert len(security) >= 3
    assert all(s["resource_type"] == "security" for s in security)


def test_incident_map_spatial_payload(client):
    """Verify incident intake returns valid location name for spatial map plotting."""
    create_res = client.post("/api/v1/incidents", json={
        "description": "Hazardous spill near Science Hub chemical stores.",
        "location": "Science Hub",
        "incident_type": "facility",
        "severity": "high",
        "injured_count": 0
    })
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["location"] == "Science Hub"
    assert "incident_id" in data
