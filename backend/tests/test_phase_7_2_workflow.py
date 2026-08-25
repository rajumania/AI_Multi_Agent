"""Phase 7.2 automatic assessment, human gate, routing, and isolation checks."""

from backend.services.llm_service import llm_service
from backend.agents.supervisor import supervisor_agent


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _operator(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def test_chemical_report_uses_actual_text_and_routes_applicable_agents(monkeypatch):
    # Keep this unit test deterministic while exercising the same safety
    # extraction and classification path used when the provider falls back.
    monkeypatch.setattr(llm_service, "generate_json_response", lambda *args, **kwargs: {})
    result = supervisor_agent.analyze_incident(
        "chemical leak in V-block two people are having breathing problems",
        reported_location="V-block",
    )

    assert result.incident_type.value == "chemical"
    assert result.location.lower().startswith("v-block")
    assert result.injured_count == 2
    assert result.severity.value == "critical"
    assert {"medical", "fire", "security", "facilities", "communication"}.issubset(result.recommended_agents)
    assert "transport" not in result.recommended_agents
    assert "respiratory" in result.summary.lower()


def test_plan_requires_approval_and_dispatch_notifies_only_required_departments(client, monkeypatch):
    monkeypatch.setattr(llm_service, "generate_json_response", lambda *args, **kwargs: {})
    operator = _operator(client)
    headers = _auth(operator)
    created = client.post(
        "/api/v1/incidents",
        headers=headers,
        json={
            "description": "chemical leak in V-block two people are having breathing problems",
            "incident_type": "unknown",
            "location": "V-block",
            "severity": "unknown",
            "injured_count": None,
        },
    )
    assert created.status_code == 201, created.text
    incident_id = created.json()["incident_id"]

    assessed = client.post(f"/api/v1/incidents/{incident_id}/analyze", headers=headers)
    assert assessed.status_code == 200, assessed.text
    assert assessed.json()["incident"]["status"] == "classified"
    assert assessed.json()["incident"]["incident_type"] == "chemical"
    assert set(assessed.json()["incident"]["required_departments"]) == {
        "MEDICAL", "FIRE", "SECURITY", "FACILITIES", "COMMUNICATION"
    }

    orchestrated = client.post(f"/api/v1/incidents/{incident_id}/orchestrate", headers=headers)
    assert orchestrated.status_code == 200, orchestrated.text
    plan = client.post(f"/api/v1/response-plans/generate/{incident_id}", headers=headers)
    assert plan.status_code == 201, plan.text
    plan_id = plan.json()["plan_id"]

    blocked = client.post(f"/api/v1/dispatch/{plan_id}/execute", headers=headers)
    assert blocked.status_code == 400
    assert "approval" in blocked.json()["detail"].lower()

    approved = client.post(
        f"/api/v1/approvals/{plan_id}/decide",
        headers=headers,
        json={"decision": "approve", "operator_name": "Main Operator"},
    )
    assert approved.status_code == 200, approved.text
    dispatched = client.post(f"/api/v1/dispatch/{plan_id}/execute", headers=headers)
    assert dispatched.status_code == 200, dispatched.text

    assignments = client.get(f"/api/v1/incidents/{incident_id}/assignments", headers=headers)
    assert {row["department"] for row in assignments.json()} == {
        "MEDICAL", "FIRE", "SECURITY", "FACILITIES", "COMMUNICATION"
    }
    assert {row["status"] for row in assignments.json()} == {"NOTIFIED"}
    assert not any(row["department"] == "TRANSPORT" for row in assignments.json())


def test_bike_accident_is_classified_from_report_text(monkeypatch):
    monkeypatch.setattr(llm_service, "generate_json_response", lambda *args, **kwargs: {})
    result = supervisor_agent.analyze_incident(
        "bike accident near North Gate, rider has a leg injury",
        reported_location="North Gate",
    )
    assert result.incident_type.value == "accident"
    assert result.injured_count == 1
    assert {"medical", "transport", "security", "communication"}.issubset(result.recommended_agents)
    assert "fire" not in result.recommended_agents
