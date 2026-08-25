"""Real agent lifecycle instrumentation for the LangGraph orchestration.

Phase 1 of the real-time 3D command-center work. This module wraps each graph
node so that the *actual* execution of an agent emits real lifecycle events over
the EXISTING event engine / WebSocket:

    agent_started    -> just before the node runs        (status "working")
    agent_completed  -> after the node returns           (status "completed")
    agent_failed     -> if the node raises               (status "failed")

Design constraints honored here:
  * No second event system: events go through ``event_engine.publish_event`` and
    are delivered by the existing ``broadcast_engine_event`` subscriber, scoped
    by role/department exactly like every other event.
  * The backend remains the source of truth: an event is emitted only when the
    real node actually starts / finishes / fails. There are no timers, no
    synthetic progress, and no fabricated ordering.
  * Only STRUCTURED output is exposed (counts, severities, statuses, booleans).
    Never chain-of-thought, prompts, or hidden model reasoning.
  * The wrapper returns the node's result unchanged, so LangGraph state merging
    and all existing behavior are identical. Instrumentation can never break the
    real workflow: emission failures are swallowed and logged.
  * Events are published with ``db=None`` so they are broadcast-only and add no
    audit rows — keeping existing audit-log assertions intact.

The five *visual* agents shown in the UI are a projection of these real nodes;
the events below carry the real node key plus a human-readable label so the
frontend can map/group them without the backend faking anything.
"""

from typing import Any, Callable, Dict, Optional

from backend.services.event_engine import event_engine
from backend.services.performance import perf_stage
from backend.services.llm_service import llm_service


