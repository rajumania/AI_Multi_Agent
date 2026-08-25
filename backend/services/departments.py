"""Canonical department registry for CampusFlow AI.

Single source of truth for the six operational departments and the mappings
between departments, resource types, agents, and incident categories.

This module is intentionally dependency-free (no DB/agent imports) so it can be
imported anywhere — migration, seed, agents, RBAC guards, routing — without
creating import cycles.

Departments (Part 5 / Part 7 of the requirements):
    SECURITY, MEDICAL, TRANSPORT, COMMUNICATION, FIRE, FACILITIES

Note: COMMUNICATION is a coordination department (campus-wide alerting) and
owns no physical resource type, but it still has an agent, a login, and a
dashboard like every other department.
"""

from typing import List, Optional

# Ordered tuple of the six department codes (stable order for UIs).
DEPARTMENTS = (
    "SECURITY",
    "MEDICAL",
    "TRANSPORT",
    "COMMUNICATION",
    "FIRE",
    "FACILITIES",
)

DEPARTMENT_SET = frozenset(DEPARTMENTS)

# Human-friendly labels for dashboards / notifications.
DEPARTMENT_LABELS = {
    "SECURITY": "Campus Security",
    "MEDICAL": "Medical & Health",
    "TRANSPORT": "Transport & Logistics",
    "COMMUNICATION": "Communications",
    "FIRE": "Fire & Safety",
    "FACILITIES": "Facilities & Maintenance",
}

# Physical resource_type -> owning department.
# Keys match ResourceType values in backend/models/resources.py.
RESOURCE_TYPE_TO_DEPARTMENT = {
    "security": "SECURITY",
    "ambulance": "MEDICAL",
    "first_aid": "MEDICAL",
    "medical_center": "MEDICAL",
    "vehicle": "TRANSPORT",
    "fire_response": "FIRE",
    "facility": "FACILITIES",
    "shelter": "FACILITIES",
    # "other" intentionally unmapped -> department stays NULL.
}

# Agent singleton name -> department it represents.
# supervisor_agent is the orchestrator and belongs to no single department.
AGENT_TO_DEPARTMENT = {
    "security_agent": "SECURITY",
    "medical_agent": "MEDICAL",
    "transport_agent": "TRANSPORT",
    "communication_agent": "COMMUNICATION",
    "fire_agent": "FIRE",
    "facilities_agent": "FACILITIES",
}

# Incident category -> departments that should be engaged (Part 7 routing).
# Keys match IncidentType values in backend/models/incident.py.
# This is ADDITIVE metadata used for department_responses / notifications; it
# does NOT change the existing LangGraph pipeline (all agents still execute).
INCIDENT_TYPE_TO_DEPARTMENTS = {
    "fire": ["FIRE", "SECURITY", "MEDICAL", "COMMUNICATION"],
    "chemical": ["MEDICAL", "FIRE", "SECURITY", "FACILITIES", "COMMUNICATION"],
    "medical": ["MEDICAL", "SECURITY"],
    "security": ["SECURITY", "COMMUNICATION"],
    "accident": ["MEDICAL", "TRANSPORT", "SECURITY"],
    "weather": ["FACILITIES", "SECURITY", "COMMUNICATION"],
    "crowd": ["SECURITY", "COMMUNICATION", "MEDICAL"],
    "facility": ["FACILITIES", "SECURITY"],
    "other": ["SECURITY"],
    "unknown": ["SECURITY"],
}

# Severities that additionally trigger campus-wide communications.
_ESCALATION_SEVERITIES = frozenset({"high", "critical"})


def normalize_department(value: Optional[str]) -> Optional[str]:
    """Return the canonical UPPERCASE department code, or None if invalid."""
    if not value:
        return None
    code = str(value).strip().upper()
    return code if code in DEPARTMENT_SET else None


def is_valid_department(value: Optional[str]) -> bool:
    return normalize_department(value) is not None


def department_for_resource_type(resource_type: Optional[str]) -> Optional[str]:
    """Map a resource_type to its owning department code (or None)."""
    if not resource_type:
        return None
    return RESOURCE_TYPE_TO_DEPARTMENT.get(str(resource_type).strip().lower())


def resource_types_for_department(department: Optional[str]) -> List[str]:
    """All resource_type values owned by a department."""
    dept = normalize_department(department)
    if dept is None:
        return []
    return [rt for rt, d in RESOURCE_TYPE_TO_DEPARTMENT.items() if d == dept]


def department_for_agent(agent_name: Optional[str]) -> Optional[str]:
    """Map an agent singleton name (e.g. 'security_agent') to a department."""
    if not agent_name:
        return None
    return AGENT_TO_DEPARTMENT.get(str(agent_name).strip().lower())


def departments_for_incident(
    incident_type: Optional[str], severity: Optional[str] = None
) -> List[str]:
    """Departments that should be engaged for an incident category.

    High/critical severities additionally engage COMMUNICATION for campus-wide
    alerting. Returns a de-duplicated list preserving priority order.
    """
    key = (incident_type or "unknown").strip().lower()
    base = list(INCIDENT_TYPE_TO_DEPARTMENTS.get(key, INCIDENT_TYPE_TO_DEPARTMENTS["unknown"]))
    if severity and str(severity).strip().lower() in _ESCALATION_SEVERITIES:
        if "COMMUNICATION" not in base:
            base.append("COMMUNICATION")
    # De-duplicate while preserving order.
    seen = set()
    ordered: List[str] = []
    for dept in base:
        if dept not in seen:
            seen.add(dept)
            ordered.append(dept)
    return ordered
