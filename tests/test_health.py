import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.models.incident import IncidentCreate, IncidentType, SeverityLevel


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["service"] == "AITAM Disaster Response AI"
    assert "seeded_resources" in data
    assert data["seeded_resources"] > 0
    assert "timestamp" in data


def test_incident_model_null_preservation():
    """Verify safety rule: unknown injured count remains null, not converted to 0."""
    incident_unknown = IncidentCreate(
        description="Smoke observed near CSE building",
        location="CSE Block",
        incident_type=IncidentType.FIRE,
        severity=SeverityLevel.HIGH,
        injured_count=None
    )
    assert incident_unknown.injured_count is None

    # Test string "unknown" string parsing to None
    incident_str_unknown = IncidentCreate(
        description="Report with unknown injuries",
        location="North Gate",
        injured_count="unknown"  # type: ignore
    )
    assert incident_str_unknown.injured_count is None

    # When explicitly 0, it should be 0
    incident_zero = IncidentCreate(
        description="Minor leak, no injuries",
        location="Lab 3",
        injured_count=0
    )
    assert incident_zero.injured_count == 0
