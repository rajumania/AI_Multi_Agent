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



def test_generate_response_plan_workflow(client):
    """Test generating a structured response plan combining incident, agents, and MCP resources."""
    # 1. Create Incident
    create_res = client.post("/api/v1/incidents", json={
        "description": "Smoke reported in Chemistry Lab 3rd floor. Possible flammable material hazard.",
        "location": "Science Hub",
        "incident_type": "fire",
        "severity": "high",
        "injured_count": None
    })
    assert create_res.status_code == 201
    inc_data = create_res.json()
    inc_id = inc_data["incident_id"]

    # 2. Generate Response Plan
    plan_res = client.post(f"/api/v1/response-plans/generate/{inc_id}")
    assert plan_res.status_code == 201
    plan_data = plan_res.json()

    assert plan_data["incident_id"] == inc_id
    assert "plan_id" in plan_data
    assert plan_data["plan_id"].startswith("PLAN-")
    assert plan_data["severity"] == "high"
    assert len(plan_data["recommended_actions"]) > 0
    assert len(plan_data["allocated_resources"]) > 0
    assert plan_data["requires_approval"] is True
    assert plan_data["approval_status"] == "pending"


def test_approve_response_plan(client):
    """Test human commander approving a response plan."""
    # Create incident & generate plan
    create_res = client.post("/api/v1/incidents", json={
        "description": "Crowd congestion near East Gate exit.",
        "location": "East Gate",
        "incident_type": "crowd",
        "severity": "medium",
        "injured_count": 0
    })
    inc_id = create_res.json()["incident_id"]
    plan_res = client.post(f"/api/v1/response-plans/generate/{inc_id}")
    plan_id = plan_res.json()["plan_id"]

    # Approve plan
    approval_res = client.post(f"/api/v1/approvals/{plan_id}/decide", json={
        "decision": "approve",
        "operator_name": "Chief Safety Officer Sarah",
        "notes": "Verified situation on CCTV. Authorize dispatch immediately."
    })
    assert approval_res.status_code == 200
    approved_data = approval_res.json()
    assert approved_data["approval_status"] == "approved"
    assert approved_data["approved_by"] == "Chief Safety Officer Sarah"
    assert "CCTV" in approved_data["approval_notes"]

    # Verify incident status updated
    inc_check = client.get(f"/api/v1/incidents/{inc_id}")
    assert inc_check.json()["status"] == "approved"


def test_reject_response_plan(client):
    """Test human commander rejecting a response plan."""
    create_res = client.post("/api/v1/incidents", json={
        "description": "Minor water tap leak in ground floor restroom.",
        "location": "Administrative Building",
        "incident_type": "facility",
        "severity": "low",
        "injured_count": 0
    })
    inc_id = create_res.json()["incident_id"]
    plan_res = client.post(f"/api/v1/response-plans/generate/{inc_id}")
    plan_id = plan_res.json()["plan_id"]

    # Reject plan
    reject_res = client.post(f"/api/v1/approvals/{plan_id}/decide", json={
        "decision": "reject",
        "operator_name": "Commander David",
        "notes": "Routine maintenance ticket already opened. No emergency action needed."
    })
    assert reject_res.status_code == 200
    rejected_data = reject_res.json()
    assert rejected_data["approval_status"] == "rejected"
    assert rejected_data["approved_by"] == "Commander David"

    # Verify incident status updated
    inc_check = client.get(f"/api/v1/incidents/{inc_id}")
    assert inc_check.json()["status"] == "rejected"


def test_get_pending_approvals_list(client):
    """Test retrieving list of response plans awaiting approval."""
    # Create incident & plan
    create_res = client.post("/api/v1/incidents", json={
        "description": "Electrical sparking near transformer behind Library.",
        "location": "Central Library",
        "incident_type": "fire",
        "severity": "high",
        "injured_count": None
    })
    inc_id = create_res.json()["incident_id"]
    client.post(f"/api/v1/response-plans/generate/{inc_id}")

    pending_res = client.get("/api/v1/approvals/pending")
    assert pending_res.status_code == 200
    pending_list = pending_res.json()
    assert len(pending_list) >= 1
    assert all(p["approval_status"] == "pending" for p in pending_list)


def test_end_to_end_audit_trail(client):
    """Test complete audit trail recording across incident lifecycle."""
    create_res = client.post("/api/v1/incidents", json={
        "description": "Sudden localized power outage affecting West Block servers.",
        "location": "West Academic Block",
        "incident_type": "facility",
        "severity": "medium",
        "injured_count": 0
    })
    inc_id = create_res.json()["incident_id"]

    # Analyze
    client.post(f"/api/v1/incidents/{inc_id}/analyze")

    # Generate response plan
    plan_res = client.post(f"/api/v1/response-plans/generate/{inc_id}")
    plan_id = plan_res.json()["plan_id"]

    # Decide approval
    client.post(f"/api/v1/approvals/{plan_id}/decide", json={
        "decision": "approve",
        "operator_name": "Duty Officer Mark",
        "notes": "Generator backup confirmed."
    })

    # Fetch audit logs for this incident
    audit_res = client.get(f"/api/v1/activity/{inc_id}")
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) >= 3

    action_types = [l["action_type"] for l in logs]
    assert "incident_created" in action_types
    assert "ai_classification" in action_types
    assert "response_plan_generated" in action_types
    assert "approval_decision" in action_types
