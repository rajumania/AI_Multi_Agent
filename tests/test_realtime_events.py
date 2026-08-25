"""Phase 1 — real agent lifecycle + workflow events (integration level).

Runs in the legacy suite (`python -m pytest tests -q`) where a seeded database
and the full agent pipeline are available and ALLOW_ANONYMOUS_ADMIN is true (so
command endpoints resolve to the operator shim without extra auth plumbing).

Verifies, against the REAL backend, that:
  * generating a plan runs the pipeline and emits agent_started/agent_completed
    for every real node (no fabricated ordering — these come from actual runs),
  * a plan that requires approval emits approval_required,
  * approving a plan emits the canonical approval_approved (alongside the
    preserved approval_granted),
  * executing dispatch emits the canonical response_dispatched.

Events are observed by wrapping the shared event engine's publish_event; the
original is still called, so behavior is unchanged.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.database import SessionLocal
from backend.database.seed import reset_seed_resources
from backend.services.event_engine import event_engine

REAL_NODES = [
    "supervisor", "security", "medical", "transport",
    "communication", "fire", "facilities", "synthesizer",
]


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


@pytest.fixture
def captured(monkeypatch):
    """Capture every published event while still invoking the real handler."""
    events = []
    original = event_engine.publish_event

    def capture(event_name, incident_id, payload, db=None):
        events.append((event_name, incident_id, dict(payload)))
        return original(event_name, incident_id, payload, db=db)

    monkeypatch.setattr(event_engine, "publish_event", capture)
    return events


def _payloads(events, incident_id, event_name, agent=None):
    out = []
    for name, iid, payload in events:
        if iid == incident_id and name == event_name:
            if agent is None or payload.get("agent") == agent:
                out.append(payload)
    return out


def test_orchestration_emits_agent_lifecycle_and_approval_required(client, captured):
    create = client.post("/api/v1/incidents", json={
        "description": "Fire near the chemistry lab; two students appear injured.",
        "location": "Science Block",
        "incident_type": "fire",
        "severity": "high",
        "injured_count": 2,
    })
    assert create.status_code == 201
    inc_id = create.json()["incident_id"]

    plan_res = client.post(f"/api/v1/response-plans/generate/{inc_id}")
    assert plan_res.status_code == 201

    # Every real node emitted a start and a completion during the real run.
    for agent in REAL_NODES:
        assert _payloads(captured, inc_id, "agent_started", agent), f"no agent_started for {agent}"
        completed = _payloads(captured, inc_id, "agent_completed", agent)
        assert completed, f"no agent_completed for {agent}"
        assert completed[-1]["status"] == "completed"
        assert "output" in completed[-1]

    # Structured supervisor output surfaced (classification), no reasoning text.
    sup = _payloads(captured, inc_id, "agent_completed", "supervisor")[-1]
    assert "severity" in sup["output"]

    # High-severity plan requires approval -> approval_required emitted.
    approval = _payloads(captured, inc_id, "approval_required")
    assert approval, "expected approval_required for a high-severity plan"
    assert approval[-1]["status"] == "waiting_approval"
    assert approval[-1]["approval_status"] == "pending"


def test_approval_decision_emits_canonical_approved(client, captured):
    create = client.post("/api/v1/incidents", json={
        "description": "Crowd congestion building near the East Gate exit.",
        "location": "East Gate",
        "incident_type": "crowd",
        "severity": "medium",
        "injured_count": 0,
    })
    inc_id = create.json()["incident_id"]
    plan_id = client.post(f"/api/v1/response-plans/generate/{inc_id}").json()["plan_id"]

    decide = client.post(f"/api/v1/approvals/{plan_id}/decide", json={
        "decision": "approve",
        "operator_name": "Commander Test",
        "notes": "Authorized.",
    })
    assert decide.status_code == 200

    # Existing event preserved AND the canonical event added.
    assert _payloads(captured, inc_id, "approval_granted"), "approval_granted must be preserved"
    approved = _payloads(captured, inc_id, "approval_approved")
    assert approved, "expected canonical approval_approved"
    assert approved[-1]["status"] == "approved"
    assert approved[-1]["approval_status"] == "approved"


def test_dispatch_emits_canonical_response_dispatched(client, captured):
    create = client.post("/api/v1/incidents", json={
        "description": "Dense smoke observed near the CSE building staircase.",
        "location": "CSE Block",
        "incident_type": "fire",
        "severity": "high",
        "injured_count": None,
    })
    inc_id = create.json()["incident_id"]
    plan_id = client.post(f"/api/v1/response-plans/generate/{inc_id}").json()["plan_id"]
    client.post(f"/api/v1/approvals/{plan_id}/decide", json={
        "decision": "approve", "operator_name": "Commander Test", "notes": "Go.",
    })

    dispatch = client.post(f"/api/v1/dispatch/{plan_id}/execute")
    assert dispatch.status_code == 200

    # Existing event preserved AND the canonical event added.
    assert _payloads(captured, inc_id, "dispatch_started"), "dispatch_started must be preserved"
    dispatched = _payloads(captured, inc_id, "response_dispatched")
    assert dispatched, "expected canonical response_dispatched"
    assert dispatched[-1]["status"] == "in_progress"
    assert isinstance(dispatched[-1]["dispatched_resources"], list)
