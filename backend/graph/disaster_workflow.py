"""Event-driven Phase 3 disaster graph with conditional parallel analysis."""

from __future__ import annotations

import json
import operator
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from backend.agents.disaster_intelligence import SPECIALIST_AGENTS, SupervisorIncidentCommander
from backend.database.models import ResponsePlanDB, RescueRequestDB
from backend.services.audit_service import audit_service
from backend.services.event_engine import event_engine
from backend.services.priority_engine import calculate_priority
from backend.services.resource_coordination import available_resources, resources_by_types
from backend.services.safe_routing import safe_routing_service


OPERATIONAL_AGENT_NAMES = {"resource", "rescue_priority", "routing", "response_planner", "monitoring", "recovery"}
PARALLEL_SPECIALIST_NAMES = [name for name in SPECIALIST_AGENTS if name not in OPERATIONAL_AGENT_NAMES]
supervisor_agent = SupervisorIncidentCommander()


def _merge_maps(left: dict | None, right: dict | None) -> dict:
    return {**(left or {}), **(right or {})}


class DisasterIntelligenceState(TypedDict, total=False):
    event_id: str
    execution_id: str
    event_source: str
    disaster_type: str
    location: str
    region: str
    zone: str
    zone_id: str
    region_id: str
    description: str
    severity: str
    risk_score: float
    risk_level: str
    risk_confidence: float
    weather_data: dict[str, Any]
    environmental_data: list[dict[str, Any]]
    sensor_data: list[dict[str, Any]]
    sensor_events: list[dict[str, Any]]
    earthquake_data: list[dict[str, Any]]
    earthquake_status: str
    severe_weather_data: list[dict[str, Any]]
    severe_weather_status: str
    image_analysis: dict[str, Any]
    exact_latitude: float
    exact_longitude: float
    correlation: dict[str, Any]
    geographic_data: dict[str, Any]
    historical_data: dict[str, Any]
    community_reports: list[dict[str, Any]]
    vulnerable_zones: list[str]
    nearby_resources: list[dict[str, Any]]
    rescue_requests: list[dict[str, Any]]
    priority_results: list[dict[str, Any]]
    shelters: list[dict[str, Any]]
    hospitals: list[dict[str, Any]]
    routes: list[dict[str, Any]]
    response_plan: dict[str, Any]
    alerts: list[dict[str, Any]]
    approval_status: str
    travel_safety: dict[str, Any]
    required_agents: list[str]
    specialist_agents: list[str]
    context: dict[str, Any]
    agent_results: Annotated[dict[str, Any], _merge_maps]
    agent_errors: Annotated[list[str], operator.add]
    audit_events: Annotated[list[dict[str, Any]], operator.add]
    replan_requested: bool


def _record(state: DisasterIntelligenceState, agent_name: str, result: dict[str, Any]) -> dict[str, Any]:
    event_id = state.get("event_id", "unknown")
    execution_id = state.get("execution_id")
    started_payload = {"event_name": "agent_started", "event": "agent_started", "agent": agent_name, "status": "working", "description": f"{agent_name.replace('_', ' ').title()} started"}
    if execution_id:
        started_payload["execution_id"] = execution_id
    # Specialist nodes are fanned out by LangGraph and may run concurrently.
    # Do not commit the shared SQLAlchemy session from these callbacks; the
    # aggregate AgentRunDB/audit record is persisted by the orchestration
    # service after the graph converges.
    event_engine.publish_event("agent_started", event_id, started_payload)
    event_engine.log_trace(event_id, agent_name.replace("_", " ").title(), "analyze", result.get("summary", "Evidence reviewed"), tool_call=result.get("evidence"), confidence=state.get("risk_confidence"))
    completed_payload = {"event_name": "agent_completed", "event": "agent_completed", "agent": agent_name, "status": "completed", "output": result, "description": result.get("summary", "Analysis completed")}
    if execution_id:
        completed_payload["execution_id"] = execution_id
    event_engine.publish_event("agent_completed", event_id, completed_payload)
    return {"agent_results": {agent_name: result}, "audit_events": [{"agent": agent_name, "result": result}]}


