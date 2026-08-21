from typing import Dict, Any, List
from datetime import datetime, timezone
from backend.graph.state import EmergencyGraphState
from backend.agents.supervisor import supervisor_agent
from backend.agents.security import security_agent
from backend.agents.medical import medical_agent
from backend.agents.transport import transport_agent
from backend.agents.communication import communication_agent


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def supervisor_node(state: EmergencyGraphState) -> Dict[str, Any]:
    """
    Supervisor Agent Node:
    Understands, classifies, assesses severity, extracts location,
    and identifies which specialized agents to delegate to.
    """
    description = state.get("description", "")
    reported_location = state.get("location")
    reported_by = state.get("reported_by")

    # Run Supervisor Agent Analysis
    analysis = supervisor_agent.analyze_incident(
        description=description,
        reported_location=reported_location,
        reported_by=reported_by
    )

    audit = state.get("audit_trail", []).copy()
    audit.append(
        f"[{now_stamp()}] Supervisor Agent: Classified incident as {analysis.incident_type.value.upper()} "
        f"({analysis.severity.value.upper()} severity, {int(analysis.confidence * 100)}% confidence). "
        f"Casualties: {'Unknown (null)' if analysis.injured_count is None else analysis.injured_count}."
    )
    audit.append(
        f"[{now_stamp()}] Supervisor Agent: Delegated workflow to {', '.join([a.capitalize() for a in analysis.recommended_agents])} Agents."
    )

    return {
        "incident_type": analysis.incident_type.value,
        "severity": analysis.severity.value,
        "location": analysis.location,
        "injured_count": analysis.injured_count,
        "summary": analysis.summary,
        "confidence": analysis.confidence,
        "delegated_agents": analysis.recommended_agents,
        "key_observations": analysis.key_observations,
        "audit_trail": audit
    }


def security_node(state: EmergencyGraphState) -> Dict[str, Any]:
    """
    Security Agent Node:
    Generates perimeter and security recommendations.
    """
    incident_type = state.get("incident_type", "unknown")
    severity = state.get("severity", "medium")
    location = state.get("location", "Campus Premises")
    description = state.get("description", "")

    result = security_agent.evaluate(
        incident_type=incident_type,
        severity=severity,
        location=location,
        description=description
    )

    audit = state.get("audit_trail", []).copy()
    audit.append(f"[{now_stamp()}] Security Agent: Generated {len(result.get('actions', []))} perimeter/access actions.")

    return {
        "security_result": result,
        "audit_trail": audit
    }


def medical_node(state: EmergencyGraphState) -> Dict[str, Any]:
    """
    Medical Agent Node:
    Generates triage readiness and medical recommendations.
    """
    incident_type = state.get("incident_type", "unknown")
    severity = state.get("severity", "medium")
    location = state.get("location", "Campus Premises")
    description = state.get("description", "")
    injured_count = state.get("injured_count")

    result = medical_agent.evaluate(
        incident_type=incident_type,
        severity=severity,
        location=location,
        description=description,
        injured_count=injured_count
    )

    audit = state.get("audit_trail", []).copy()
    audit.append(f"[{now_stamp()}] Medical Agent: Generated {len(result.get('actions', []))} triage/ambulance actions.")

    return {
        "medical_result": result,
        "audit_trail": audit
    }


def transport_node(state: EmergencyGraphState) -> Dict[str, Any]:
    """
    Transport Agent Node:
    Generates transit corridor and vehicle logistics recommendations.
    """
    incident_type = state.get("incident_type", "unknown")
    severity = state.get("severity", "medium")
    location = state.get("location", "Campus Premises")
    description = state.get("description", "")

    result = transport_agent.evaluate(
        incident_type=incident_type,
        severity=severity,
        location=location,
        description=description
    )

    audit = state.get("audit_trail", []).copy()
    audit.append(f"[{now_stamp()}] Transport Agent: Formulated route plan (Status: {result.get('route_status', 'open').upper()}).")

    return {
        "transport_result": result,
        "audit_trail": audit
    }


