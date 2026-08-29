"""Canonical department registry for AITAM Disaster Response AI.

Single source of truth for the eight operational departments and the mappings
between departments, resource types, agents, and incident categories.

This module is intentionally dependency-free (no DB/agent imports) so it can be
imported anywhere — migration, seed, agents, RBAC guards, routing — without
creating import cycles.

Departments (Part 5 / Part 7 of the requirements):
    MEDICAL, SEARCH_AND_RESCUE, FIRE, SECURITY, TRANSPORT, COMMUNICATION,
    FACILITIES, SHELTER

Note: COMMUNICATION is a coordination department (campus-wide alerting) and
owns no physical resource type, but it still has an agent, a login, and a
dashboard like every other department.
"""

from typing import List, Optional

# Ordered tuple of the eight built-in department codes (stable order for UIs).
DEPARTMENTS = (
    "MEDICAL",
    "SEARCH_AND_RESCUE",
    "FIRE",
    "SECURITY",
    "TRANSPORT",
    "COMMUNICATION",
    "FACILITIES",
    "SHELTER",
)

# The built-in codes are immutable in the public UI, while the persisted
# organization administrator may register additional operational units at
# runtime. The set is intentionally private in behavior but retained under
# this historical name for compatibility with existing imports.
DEPARTMENT_SET = set(DEPARTMENTS)

# Human-friendly labels for dashboards / notifications.
DEPARTMENT_LABELS = {
    "MEDICAL": "Medical & Health",
    "SEARCH_AND_RESCUE": "Search & Rescue",
    "FIRE": "Fire & Safety",
    "SECURITY": "Security / Public Safety",
    "TRANSPORT": "Transport & Logistics",
    "COMMUNICATION": "Communications",
    "FACILITIES": "Facilities & Maintenance",
    "SHELTER": "Shelter & Relief",
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
    "shelter": "SHELTER",
    "hospital": "MEDICAL",
    "clinic": "MEDICAL",
    "rescue_team": "SEARCH_AND_RESCUE",
    "fire_service": "FIRE",
    "police": "SECURITY",
    "emergency_service": "SECURITY",
    "boat": "TRANSPORT",
    "food": "FACILITIES",
    "water": "FACILITIES",
    "emergency_kit": "FACILITIES",
    # "other" intentionally unmapped -> department stays NULL.
}

# Agent singleton name -> department it represents.
# supervisor_agent is the orchestrator and belongs to no single department.
AGENT_TO_DEPARTMENT = {
    "medical_agent": "MEDICAL",
    "rescue_agent": "SEARCH_AND_RESCUE",
    "search_rescue_agent": "SEARCH_AND_RESCUE",
    "fire_agent": "FIRE",
    "security_agent": "SECURITY",
    "transport_agent": "TRANSPORT",
    "communication_agent": "COMMUNICATION",
    "facilities_agent": "FACILITIES",
    "shelter_agent": "SHELTER",
}

# Incident category -> departments that should be engaged (Part 7 routing).
# Keys match IncidentType values in backend/models/incident.py.
# This is ADDITIVE metadata used for department_responses / notifications; it
# does NOT change the existing LangGraph pipeline (all agents still execute).
INCIDENT_TYPE_TO_DEPARTMENTS = {
    "fire": ["FIRE", "MEDICAL", "SECURITY", "TRANSPORT", "FACILITIES", "COMMUNICATION"],
    "chemical": ["FIRE", "MEDICAL", "SECURITY", "FACILITIES", "TRANSPORT", "COMMUNICATION"],
    "medical": ["MEDICAL", "SECURITY"],
    "security": ["SECURITY", "COMMUNICATION"],
    "accident": ["MEDICAL", "SEARCH_AND_RESCUE", "TRANSPORT", "SECURITY"],
    "weather": ["SEARCH_AND_RESCUE", "MEDICAL", "TRANSPORT", "SHELTER", "FACILITIES", "SECURITY", "COMMUNICATION"],
    "crowd": ["SECURITY", "COMMUNICATION", "MEDICAL"],
    "facility": ["FACILITIES", "SECURITY"],
    "other": ["SECURITY"],
    "unknown": ["SECURITY"],
    "landslide": ["SEARCH_AND_RESCUE", "FACILITIES", "MEDICAL", "SECURITY", "TRANSPORT", "COMMUNICATION", "SHELTER"],
    "flood": ["SEARCH_AND_RESCUE", "MEDICAL", "TRANSPORT", "SHELTER", "FACILITIES", "SECURITY", "COMMUNICATION"],
    "urban_flood": ["SEARCH_AND_RESCUE", "MEDICAL", "TRANSPORT", "SHELTER", "FACILITIES", "SECURITY", "COMMUNICATION"],
    "cyclone": ["SEARCH_AND_RESCUE", "MEDICAL", "TRANSPORT", "SHELTER", "FACILITIES", "SECURITY", "COMMUNICATION"],
    "earthquake": ["SEARCH_AND_RESCUE", "MEDICAL", "SECURITY", "FACILITIES"],
}

# Severities that additionally trigger community-wide communications.
_ESCALATION_SEVERITIES = frozenset({"high", "critical"})


def normalize_department(value: Optional[str]) -> Optional[str]:
    """Return the canonical UPPERCASE department code, or None if invalid."""
    if not value:
        return None
    code = str(value).strip().upper()
    return code if code in DEPARTMENT_SET else None


def register_department(code: Optional[str], label: Optional[str] = None) -> Optional[str]:
    """Register an admin-created code for auth/event scope resolution."""
    normalized = str(code or "").strip().upper().replace(" ", "_")
    if not normalized:
        return None
    DEPARTMENT_SET.add(normalized)
    if label:
        DEPARTMENT_LABELS.setdefault(normalized, label)
    return normalized


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
    incident_type: Optional[str], severity: Optional[str] = None,
    disaster_type: Optional[str] = None,
) -> List[str]:
    """Departments that should be engaged for an incident category.

    High/critical severities additionally engage COMMUNICATION for community-wide
    alerting. Returns a de-duplicated list preserving priority order.
    """
    key = (disaster_type or incident_type or "unknown").strip().lower()
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
