"""Phase 1 — real agent lifecycle event emission (unit level).

These tests exercise ``instrument_node`` directly with fake nodes, so they need
no database, no LLM key, and no real agents. They verify that:

  * a node's REAL execution emits agent_started then agent_completed,
  * completion carries STRUCTURED output (counts/scalars) — never reasoning,
  * a raising node emits agent_failed and the exception still propagates,
  * with no incident_id in state, nothing is emitted (no unroutable events),
  * the per-node metadata covers every real graph node.

Graph/API-level event tests (approval_required, approval_approved,
response_dispatched, and a full-pipeline run) live in the legacy suite
``tests/test_realtime_events.py`` where a seeded DB and the full agent pipeline
are available.
"""

import pytest

from backend.services.event_engine import event_engine
from backend.graph.instrumentation import instrument_node, AGENT_META


class _Capture:
    """Collect events published to the global event engine during a test."""

    def __init__(self, names):
        self.events = []
        for name in names:
            event_engine.subscribe(name, self._handler)

    def _handler(self, incident_id, payload, db=None):
        self.events.append((payload.get("event_name"), incident_id, payload))

    def of(self, name):
        return [e for e in self.events if e[0] == name]


def test_instrument_node_emits_started_and_completed_with_structured_output():
    cap = _Capture(["agent_started", "agent_completed", "agent_failed"])

    def fake_medical_node(state):
        # Mirrors the shape the real medical node returns.
        return {
            "medical_result": {
                "actions": ["triage", "stage ambulance"],
                "recommended_ambulances": 2,
                "matched_resources": [{"resource_id": "AMB-01"}],
            }
        }

    wrapped = instrument_node(fake_medical_node, "medical")
    result = wrapped({"incident_id": "INC-U1", "description": "x"})

    # Node result must be returned unchanged (state merging unaffected).
    assert result["medical_result"]["recommended_ambulances"] == 2

    started = [e for e in cap.of("agent_started") if e[1] == "INC-U1"]
    assert started and started[-1][2]["agent"] == "medical"
    assert started[-1][2]["status"] == "working"
    assert started[-1][2]["event"] == "agent_started"  # client-facing key present

    completed = [e for e in cap.of("agent_completed") if e[1] == "INC-U1"]
    assert completed, "expected an agent_completed event"
    payload = completed[-1][2]
    assert payload["status"] == "completed"
    assert payload["agent_label"] == AGENT_META["medical"]["label"]
    # Structured output only.
    assert payload["output"]["actions_count"] == 2
    assert payload["output"]["recommended_ambulances"] == 2
    assert payload["output"]["matched_resources"] == 1

    assert [e for e in cap.of("agent_failed") if e[1] == "INC-U1"] == []


def test_instrument_node_emits_failed_and_reraises():
    cap = _Capture(["agent_started", "agent_completed", "agent_failed"])

    def boom(state):
        raise ValueError("node blew up")

    wrapped = instrument_node(boom, "security")
    with pytest.raises(ValueError):
        wrapped({"incident_id": "INC-U2"})

    failed = [e for e in cap.of("agent_failed") if e[1] == "INC-U2"]
    assert failed, "expected an agent_failed event"
    fp = failed[-1][2]
    assert fp["agent"] == "security"
    assert fp["status"] == "failed"
    assert "node blew up" in fp["error"]

    assert any(e[1] == "INC-U2" for e in cap.of("agent_started"))
    assert [e for e in cap.of("agent_completed") if e[1] == "INC-U2"] == []


def test_instrument_node_without_incident_id_emits_nothing():
    cap = _Capture(["agent_started", "agent_completed", "agent_failed"])

    def node(state):
        return {"ok": True}

    result = instrument_node(node, "medical")({})  # no incident_id
    assert result == {"ok": True}
    assert cap.events == []


def test_agent_meta_covers_every_real_node():
    # Guards against future drift between the graph nodes and their metadata.
    expected = {
        "supervisor", "security", "medical", "transport",
        "communication", "fire", "facilities", "synthesizer",
    }
    assert expected.issubset(set(AGENT_META.keys()))
    for key in expected:
        meta = AGENT_META[key]
        assert meta.get("label")
        assert meta.get("start")
        assert meta.get("done")
        assert callable(meta.get("output"))