def _summarize_result(result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract a compact, structured summary of a specialized-agent result.

    Deliberately exposes only counts / statuses / booleans — never free-form
    reasoning text — so nothing sensitive or chain-of-thought-like leaks.
    """
    if not isinstance(result, dict):
        return {}

    summary: Dict[str, Any] = {}

    actions = result.get("actions")
    if isinstance(actions, list):
        summary["actions_count"] = len(actions)

    matched = result.get("matched_resources")
    if isinstance(matched, list):
        summary["matched_resources"] = len(matched)

    # Structured scalar/boolean signals that are safe to surface.
    for key in (
        "severity_assessment",
        "risk_level",
        "recommended_ambulances",
        "route_status",
        "broadcast_priority",
        "evacuation_required",
        "utility_shutdown_required",
        "perimeter_lockdown_required",
        "traffic_rerouting_active",
    ):
        if key in result:
            summary[key] = result[key]

    return summary


# Per-node metadata: human label, start/done messages, and a structured-output
# extractor that reads from the node's RETURNED partial-state dict.
AGENT_META: Dict[str, Dict[str, Any]] = {
    "supervisor": {
        "label": "Incident Intelligence Agent",
        "start": "Analyzing the report and classifying the incident...",
        "done": "Incident classified; specialized response agents delegated.",
        "output": lambda r: {
            "incident_type": r.get("incident_type"),
            "severity": r.get("severity"),
            "confidence": r.get("confidence"),
            "injured_count": r.get("injured_count"),
            "delegated_agents": r.get("delegated_agents"),
        },
    },
    "security": {
        "label": "Security & Perimeter Agent",
        "start": "Assessing perimeter and access-control needs...",
        "done": "Security assessment completed.",
        "output": lambda r: _summarize_result(r.get("security_result")),
    },
    "medical": {
        "label": "Medical Response Agent",
        "start": "Assessing medical risk and triage readiness...",
        "done": "Medical assessment completed.",
        "output": lambda r: _summarize_result(r.get("medical_result")),
    },
    "transport": {
        "label": "Resource & Transport Agent",
        "start": "Planning transit corridors and vehicle logistics...",
        "done": "Transport and logistics plan formulated.",
        "output": lambda r: _summarize_result(r.get("transport_result")),
    },
    "communication": {
        "label": "Communication Agent",
        "start": "Preparing campus alerts and notifications...",
        "done": "Communication plan staged.",
        "output": lambda r: _summarize_result(r.get("communication_result")),
    },
    "fire": {
        "label": "Safety & Hazard Agent",
        "start": "Evaluating fire, containment and evacuation hazards...",
        "done": "Safety and hazard assessment completed.",
        "output": lambda r: _summarize_result(r.get("fire_result")),
    },
    "facilities": {
        "label": "Facilities & Infrastructure Agent",
        "start": "Assessing infrastructure isolation and utility risks...",
        "done": "Facilities assessment completed.",
        "output": lambda r: _summarize_result(r.get("facilities_result")),
    },
    "synthesizer": {
        "label": "Response Planning Agent",
        "start": "Consolidating agent findings into a unified response plan...",
        "done": "Response plan synthesized.",
        "output": lambda r: {
            "recommended_actions": len(r.get("all_recommendations", []) or []),
            "required_approvals": len(r.get("required_approvals", []) or []),
            "allocated_resources": len(r.get("mcp_resources", []) or []),
        },
    },
}


def _emit_agent_event(
    event_name: str,
    incident_id: Optional[str],
    agent_key: str,
    label: str,
    status: str,
    message: str,
    output: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    """Publish a single agent lifecycle event over the existing event engine.

    Broadcast-only (``db=None``). Never raises: instrumentation must not be able
    to break the real workflow.
    """
    if not incident_id:
        # No incident context (e.g. an ad-hoc graph run in a unit test) -> skip
        # emission rather than publish an unroutable event.
        return

    payload: Dict[str, Any] = {
        "event_name": event_name,  # internal routing key (broadcast/should_deliver)
        "event": event_name,       # documented client-facing key
        "agent": agent_key,
        "agent_label": label,
        "status": status,
        "message": message,
    }
    if output is not None:
        payload["output"] = output
    if error is not None:
        payload["error"] = error

    try:
        event_engine.publish_event(event_name, incident_id, payload, db=None)
    except Exception as exc:  # pragma: no cover - defensive; must never propagate
        print(f"[graph-instrumentation] failed to emit {event_name} for {agent_key}: {exc}")


def instrument_node(node_fn: Callable[..., Dict[str, Any]], agent_key: str) -> Callable[..., Dict[str, Any]]:
    """Wrap a graph node so its real execution emits lifecycle events.

    The returned callable forwards ``*args, **kwargs`` to the original node
    (LangGraph may pass a config alongside state) and returns its result
    unchanged, so state merging and existing behavior are untouched.
    """
    meta = AGENT_META.get(agent_key, {})
    label = meta.get("label", agent_key.replace("_", " ").title())
    start_message = meta.get("start", f"{label} started.")
    done_message = meta.get("done", f"{label} completed.")
    output_extractor = meta.get("output")

    def wrapped(state, *args, **kwargs):
        incident_id = state.get("incident_id") if isinstance(state, dict) else None
        incident_token = llm_service.set_incident_context(incident_id)

        _emit_agent_event("agent_started", incident_id, agent_key, label, "working", start_message)

        try:
            with perf_stage(f"{agent_key}_agent", incident_id=incident_id):
                result = node_fn(state, *args, **kwargs)
        except Exception as exc:
            _emit_agent_event(
                "agent_failed", incident_id, agent_key, label, "failed",
                f"{label} failed.", error=str(exc),
            )
            raise
        finally:
            llm_service.reset_incident_context(incident_token)

        output: Optional[Dict[str, Any]] = None
        if output_extractor is not None and isinstance(result, dict):
            try:
                output = output_extractor(result)
            except Exception:
                output = None

        _emit_agent_event(
            "agent_completed", incident_id, agent_key, label, "completed",
            done_message, output=output,
        )
        return result

    wrapped.__name__ = getattr(node_fn, "__name__", f"{agent_key}_node")
    wrapped.__doc__ = getattr(node_fn, "__doc__", None)
    return wrapped