def communication_node(state: EmergencyGraphState) -> Dict[str, Any]:
    """
    Communication Agent Node:
    Composes public alerts, radio briefings, and notification recommendations.
    """
    incident_type = state.get("incident_type", "unknown")
    severity = state.get("severity", "medium")
    location = state.get("location", "Campus Premises")
    description = state.get("description", "")
    summary = state.get("summary", "")
    injured_count = state.get("injured_count")

    result = communication_agent.evaluate(
        incident_type=incident_type,
        severity=severity,
        location=location,
        description=description,
        summary=summary,
        injured_count=injured_count
    )

    audit = state.get("audit_trail", []).copy()
    audit.append(f"[{now_stamp()}] Communication Agent: Staged {result.get('broadcast_priority', 'standard').upper()} priority campus alert.")

    return {
        "communication_result": result,
        "audit_trail": audit
    }


def synthesizer_node(state: EmergencyGraphState) -> Dict[str, Any]:
    """
    Synthesizer Node:
    Consolidates specialized agent recommendations into an integrated plan,
    aggregates real MCP-discovered physical resources, and determines necessary approval requirements.
    """
    all_recommendations: List[str] = []
    required_approvals: List[str] = []
    mcp_resources: List[Dict[str, Any]] = []
    seen_resource_ids = set()

    def add_mcp_items(items):
        if items and isinstance(items, list):
            for it in items:
                rid = it.get("resource_id")
                if rid and rid not in seen_resource_ids:
                    seen_resource_ids.add(rid)
                    mcp_resources.append(it)

    sec = state.get("security_result")
    if sec:
        add_mcp_items(sec.get("matched_resources", []))
        if "actions" in sec:
            for a in sec["actions"]:
                all_recommendations.append(f"[Security] {a}")
        if sec.get("perimeter_lockdown_required"):
            required_approvals.append("Authorize Building / Zone Perimeter Lockdown")

    med = state.get("medical_result")
    if med:
        add_mcp_items(med.get("matched_resources", []))
        if "actions" in med:
            for a in med["actions"]:
                all_recommendations.append(f"[Medical] {a}")
        if med.get("recommended_ambulances", 0) > 0:
            required_approvals.append(f"Dispatch {med['recommended_ambulances']} Emergency Ambulance(s)")

    trn = state.get("transport_result")
    if trn:
        add_mcp_items(trn.get("matched_resources", []))
        if "actions" in trn:
            for a in trn["actions"]:
                all_recommendations.append(f"[Transport] {a}")
        if trn.get("traffic_rerouting_active"):
            required_approvals.append("Enforce Campus Perimeter Road Closures")

    com = state.get("communication_result")
    if com and "actions" in com:
        for a in com["actions"]:
            all_recommendations.append(f"[Comms] {a}")
        if com.get("broadcast_priority") in ["high", "urgent"]:
            required_approvals.append(f"Broadcast All-Campus Emergency Alert: '{com.get('alert_headline')}'")

    audit = state.get("audit_trail", []).copy()
    resource_id_list = [r['resource_id'] for r in mcp_resources]
    audit.append(
        f"[{now_stamp()}] MCP Coordination: Retrieved {len(mcp_resources)} factual campus resource(s) from SQLite: "
        f"({', '.join(resource_id_list) if resource_id_list else 'No units allocated'})."
    )
    audit.append(
        f"[{now_stamp()}] Graph Synthesizer: Consolidated {len(all_recommendations)} actions "
        f"across specialized agents. {len(required_approvals)} action(s) require human approval."
    )

    return {
        "all_recommendations": all_recommendations,
        "required_approvals": required_approvals,
        "mcp_resources": mcp_resources,
        "execution_status": "orchestrated",
        "audit_trail": audit
    }