def _supervisor(state: DisasterIntelligenceState) -> dict[str, Any]:
    selected = supervisor_agent.select(state)
    operational = ["resource", "rescue_priority", "routing", "response_planner", "monitoring", "recovery"]
    result = {"status": "completed", "summary": f"Supervisor routed {len(selected)} independent specialist(s) and {len(operational)} operational stage(s).", "selected_specialists": selected, "operational_stages": operational}
    return {**_record(state, "supervisor", result), "required_agents": selected + operational, "specialist_agents": selected, "audit_events": [{"agent": "supervisor", "selected": selected + operational}]}


def _fan_out(state: DisasterIntelligenceState):
    return [Send(name, state) for name in state.get("specialist_agents", []) if name in PARALLEL_SPECIALIST_NAMES]


def _specialist(name: str):
    def node(state: DisasterIntelligenceState):
        try:
            return _record(state, name, SPECIALIST_AGENTS[name].analyze(dict(state)))
        except Exception as exc:
            event_engine.publish_event("agent_failed", state.get("event_id", "unknown"), {"event_name": "agent_failed", "event": "agent_failed", "agent": name, "status": "failed", "error": str(exc), "description": str(exc), "execution_id": state.get("execution_id")})
            return {"agent_errors": [f"{name}: {exc}"], "audit_events": [{"agent": name, "error": str(exc)}]}
    return node


def _situation(state):
    result = {"status": "completed", "summary": "Specialist evidence merged into a shared situation state.", "agent_count": len(state.get("agent_results", {})), "correlation": state.get("correlation", {})}
    return _record(state, "situation_state", result)


def _resources(state):
    db = state.get("context", {}).get("db")
    if db is None:
        result = {"status": "completed", "summary": "Resource database unavailable", "resources": []}
    else:
        resources = available_resources(db, state.get("zone_id"))
        state_result = {"status": "completed", "summary": f"{len(resources)} available database resource(s) found.", "resources": resources}
        result = state_result
        state["nearby_resources"] = resources
        state["shelters"] = resources_by_types(db, {"shelter"})
        state["hospitals"] = resources_by_types(db, {"hospital", "clinic", "medical_center"})
    return {**_record(state, "resource", result), "nearby_resources": state.get("nearby_resources", []), "shelters": state.get("shelters", []), "hospitals": state.get("hospitals", [])}


def _priority(state):
    db = state.get("context", {}).get("db")
    results = []
    if db is not None:
        requests = db.query(RescueRequestDB).filter(RescueRequestDB.zone_id == state.get("zone_id"), RescueRequestDB.status.in_(["reported", "pending", "in_progress"])).all()
        for request in requests:
            result = calculate_priority(request, state.get("risk_score", 0), inaccessible=state.get("risk_level") == "critical")
            request.priority_score = result["priority_score"]
            results.append(result)
        db.commit()
    state["priority_results"] = sorted(results, key=lambda item: item["priority_score"], reverse=True)
    result = {"status": "completed", "summary": f"{len(results)} rescue request(s) ranked deterministically.", "results": results}
    return {**_record(state, "rescue_priority", result), "priority_results": state["priority_results"]}


def _routing(state):
    resources = state.get("nearby_resources", [])
    origin = resources[0].get("location") if resources else "Emergency Operations Center"
    route = safe_routing_service.calculate(origin or "Emergency Operations Center", state.get("location", "affected zone"), origin_lat=resources[0].get("latitude") if resources else None, origin_lng=resources[0].get("longitude") if resources else None, destination_lat=state.get("geographic_data", {}).get("latitude"), destination_lng=state.get("geographic_data", {}).get("longitude"), hazardous_zones=state.get("vulnerable_zones"))
    state["routes"] = [route]
    result = {"status": "completed", "summary": route.get("reason", "Route evaluated"), "route": route}
    return {**_record(state, "routing", result), "routes": state["routes"]}


