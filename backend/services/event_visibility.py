"""WebSocket event visibility rules for CampusFlow AI (Increment 1).

Pure, DB-free logic that decides which live events a given connection may
receive. This is the real-time counterpart to the REST RBAC guards: the socket
is authenticated, each connection carries a :class:`ConnectionScope`, and every
outbound event is filtered against that scope.

Delivery policy:
  * Admin / operator (privileged)  -> receive everything (command center).
  * Department staff               -> only events for incidents routed to their
                                       department.
  * Citizen (user portal)          -> only *user-safe* status events, and only
                                       for incidents they themselves reported.
                                       They never receive internal agent
                                       reasoning, tool traces, or approvals.
  * Guest (no/invalid token, and anonymous-admin disabled) -> nothing.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Set

from backend.services.departments import normalize_department

# Events a citizen is allowed to see: high-level progress only. Deliberately
# excludes internal reasoning/coordination events such as agent_started,
# tool_started/…, trace_updated, approval_requested/granted/rejected, and the
# various provider_/gps_ operational telemetry events.
USER_SAFE_EVENTS = frozenset({
    "incident_created",
    "assessment_started",
    "incident_assessed",
    "assessment_failed",
    "incident_updated",
    "response_status_changed",
    "dispatch_started",
    "response_dispatched",
    "resource_dispatched",
    "vehicle_arrived",
    "monitoring_started",
    "incident_resolved",
    "incident_closed",
    "in_app_alert_available",
    "notification_created",
})

# Assignment events carry a concrete department in their payload. Department
# staff may receive incident-level operational events for incidents routed to
# them, but they must never receive another department's assignment stream.
# This is enforced here, at the WebSocket boundary, rather than by trusting a
# department portal to hide rows after delivery.
DEPARTMENT_SCOPED_EVENTS = frozenset({
    "department_notified",
    "dept_assignment_accepted",
    "dept_assignment_declined",
    "dept_team_assigned",
    "dept_en_route",
    "dept_on_scene",
    "dept_assignment_completed",
    "notification_created",
    "transport_location_updated",
    "transport_route_created",
    "transport_route_updated",
    "transport_eta_updated",
    "transport_arrived",
    "road_condition_updated",
    "route_selected",
    "route_blocked",
    "route_recalculated",
    "vehicle_location_updated",
    "vehicle_arrived",
})

TRANSPORT_PRIVATE_EVENTS = frozenset({
    "transport_location_updated",
    "transport_route_created",
    "transport_route_updated",
    "transport_eta_updated",
    "transport_arrived",
    "route_selected",
    "route_blocked",
    "route_recalculated",
    "vehicle_location_updated",
    "vehicle_arrived",
})


@dataclass
class ConnectionScope:
    """The authorization scope attached to a single WebSocket connection."""

    subject_type: str  # "operator" | "admin" | "department" | "user" | "guest"
    role: str
    privileged: bool = False
    user_id: Optional[str] = None
    department: Optional[str] = None


def guest_scope() -> ConnectionScope:
    return ConnectionScope(subject_type="guest", role="guest")


def operator_scope() -> ConnectionScope:
    """Full-access scope used for the legacy anonymous operator console."""
    return ConnectionScope(subject_type="operator", role="operator", privileged=True)


def scope_from_principal(principal) -> ConnectionScope:
    """Translate an authenticated Principal into a connection scope."""
    if principal is None:
        return guest_scope()
    if principal.is_privileged:
        return ConnectionScope(
            subject_type=principal.subject_type or "operator",
            role=principal.role,
            privileged=True,
        )
    if principal.is_department:
        return ConnectionScope(
            subject_type="department",
            role=principal.role,
            department=normalize_department(principal.department),
        )
    return ConnectionScope(
        subject_type="user",
        role=principal.role,
        user_id=str(principal.id),
    )


def should_deliver(
    scope: Optional[ConnectionScope],
    event_name: Optional[str],
    incident_scope: Dict[str, Any],
    event_payload: Optional[Dict[str, Any]] = None,
) -> bool:
    """Decide whether ``event_name`` should reach a connection with ``scope``.

    ``incident_scope`` describes the incident the event pertains to:
        {"user_id": Optional[str], "departments": Set[str]}

    ``event_payload`` is optional for backwards-compatible callers. When an
    assignment event includes a department, that department is checked against
    the connection scope before delivery.
    """
    if scope is None or scope.subject_type == "guest":
        return False
    if scope.privileged:
        return True

    departments: Set[str] = incident_scope.get("departments") or set()
    owner: Optional[str] = incident_scope.get("user_id")

    if scope.subject_type == "department":
        if scope.department is None or scope.department not in departments:
            return False
        # An incident can legitimately involve several departments. Assignment
        # events are still private to the department named by the event.
        if event_name in DEPARTMENT_SCOPED_EVENTS and event_payload:
            if event_name == "notification_created" and event_payload.get("recipient_type") != "department":
                return False
            event_department = normalize_department(event_payload.get("department"))
            if event_department is not None:
                return event_department == scope.department
            if event_name in TRANSPORT_PRIVATE_EVENTS:
                return False
        return True

    if scope.subject_type == "user":
        if event_name not in USER_SAFE_EVENTS:
            return False
        if owner is None or owner != scope.user_id:
            return False
        if event_name == "notification_created" and event_payload:
            return (
                event_payload.get("recipient_type") == "user"
                and str(event_payload.get("recipient_id")) == str(scope.user_id)
            )
        return True

    return False
