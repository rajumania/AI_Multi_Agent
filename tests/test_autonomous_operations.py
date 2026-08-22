import pytest
from backend.services.severity_engine import severity_engine
from backend.services.policy_engine import policy_engine
from backend.services.event_engine import event_engine
from backend.services.simulation_service import simulation_service
from backend.database.database import SessionLocal, Base, engine
from backend.database.seed import seed_resources


@pytest.fixture(scope="module")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_resources(db)
    yield db
    db.close()


def test_severity_engine_deterministic_scoring():
    # 1. Critical Fire with casualties in academic building
    res = severity_engine.evaluate(
        incident_type="fire",
        description="Explosion and dense smoke on 2nd floor U-Block CSE lab, multiple students trapped.",
        location="U-Block (CSE & IT)",
        injured_count=3,
        corroboration_count=3
    )
    assert res.level in ["high", "critical"]
    assert res.score >= 60
    assert res.confidence >= 0.85
    assert len(res.breakdown) >= 4
    assert any("Casualties" in b["factor"] for b in res.breakdown)

    # 2. Minor Facility Issue
    res_minor = severity_engine.evaluate(
        incident_type="facility",
        description="Water tap leaking near outdoor garden walkway.",
        location="Campus Open Quad",
        injured_count=0,
        corroboration_count=1
    )
    assert res_minor.level in ["low", "medium"]
    assert res_minor.score < 45


def test_policy_engine_guardrails():
    # Safe actions vs high-impact actions
    actions = [
        "Position security squad at building perimeter",
        "Reserve ambulance at Health Centre for medical standby",
        "Issue campus-wide emergency SMS broadcast and sound sirens",
        "Inspect electrical mains shutoff panel"
    ]
    auto_exec, req_approval, flag = policy_engine.evaluate_plan_actions(actions, severity="high")
    assert len(auto_exec) == 3
    assert len(req_approval) == 1
    assert "broadcast" in req_approval[0].lower() or "siren" in req_approval[0].lower()
    assert flag is True


def test_event_engine_decision_trace():
    inc_id = "TEST-TRACE-001"
    event_engine.log_trace(
        incident_id=inc_id,
        agent_name="Security Agent",
        action="find_nearest_security_team",
        thought="Queried nearest squad: SEC-002 selected.",
        confidence=0.95,
        why="Stationed within 40m of U-Block."
    )

    trace = event_engine.get_decision_trace(inc_id)
    assert len(trace) >= 1
    assert trace[0]["agent"] == "Security Agent"
    assert trace[0]["confidence"] == 0.95


def test_simulation_service_scenario_and_failure_injection(db_session):
    # Start Digital Twin U-Block Fire Scenario
    sim_res = simulation_service.start_scenario("ublock_fire", db_session)
    assert sim_res["status"] == "scenario_initiated"
    inc_id = sim_res["incident_id"]
    assert inc_id.startswith("SIM-")
    assert len(sim_res["decision_trace"]) >= 3

    # Inject Breakdown Failure on AMB-001
    fail_res = simulation_service.inject_resource_failure(inc_id, "AMB-001", db_session)
    assert fail_res["status"] == "replan_success"
    assert fail_res["failed_resource"] == "AMB-001"
    assert fail_res["substitute_resource"] == "AMB-002"

    # Check updated decision trace contains failure and re-plan
    trace = event_engine.get_decision_trace(inc_id)
    assert any("CRITICAL ALERT" in t["thought"] or "mechanical breakdown" in t["thought"] for t in trace)
    assert any("replan_alternate_resource" in t["action"] for t in trace)
