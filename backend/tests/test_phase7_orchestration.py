"""Phase 7 unified event-fusion, lifecycle, and re-planning contracts."""

from datetime import datetime, timezone

from backend.database.models import AgentRunDB, RescueRequestDB, SensorObservationDB
from backend.services.disaster_intelligence_service import trigger_disaster_intelligence
from backend.services.event_engine import event_engine


def test_community_and_sensor_evidence_reach_one_shared_state(db_session):
    sensor_id = "PHASE7-CORRELATION-SENSOR"
    db_session.add(SensorObservationDB(
        sensor_id=sensor_id,
        sensor_type="ground_movement",
        region_id="NEPAL-REGION",
        zone_id="DEMO-N14",
        location="Nepal Mountain N-14",
        value=80,
        unit="normalized",
        observed_at=datetime.now(timezone.utc),
        received_at=datetime.now(timezone.utc),
        source="DEMO_SIMULATION",
    ))
    db_session.add(RescueRequestDB(
        request_id="PHASE7-CORRELATION-REQUEST",
        location="Nepal Mountain N-14",
        description="Community report confirms route movement.",
        people_count=2,
        region_id="NEPAL-REGION",
        zone_id="DEMO-N14",
        status="reported",
    ))
    db_session.commit()

    result = trigger_disaster_intelligence(
        db_session,
        source="community",
        location="Nepal Mountain N-14",
        description="Landslide risk increasing near Nepal mountain route.",
        zone_id="DEMO-N14",
        disaster_type="landslide",
        community_reports=1,
    )

    correlation = result["correlation"]
    assert correlation["sensor_observation_count"] >= 1
    assert correlation["community_report_count"] >= 1
    assert correlation["corroborated"] is True
    assert result["response_plan"]["approval_status"] == "pending"


def test_graph_lifecycle_and_persisted_run_are_reconcilable(db_session):
    captured = []
    original = event_engine.publish_event

    def capture(name, incident_id, payload, db=None):
        captured.append((name, incident_id, dict(payload)))
        return original(name, incident_id, payload, db=db)

    event_engine.publish_event = capture
    try:
        result = trigger_disaster_intelligence(
            db_session,
            source="community",
            location="Nepal Mountain N-14",
            description="Community reports rising landslide risk.",
            zone_id="DEMO-N14",
            disaster_type="landslide",
        )
    finally:
        event_engine.publish_event = original

    names = {(name, payload.get("agent")) for name, _, payload in captured}
    for stage in ("supervisor", "situation_state", "resource", "rescue_priority", "routing", "response_planner", "approval_gate", "monitoring", "recovery"):
        assert ("agent_started", stage) in names
        assert ("agent_completed", stage) in names
    assert any(name == "event_fused" for name, _, _ in captured)
    assert any(name == "risk_updated" for name, _, _ in captured)

    run = db_session.query(AgentRunDB).filter_by(run_id=result["agent_run_id"]).first()
    assert run is not None
    assert run.status == "completed"
    assert result["execution_id"] == run.run_id
    assert "supervisor" in result["agent_results"]
    assert "situation_state" in result["agent_results"]


def test_changed_conditions_create_a_new_approval_gated_plan(db_session):
    initial = trigger_disaster_intelligence(
        db_session,
        source="community",
        location="Nepal Mountain N-14",
        description="Initial landslide warning near the mountain route.",
        zone_id="DEMO-N14",
        disaster_type="landslide",
    )
    updated = trigger_disaster_intelligence(
        db_session,
        source="sensor",
        location="Nepal Mountain N-14",
        description="Ground movement anomaly confirms changing landslide conditions.",
        zone_id="DEMO-N14",
        disaster_type="landslide",
        event_id=initial["event_id"],
        replan=True,
    )

    assert updated["event_id"] == initial["event_id"]
    assert updated["response_plan"]["plan_id"] != initial["response_plan"]["plan_id"]
    assert updated["response_plan"]["previous_plan_id"] == initial["response_plan"]["plan_id"]
    assert updated["approval_status"] == "pending"
    assert updated["correlation"]["sensor_observation_count"] >= 1


def test_department_head_can_decide_only_a_routed_plan(client):
    created = client.post("/api/v1/events", json={
        "event_source": "community",
        "location": "Nepal Mountain N-14",
        "zone_id": "DEMO-N14",
        "disaster_type": "landslide",
        "description": "Department approval scope test for the mountain route.",
    })
    assert created.status_code == 201, created.text
    event_id = created.json()["event_id"]
    plan_id = created.json()["response_plan"]["plan_id"]

    login = client.post("/api/v1/auth/department/login", json={"email": "security@aitam.local", "password": "password123", "department": "SECURITY"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    pending = client.get("/api/v1/approvals/pending", headers=headers)
    assert pending.status_code == 200, pending.text
    assert any(row["plan_id"] == plan_id and row["incident_id"] == event_id for row in pending.json())

    decided = client.post(f"/api/v1/approvals/{plan_id}/decide", headers=headers, json={"decision": "approve", "operator_name": "ignored"})
    assert decided.status_code == 200, decided.text
    assert decided.json()["approval_status"] == "approved"
