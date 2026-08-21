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



def test_execute_approved_plan_success(client):
    """Test full automated dispatch execution on an approved response plan."""
    # 1. Create incident
    create_res = client.post("/api/v1/incidents", json={
        "description": "Dense smoke observed near CSE building staircase. Occupants evacuating.",
        "location": "CSE Block",
        "incident_type": "fire",
        "severity": "high",
        "injured_count": None
    })
    inc_id = create_res.json()["incident_id"]

    # 2. Generate Response Plan
    plan_res = client.post(f"/api/v1/response-plans/generate/{inc_id}")
    plan_id = plan_res.json()["plan_id"]

    # 3. Approve Plan
    client.post(f"/api/v1/approvals/{plan_id}/decide", json={
        "decision": "approve",
        "operator_name": "Commander Alex",
        "notes": "Verified. Dispatch units immediately."
    })

    # 4. Execute Dispatch
    dispatch_res = client.post(f"/api/v1/dispatch/{plan_id}/execute")
    assert dispatch_res.status_code == 200
    dispatch_data = dispatch_res.json()

    assert dispatch_data["plan_id"] == plan_id
    assert dispatch_data["execution_status"] == "dispatched"
    assert len(dispatch_data["dispatched_resources"]) > 0
    assert len(dispatch_data["broadcast_alerts"]) >= 3

    # 5. Verify allocated resources are now marked 'busy' in DB
    for rid in dispatch_data["dispatched_resources"]:
        r_check = client.get(f"/api/v1/resources/{rid}")
        assert r_check.status_code == 200
        assert r_check.json()["availability_status"] == "busy"

    # 6. Verify Incident status updated to in_progress
    inc_check = client.get(f"/api/v1/incidents/{inc_id}")
    assert inc_check.json()["status"] == "in_progress"


def test_execute_unapproved_plan_fails(client):
    """Test that high-impact automated dispatch strictly fails on unapproved plans."""
    create_res = client.post("/api/v1/incidents", json={
        "description": "Water pipe leak in basement corridor.",
        "location": "Administrative Building",
        "incident_type": "facility",
        "severity": "low",
        "injured_count": 0
    })
    inc_id = create_res.json()["incident_id"]
    plan_res = client.post(f"/api/v1/response-plans/generate/{inc_id}")
    plan_id = plan_res.json()["plan_id"]

    # Try executing without approval
    dispatch_res = client.post(f"/api/v1/dispatch/{plan_id}/execute")
    assert dispatch_res.status_code == 400
    assert "Human approval is required" in dispatch_res.json()["detail"]


def test_resolve_incident_releases_resources(client):
    """Test resolving an incident and releasing all locked emergency units."""
    # Create incident, generate plan, approve, and execute dispatch
    create_res = client.post("/api/v1/incidents", json={
        "description": "Small fire drill in Mechanical workshop. Standby unit requested.",
        "location": "Mechanical Workshop",
        "incident_type": "fire",
        "severity": "medium",
        "injured_count": 0
    })
    inc_id = create_res.json()["incident_id"]
    plan_res = client.post(f"/api/v1/response-plans/generate/{inc_id}")
    plan_id = plan_res.json()["plan_id"]

    client.post(f"/api/v1/approvals/{plan_id}/decide", json={
        "decision": "approve",
        "operator_name": "Safety Lead Sarah",
        "notes": "Drill authorized."
    })

    dispatch_res = client.post(f"/api/v1/dispatch/{plan_id}/execute")
    dispatched_ids = dispatch_res.json()["dispatched_resources"]

    # Now Resolve Incident
    resolve_res = client.post(f"/api/v1/incidents/{inc_id}/resolve", json={
        "resolution_notes": "Drill completed successfully. Fire safety officer gave all clear.",
        "resolved_by": "Safety Lead Sarah"
    })
    assert resolve_res.status_code == 200
    resolved_data = resolve_res.json()
    assert resolved_data["status"] == "resolved"
    assert "Drill completed successfully" in resolved_data["summary"]

    # Verify all dispatched units are released back to 'available'
    for rid in dispatched_ids:
        r_check = client.get(f"/api/v1/resources/{rid}")
        assert r_check.status_code == 200
        assert r_check.json()["availability_status"] == "available"

    # Verify audit log recorded resolution
    audit_res = client.get(f"/api/v1/activity/{inc_id}")
    logs = audit_res.json()
    action_types = [l["action_type"] for l in logs]
    assert "automation_execution" in action_types
    assert "incident_resolved" in action_types
