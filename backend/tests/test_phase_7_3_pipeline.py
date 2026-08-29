"""Phase 7.3 asynchronous intake, provider state, and fallback checks."""

import asyncio
import time

from backend.api import incidents as incidents_api
from backend.config import settings
from backend.services.event_engine import event_engine
from backend.services.llm_service import llm_service


def _payload(description="bike accident near North Gate, rider has a leg injury"):
    return {
        "description": description,
        "incident_type": "unknown",
        "location": "North Gate",
        "severity": "unknown",
        "injured_count": None,
    }


def test_incident_creation_returns_before_background_workflow(client, monkeypatch):
    started = []

    def record_background(incident_id):
        started.append(incident_id)

    monkeypatch.setattr(settings, "AUTOMATIC_AI_WORKFLOW", True)
    monkeypatch.setattr(incidents_api, "run_automatic_incident_pipeline", record_background)

    began = time.perf_counter()
    response = client.post("/api/v1/incidents", json=_payload())
    elapsed_ms = (time.perf_counter() - began) * 1000

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "reported"
    assert response.json()["incident_id"] in started
    assert elapsed_ms < 500


def test_background_pipeline_uses_existing_fallback_and_stops_for_approval(client, monkeypatch):
    # Disable only external providers for this focused test. The real fallback
    # implementation, supervisor sanitization, LangGraph agents, and planner
    # still execute end-to-end.
    monkeypatch.setattr(settings, "AUTOMATIC_AI_WORKFLOW", False)
    monkeypatch.setattr(llm_service, "is_gemini_available", lambda: False)
    monkeypatch.setattr(llm_service, "is_openai_available", lambda: False)
    emitted = []
    original_publish = event_engine.publish_event

    def capture_event(event_name, incident_id, payload, db=None):
        emitted.append(event_name)
        return original_publish(event_name, incident_id, payload, db=db)

    monkeypatch.setattr(event_engine, "publish_event", capture_event)

    created = client.post(
        "/api/v1/incidents",
        json=_payload("chemical leak in V-block two people are having breathing problems"),
    )
    assert created.status_code == 201, created.text
    incident_id = created.json()["incident_id"]

    incidents_api.run_automatic_incident_pipeline(incident_id)

    incident = client.get(f"/api/v1/incidents/{incident_id}").json()
    assert incident["status"] == "awaiting_approval"
    assert incident["ai_provider_status"] == "FALLBACK_ACTIVE"
    assert incident["incident_type"] == "chemical"
    assert incident["injured_count"] == 2

    operator = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"})
    assert operator.status_code == 200, operator.text
    headers = {"Authorization": f"Bearer {operator.json()['token']}"}
    plans_response = client.get(f"/api/v1/response-plans?incident_id={incident_id}", headers=headers)
    assert plans_response.status_code == 200, plans_response.text
    plans = plans_response.json()
    assert len(plans) == 1
    assert plans[0]["approval_status"] == "pending"
    assert client.get(f"/api/v1/incidents/{incident_id}/assignments", headers=headers).json() == []
    assert {"assessment_started", "incident_assessed", "response_plan_generated", "awaiting_human_authorization"}.issubset(emitted)


def test_gemini_timeout_records_reason_and_runs_existing_fallback(monkeypatch):
    class FakeModel:
        pass

    async def timeout(*args, **kwargs):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(llm_service, "is_gemini_available", lambda: True)
    monkeypatch.setattr(llm_service, "is_openai_available", lambda: False)
    monkeypatch.setattr("backend.services.llm_service.genai.GenerativeModel", lambda **kwargs: FakeModel())
    monkeypatch.setattr(llm_service, "_generate_gemini_response", timeout)

    result = llm_service.generate_json_response("system", "chemical leak in V-block")
    metadata = llm_service.get_last_call_metadata()

    assert isinstance(result, dict)
    assert metadata["status"] == "FALLBACK_ACTIVE"
    assert metadata["fallback_used"] is True
    assert metadata["failure_reason"] == "gemini_timeout"
