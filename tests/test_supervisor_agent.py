import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.agents.supervisor import supervisor_agent
from backend.models.incident import IncidentType, SeverityLevel


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_supervisor_fire_unknown_injured():
    """
    Test Step 3 golden example:
    Input: "There is smoke and possible fire near the CSE block. I don't know whether anyone is injured."
    Must strictly preserve injured_count as None (null), classify as fire, high/critical severity, CSE Block location.
    """
    text = "There is smoke and possible fire near the CSE block. I don't know whether anyone is injured."
    result = supervisor_agent.analyze_incident(description=text)

    assert result.incident_type == IncidentType.FIRE
    assert result.severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]
    assert "CSE" in result.location
    assert result.injured_count is None  # CRITICAL SAFETY RULE: Must be None, NEVER 0!
    assert result.confidence >= 0.8
    assert "fire" in result.summary.lower()
    assert "security" in result.recommended_agents
    assert len(result.key_observations) > 0


def test_supervisor_medical_confirmed_injuries():
    """
    Test medical incident with confirmed 2 casualties.
    """
    text = "2 students collapsed during heatstroke at Sports Complex Arena. Need medical help immediately."
    result = supervisor_agent.analyze_incident(description=text)

    assert result.incident_type == IncidentType.MEDICAL
    assert result.injured_count == 2
    assert "Sports" in result.location or "Arena" in result.location
    assert "medical" in result.recommended_agents
    assert result.confidence >= 0.8


def test_supervisor_facility_confirmed_zero_injured():
    """
    Test facility leak with explicitly confirmed zero injuries.
    """
    text = "Major water pipe leak in Science Lab basement corridor. Confirmed no injuries reported."
    result = supervisor_agent.analyze_incident(description=text)

    assert result.incident_type == IncidentType.FACILITY
    assert result.injured_count == 0  # Confirmed explicitly no injuries
    assert result.severity in [SeverityLevel.LOW, SeverityLevel.MEDIUM]


def test_supervisor_security_incident():
    """
    Test security threat extraction.
    """
    text = "Suspicious intruder spotted attempting break-in at North Auditorium entrance."
    result = supervisor_agent.analyze_incident(description=text)

    assert result.incident_type == IncidentType.SECURITY
    assert "Auditorium" in result.location
    assert result.injured_count is None
    assert "security" in result.recommended_agents


def test_api_analyze_incident_by_id(client):
    """
    Test POST /api/v1/incidents/{incident_id}/analyze updates database and status to 'classified'.
    """
    # 1. Create reported incident with unconfirmed injuries
    create_payload = {
        "description": "Thick black smoke billowing from CSE block server room. Unknown if anyone trapped.",
        "incident_type": "unknown",
        "location": "CSE Block",
        "severity": "unknown",
        "injured_count": None,
        "evidence_source": "student_report"
    }
    create_res = client.post("/api/v1/incidents", json=create_payload)
    assert create_res.status_code == 201
    incident_id = create_res.json()["incident_id"]
    assert create_res.json()["status"] == "reported"

    # 2. Trigger Supervisor AI Agent analysis
    analyze_res = client.post(f"/api/v1/incidents/{incident_id}/analyze")
    assert analyze_res.status_code == 200
    data = analyze_res.json()

    # Check incident was updated in DB
    updated_inc = data["incident"]
    assert updated_inc["incident_id"] == incident_id
    assert updated_inc["status"] == "classified"
    assert updated_inc["incident_type"] == "fire"
    assert updated_inc["severity"] in ["high", "critical"]
    assert updated_inc["injured_count"] is None  # Preserved null
    assert updated_inc["summary"] is not None
    assert updated_inc["confidence"] is not None and updated_inc["confidence"] > 0.5

    # Check structured analysis payload
    analysis = data["analysis"]
    assert analysis["incident_type"] == "fire"
    assert "security" in analysis["recommended_agents"]


def test_api_analyze_raw_text(client):
    """
    Test POST /api/v1/incidents/analyze-raw endpoint.
    """
    payload = {
        "description": "Power blackout and elevator stoppage in Student Residence Quarters.",
        "location": "Student Residence",
        "incident_type": "unknown",
        "severity": "unknown",
        "injured_count": None
    }
    res = client.post("/api/v1/incidents/analyze-raw", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["incident_type"] == "facility"
    assert data["injured_count"] is None
    assert data["confidence"] >= 0.8