def _planner(state):
    db = state.get("context", {}).get("db")
    plan = None
    if db is not None:
        existing = db.query(ResponsePlanDB).filter(ResponsePlanDB.incident_id == state.get("event_id")).order_by(ResponsePlanDB.created_at.desc()).first()
        if existing and not state.get("context", {}).get("replan"):
            plan = {"plan_id": existing.plan_id, "approval_status": existing.approval_status}
        else:
            now = datetime.now(timezone.utc)
            allocated = [item.get("resource_id") for item in state.get("nearby_resources", [])[:5] if item.get("resource_id")]
            actions = ["Review current risk evidence", "Prepare rescue and relief resources", "Check shelter and hospital capacity", "Issue public communication after approval"]
            row = ResponsePlanDB(plan_id=f"PLAN-{uuid.uuid4().hex[:10].upper()}", incident_id=state.get("event_id"), title=f"{str(state.get('disaster_type', 'disaster')).replace('_', ' ').title()} community response", severity=state.get("risk_level", "medium"), location=state.get("location", "affected zone"), recommended_actions=json.dumps(actions), allocated_resources=json.dumps(allocated), requires_approval="true", approval_status="pending", created_at=now, updated_at=now)
            db.add(row)
            db.commit()
            plan = {"plan_id": row.plan_id, "approval_status": row.approval_status, "allocated_resources": allocated, "recommended_actions": actions, "previous_plan_id": existing.plan_id if existing and state.get("context", {}).get("replan") else None}
    plan = plan or {"plan_id": None, "approval_status": "not_created"}
    state["response_plan"] = plan
    return {**_record(state, "response_planner", {"status": "completed", "summary": "Response plan prepared; high-impact actions remain approval-gated.", "plan": plan}), "response_plan": plan}


def _approval(state):
    status = state.get("response_plan", {}).get("approval_status", "not_created")
    state["approval_status"] = status
    if status == "pending":
        event_engine.publish_event("approval_required", state.get("event_id", "unknown"), {"event_name": "approval_required", "description": "Human approval required before high-impact response actions.", "plan_id": state.get("response_plan", {}).get("plan_id")})
    return {**_record(state, "approval_gate", {"status": "completed", "summary": f"Approval status: {status}.", "requires_human_authorization": status == "pending"}), "approval_status": status}


def _monitor(state):
    result = {"status": "active", "summary": "Monitoring weather, sensors, resources, routes, shelters, hospitals and community reports."}
    event_engine.publish_event("monitoring_started", state.get("event_id", "unknown"), {"event_name": "monitoring_started", "event": "MONITORING_STARTED", "status": "active", "description": result["summary"], "execution_id": state.get("execution_id")})
    return _record(state, "monitoring", result)


def _recovery(state):
    result = {"status": "standby", "summary": "Recovery coordination is ready after threat conditions stabilize."}
    return _record(state, "recovery", result)


def create_disaster_graph():
    graph = StateGraph(DisasterIntelligenceState)
    graph.add_node("supervisor", _supervisor)
    for name in PARALLEL_SPECIALIST_NAMES:
        graph.add_node(name, _specialist(name))
    for name, node in (("situation_state", _situation), ("resource_coordination", _resources), ("priority_evaluation", _priority), ("safe_routing", _routing), ("response_planner", _planner), ("approval_gate", _approval), ("monitoring", _monitor), ("recovery", _recovery)):
        graph.add_node(name, node)
    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges("supervisor", _fan_out, path_map=PARALLEL_SPECIALIST_NAMES)
    for name in PARALLEL_SPECIALIST_NAMES:
        graph.add_edge(name, "situation_state")
    graph.add_edge("situation_state", "resource_coordination")
    graph.add_edge("resource_coordination", "priority_evaluation")
    graph.add_edge("priority_evaluation", "safe_routing")
    graph.add_edge("safe_routing", "response_planner")
    graph.add_edge("response_planner", "approval_gate")
    graph.add_edge("approval_gate", "monitoring")
    graph.add_edge("monitoring", "recovery")
    graph.add_edge("recovery", END)
    return graph.compile()


disaster_workflow = create_disaster_graph()


def run_disaster_workflow(state: DisasterIntelligenceState) -> DisasterIntelligenceState:
    return disaster_workflow.invoke(state)
