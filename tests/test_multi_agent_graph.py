import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.graph.workflow import run_emergency_workflow
from backend.agents.security import security_agent
from backend.agents.medical import medical_agent
from backend.agents.transport import transport_agent
from backend.agents.communication import communication_agent


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_security_agent_evaluation():
    """Test Security Agent recommendations for high-severity fire incident."""
    res = security_agent.evaluate(
        incident_type="fire",
        severity="high",
        location="CSE Block",
        description="Thick smoke and flames observed on floor 2."
    )
    assert res["agent_name"] == "Security Agent"
    assert res["threat_level"] in ["high", "critical"]
    assert len(res["actions"]) >= 2
    assert any("perimeter" in a.lower() or "safety" in a.lower() for a in res["actions"])


def test_medical_agent_preserves_unknown_injured():
    """Test Medical Agent safety rule: does not hallucinate casualties when count is unknown."""
    res = medical_agent.evaluate(
        incident_type="fire",
        severity="high",
        location="CSE Block",
        description="Fire reported. Injuries unknown.",
        injured_count=None  # strictly null
    )
    assert res["agent_name"] == "Medical Agent"
    assert "precautionary" in res["casualty_assessment"].lower() or "unconfirmed" in res["casualty_assessment"].lower()
    assert any("standby" in a.lower() for a in res["actions"])


def test_medical_agent_confirmed_casualties():
    """Test Medical Agent deploys ambulances and alerts ER when casualties are confirmed."""
    res = medical_agent.evaluate(
        incident_type="accident",
        severity="critical",
        location="East Ring Road",
        description="Shuttle collision, 2 students injured.",
        injured_count=2
    )
    assert res["agent_name"] == "Medical Agent"
    assert res["recommended_ambulances"] >= 1
    assert res["triage_priority"] in ["urgent", "immediate"]
    assert res["medical_center_alert"] is True


def test_transport_agent_evaluation():
    """Test Transport Agent rerouting and evacuation recommendations."""
    res = transport_agent.evaluate(
        incident_type="fire",
        severity="high",
        location="CSE Block",
        description="Fire emergency requiring access lane clearance."
    )
    assert res["agent_name"] == "Transport Agent"
    assert res["route_status"] == "restricted"
    assert res["traffic_rerouting_active"] is True
    assert len(res["actions"]) >= 1


def test_communication_agent_evaluation():
    """Test Communication Agent drafting calibrated alerts."""
    res = communication_agent.evaluate(
        incident_type="fire",
        severity="high",
        location="CSE Block",
        description="Fire emergency at CSE block.",
        summary="Fire incident reported at CSE Block.",
        injured_count=None
    )
    assert res["agent_name"] == "Communication Agent"
    assert res["broadcast_priority"] in ["high", "urgent"]
    assert len(res["broadcast_channels"]) >= 2
    assert "CSE" in res["alert_headline"]


def test_langgraph_workflow_execution():
    """
    Test complete LangGraph multi-agent execution pipeline.
    START -> Supervisor -> Security -> Medical -> Transport -> Communication -> Synthesizer -> END
    """
    initial_state = {
        "incident_id": "TEST-INC-001",
        "description": "There is smoke and possible fire near the CSE block. I don't know whether anyone is injured.",
        "location": "CSE Block",
        "reported_by": "Campus Watch",
        "audit_trail": []
    }

    final_state = run_emergency_workflow(initial_state)

    # 1. State assertions
    assert final_state["incident_type"] == "fire"
    assert final_state["severity"] in ["high", "critical"]
    assert final_state["injured_count"] is None  # Safety: Preserved as null!
    assert final_state["execution_status"] == "orchestrated"

    # 2. Agent result assertions
    assert final_state["security_result"] is not None
    assert final_state["medical_result"] is not None
    assert final_state["transport_result"] is not None
    assert final_state["communication_result"] is not None

    # 3. Synthesizer assertions
    assert len(final_state["all_recommendations"]) >= 4
    assert len(final_state["audit_trail"]) >= 5


def test_api_orchestrate_incident(client):
    """
    Test POST /api/v1/incidents/{incident_id}/orchestrate endpoint.
    """
    # 1. Create reported incident
    create_payload = {
        "description": "Flash electrical fire in CSE Block server room with dense smoke.",
        "location": "CSE Block",
        "incident_type": "unknown",
        "severity": "unknown",
        "injured_count": None,
        "evidence_source": "facilities"
    }
    create_res = client.post("/api/v1/incidents", json=create_payload)
    assert create_res.status_code == 201
    incident_id = create_res.json()["incident_id"]

    # 2. Trigger LangGraph Orchestration
    orch_res = client.post(f"/api/v1/incidents/{incident_id}/orchestrate")
    assert orch_res.status_code == 200
    data = orch_res.json()

    # Check updated incident record
    incident = data["incident"]
    assert incident["incident_id"] == incident_id
    assert incident["status"] == "response_planning"
    assert incident["incident_type"] == "fire"
    assert incident["injured_count"] is None

    # Check specialized agent outputs
    assert data["security_result"] is not None
    assert data["medical_result"] is not None
    assert data["transport_result"] is not None
    assert data["communication_result"] is not None
    assert len(data["all_recommendations"]) > 0
    assert len(data["audit_trail"]) > 0
    assert data["execution_status"] == "orchestrated"
