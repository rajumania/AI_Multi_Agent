import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_create_incident_with_unknown_injured(client):
    """Test incident creation where injured count is unknown (null)."""
    payload = {
        "description": "Thick smoke emerging from second floor lab in CSE block.",
        "incident_type": "fire",
        "location": "CSE Block",
        "severity": "high",
        "injured_count": None,
        "evidence_source": "manual_report",
        "reported_by": "Security Officer"
    }
    response = client.post("/api/v1/incidents", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["incident_id"].startswith("INC-")
    assert data["description"] == payload["description"]
    assert data["incident_type"] == "fire"
    assert data["location"] == "CSE Block"
    assert data["severity"] == "high"
    assert data["injured_count"] is None  # Safety test: MUST be null, not 0!
    assert data["status"] == "reported"


def test_create_incident_with_confirmed_zero_injured(client):
    """Test incident creation where injured count is explicitly 0 (confirmed no injuries)."""
    payload = {
        "description": "Water pipe leak in basement corridor, no one harmed.",
        "incident_type": "facility",
        "location": "Engineering Lab Basement",
        "severity": "low",
        "injured_count": 0,
        "evidence_source": "facilities_staff"
    }
    response = client.post("/api/v1/incidents", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["injured_count"] == 0


def test_create_incident_with_confirmed_injuries(client):
    """Test incident creation with positive number of injured persons."""
    payload = {
        "description": "Lab chemistry spill resulting in minor chemical burns.",
        "incident_type": "medical",
        "location": "Chemistry Block Lab 4",
        "severity": "medium",
        "injured_count": 2,
        "evidence_source": "lab_assistant"
    }
    response = client.post("/api/v1/incidents", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["injured_count"] == 2


def test_list_incidents(client):
    """Test retrieving list of reported incidents."""
    response = client.get("/api/v1/incidents")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 3


def test_get_incident_by_id(client):
    """Test retrieving a single incident by ID and testing 404 for nonexistent ID."""
    # First create an incident
    payload = {
        "description": "Power fluctuation in server room.",
        "incident_type": "facility",
        "location": "Data Center",
        "severity": "medium"
    }
    create_res = client.post("/api/v1/incidents", json=payload)
    incident_id = create_res.json()["incident_id"]

    # Fetch by ID
    get_res = client.get(f"/api/v1/incidents/{incident_id}")
    assert get_res.status_code == 200
    assert get_res.json()["incident_id"] == incident_id

    # Non-existent ID
    not_found_res = client.get("/api/v1/incidents/INC-NONEXISTENT-999")
    assert not_found_res.status_code == 404
