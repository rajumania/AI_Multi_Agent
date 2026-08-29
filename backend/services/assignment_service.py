"""Backend-owned department assignment lifecycle for Phase 6.

Assignments are created only after an approved response plan is dispatched.
Every later state change is an explicit authenticated department action; this
module never schedules or simulates a transition.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.database.models import CampusResourceDB, DepartmentResponseDB, IncidentDB, NotificationDB
from backend.services.audit_service import audit_service
from backend.services.departments import departments_for_incident, normalize_department
from backend.services.event_engine import event_engine
from backend.services.notification_service import build_operational_details


NOTIFIED = "NOTIFIED"
ACCEPTED = "ACCEPTED"
DECLINED = "DECLINED"
TEAM_ASSIGNED = "TEAM_ASSIGNED"
EN_ROUTE = "EN_ROUTE"
ON_SCENE = "ON_SCENE"
COMPLETED = "COMPLETED"

TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    NOTIFIED: (ACCEPTED, DECLINED),
    ACCEPTED: (TEAM_ASSIGNED,),
    TEAM_ASSIGNED: (EN_ROUTE,),
    EN_ROUTE: (ON_SCENE,),
    ON_SCENE: (COMPLETED,),
    DECLINED: (),
    COMPLETED: (),
}

EVENTS = {
    NOTIFIED: "department_notified",
    ACCEPTED: "dept_assignment_accepted",
    DECLINED: "dept_assignment_declined",
    TEAM_ASSIGNED: "dept_team_assigned",
    EN_ROUTE: "dept_en_route",
    ON_SCENE: "dept_on_scene",
    COMPLETED: "dept_assignment_completed",
}

TITLES = {
    NOTIFIED: "Department assignment notified",
    ACCEPTED: "Department assignment accepted",
    DECLINED: "Department assignment declined",
    TEAM_ASSIGNED: "Response team assigned",
    EN_ROUTE: "Response team en route",
    ON_SCENE: "Response team on scene",
    COMPLETED: "Department response completed",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _actor(principal=None, fallback: str = "System") -> str:
    if principal is None:
        return fallback
    return principal.full_name or principal.email or principal.username or str(principal.id)


def _required_departments(incident: IncidentDB) -> List[str]:
    try:
        values = json.loads(incident.required_departments) if incident.required_departments else []
    except (TypeError, ValueError):
        values = []
    result: List[str] = []
    for value in values if isinstance(values, list) else []:
        department = normalize_department(value)
        if department and department not in result:
            result.append(department)
    return result or departments_for_incident(incident.incident_type, incident.severity)


def _add_notification(
    db: Session,
    *,
    incident: IncidentDB,
    department: str,
    status_name: str,
    recipient_type: str,
    recipient_id: Optional[str],
    now: datetime,
    event_key: Optional[str] = None,
    title: Optional[str] = None,
    message: Optional[str] = None,
    level: Optional[str] = None,
    priority: Optional[str] = None,
    details: Optional[dict] = None,
) -> Optional[NotificationDB]:
    event_key = event_key or f"{recipient_type}:{incident.incident_id}:{department}:{status_name}"
    if db.query(NotificationDB).filter(NotificationDB.event_key == event_key).first():
        return None
    notification_priority = priority or {NOTIFIED: "critical", ACCEPTED: "high", DECLINED: "high", TEAM_ASSIGNED: "medium", EN_ROUTE: "high", ON_SCENE: "high", COMPLETED: "low"}.get(status_name, "medium")
    row = NotificationDB(
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        department=department,
        incident_id=incident.incident_id,
        title=title or TITLES[status_name],
        message=message or f"{department} assignment for incident {incident.incident_id}: {status_name}.",
        level=level or notification_priority,
        read=0,
        created_at=now,
        priority=notification_priority,
        lifecycle_status="CREATED",
        event_key=event_key,
        details_json=json.dumps(details or build_operational_details(db, incident, department=department, response_status=status_name, approval_status="approved"), default=str, separators=(",", ":")),
    )
    db.add(row)
    return row


def _emit_notification_created(
    assignment: DepartmentResponseDB,
    notification: NotificationDB,
    actor: str,
    now: datetime,
) -> None:
    """Publish the persisted assignment notification over the existing WS.

    The database row is created before this broadcast. The event is additive
    and broadcast-only; the REST notification endpoint remains the source of
    truth and owns read state.
    """
    event_engine.publish_event(
        "notification_created",
        assignment.incident_id,
        {
            "event_name": "notification_created",
            "event": "notification_created",
            "notification_id": notification.id,
            "department": assignment.department,
            "status": assignment.status,
            "title": notification.title,
            "message": notification.message,
            "level": notification.level,
            "recipient_type": notification.recipient_type,
            "recipient_id": notification.recipient_id,
            "assignment_id": assignment.id,
            "actor": actor,
            "timestamp": now.isoformat(),
            "priority": notification.priority,
            "lifecycle_status": notification.lifecycle_status,
            "delivered_at": notification.delivered_at.isoformat() if notification.delivered_at else None,
            **_notification_details(notification),
        },
        db=None,
    )


def _notification_details(notification: NotificationDB) -> dict:
    try:
        value = json.loads(notification.details_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        value = {}
    return value if isinstance(value, dict) else {}


def _emit(
    assignment: DepartmentResponseDB,
    event_name: str,
    actor: str,
    now: datetime,
    *,
    previous_status: Optional[str] = None,
) -> None:
    try:
        resources = json.loads(assignment.assigned_resources or "[]")
    except (TypeError, ValueError):
        resources = []
    event_engine.publish_event(
        event_name,
        assignment.incident_id,
        {
            "event_name": event_name,
            "event": event_name,
            "assignment_id": assignment.id,
            "incident_id": assignment.incident_id,
            "department": assignment.department,
            "status": assignment.status,
            "previous_status": previous_status,
            "actor": actor,
            "timestamp": now.isoformat(),
            "updated_at": now.isoformat(),
            "message": assignment.message,
            "assigned_resources": resources,
        },
        db=None,
    )


def create_required_assignments(incident: IncidentDB, db: Session, actor: str = "System") -> List[DepartmentResponseDB]:
    """Create NOTIFIED rows for required departments, idempotently."""
    created: List[DepartmentResponseDB] = []
    notifications: List[Tuple[DepartmentResponseDB, NotificationDB]] = []
    now = _now()
    for department in _required_departments(incident):
        existing = db.query(DepartmentResponseDB).filter(
            DepartmentResponseDB.incident_id == incident.incident_id,
            DepartmentResponseDB.department == department,
        ).first()
        if existing:
            continue
        assignment = DepartmentResponseDB(
            incident_id=incident.incident_id,
            department=department,
            status=NOTIFIED,
            accepted=0,
            responder=None,
            assigned_resources=json.dumps([]),
            created_at=now,
            updated_at=now,
        )
        db.add(assignment)
        db.flush()
        department_notification = _add_notification(
            db,
            incident=incident, department=department, status_name=NOTIFIED,
            recipient_type="department", recipient_id=department, now=now,
        )
        _add_notification(
            db,
            incident=incident, department=department, status_name=NOTIFIED,
            recipient_type="admin", recipient_id=None, now=now,
        )
        audit_service.log(
            action_type="department_notified",
            description=f"{department} notified for incident {incident.incident_id}.",
            incident_id=incident.incident_id,
            actor=actor,
            details={"department": department, "previous_status": None, "new_status": NOTIFIED, "assignment_id": assignment.id},
            db=db,
        )
        created.append(assignment)
        if department_notification:
            notifications.append((assignment, department_notification))
    # The approval endpoint owns the transaction containing the incident,
    # assignments, audit entries, and notification rows. Commit before any
    # socket frame is scheduled so a portal acknowledgement can always see
    # the durable notification row.
    if created:
        db.commit()
        for assignment, notification in notifications:
            _emit_notification_created(assignment, notification, actor, now)
        for assignment in created:
            _emit(assignment, EVENTS[NOTIFIED], actor, now, previous_status=None)
    return created


def notify_replan_approval(incident: IncidentDB, plan_id: str, db: Session, actor: str = "System") -> List[NotificationDB]:
    """Notify existing routed departments when a new plan is approved.

    Assignment rows remain idempotent across plans, but a re-plan is a new
    approval-gated operational decision and therefore needs a new durable
    notification. The plan id makes the event key unique without duplicating
    department assignments or broadening the audience.
    """
    notifications: List[NotificationDB] = []
    now = _now()
    assignments = db.query(DepartmentResponseDB).filter(DepartmentResponseDB.incident_id == incident.incident_id).order_by(DepartmentResponseDB.department.asc()).all()
    for assignment in assignments:
        department = normalize_department(assignment.department)
        if not department:
            continue
        message = f"Updated approved response plan {plan_id} for incident {incident.incident_id} is ready for {department}."
        details = build_operational_details(db, incident, department=department, response_status="REPLAN_APPROVED", approval_status="approved")
        department_notification = _add_notification(
            db,
            incident=incident,
            department=department,
            status_name=NOTIFIED,
            recipient_type="department",
            recipient_id=department,
            now=now,
            event_key=f"department:{incident.incident_id}:{department}:replan:{plan_id}",
            title="Updated response plan approved",
            message=message,
            level="critical",
            priority="critical",
            details={**details, "plan_id": plan_id, "response_status": "REPLAN_APPROVED"},
        )
        _add_notification(
            db,
            incident=incident,
            department=department,
            status_name=NOTIFIED,
            recipient_type="admin",
            recipient_id=None,
            now=now,
            event_key=f"admin:{incident.incident_id}:{department}:replan:{plan_id}",
            title="Updated response plan approved",
            message=message,
            level="critical",
            priority="critical",
            details={**details, "plan_id": plan_id, "response_status": "REPLAN_APPROVED"},
        )
        if department_notification:
            notifications.append(department_notification)
    if notifications:
        db.commit()
        for notification in notifications:
            assignment = next((item for item in assignments if normalize_department(item.department) == normalize_department(notification.department)), None)
            if assignment:
                _emit_notification_created(assignment, notification, actor, now)
    return notifications


def list_for_incident(incident_id: str, db: Session, principal) -> List[DepartmentResponseDB]:
    query = db.query(DepartmentResponseDB).filter(DepartmentResponseDB.incident_id == incident_id)
    if not principal.is_privileged:
        department = normalize_department(principal.department)
        if not department:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No department assigned.")
        query = query.filter(DepartmentResponseDB.department == department)
    return query.order_by(DepartmentResponseDB.created_at.asc()).all()


def list_for_department(db: Session, principal) -> List[DepartmentResponseDB]:
    if principal.is_privileged:
        return db.query(DepartmentResponseDB).order_by(DepartmentResponseDB.updated_at.desc()).all()
    department = normalize_department(principal.department)
    if not department:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No department assigned.")
    return db.query(DepartmentResponseDB).filter(
        DepartmentResponseDB.department == department
    ).order_by(DepartmentResponseDB.updated_at.desc()).all()


def transition(incident_id: str, department_value: str, target: str, db: Session, principal, *, message: Optional[str] = None, resource_ids: Optional[List[str]] = None) -> DepartmentResponseDB:
    department = normalize_department(department_value)
    if not department:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown department.")
    if not principal.is_privileged and normalize_department(principal.department) != department:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only modify your own department.")

    assignment = db.query(DepartmentResponseDB).filter(
        DepartmentResponseDB.incident_id == incident_id,
        DepartmentResponseDB.department == department,
    ).first()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department assignment not found.")
    incident = db.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")

    previous = (assignment.status or NOTIFIED).upper()
    if target not in TRANSITIONS.get(previous, ()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Invalid assignment transition {previous} -> {target}.")

    selected = list(resource_ids or [])
    if target == TEAM_ASSIGNED:
        if not selected and not message:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assign a team name or at least one team resource.")
        if selected:
            resources = db.query(CampusResourceDB).filter(CampusResourceDB.resource_id.in_(selected)).all()
            if len(resources) != len(set(selected)):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more assigned resources do not exist.")
            if any(normalize_department(resource.department) != department for resource in resources):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Resources must belong to the assigned department.")

    now = _now()
    actor = _actor(principal)
    assignment.status = target
    assignment.accepted = 1 if target != DECLINED else 0
    assignment.responder = actor
    assignment.message = message
    assignment.updated_at = now
    if target == TEAM_ASSIGNED:
        assignment.assigned_resources = json.dumps(selected)
    db.commit()

    audit_service.log(
        action_type=EVENTS[target],
        description=f"{department} assignment transitioned from {previous} to {target}.",
        incident_id=incident_id,
        actor=actor,
        details={
            "assignment_id": assignment.id,
            "department": department,
            "previous_status": previous,
            "new_status": target,
            "assigned_resources": selected or json.loads(assignment.assigned_resources or "[]"),
            "timestamp": now.isoformat(),
        },
        db=db,
    )
    department_notification = _add_notification(
        db,
        incident=incident, department=department, status_name=target,
        recipient_type="department", recipient_id=department, now=now,
    )
    _add_notification(
        db,
        incident=incident, department=department, status_name=target,
        recipient_type="admin", recipient_id=None, now=now,
    )
    db.commit()
    db.refresh(assignment)
    if department_notification:
        _emit_notification_created(assignment, department_notification, actor, now)
    _emit(assignment, EVENTS[target], actor, now, previous_status=previous)
    if target == ON_SCENE and department == "TRANSPORT":
        try:
            assigned = json.loads(assignment.assigned_resources or "[]")
        except (TypeError, ValueError):
            assigned = []
        event_engine.publish_event(
            "transport_arrived",
            assignment.incident_id,
            {
                "event_name": "transport_arrived",
                "event": "transport_arrived",
                "incident_id": assignment.incident_id,
                "assignment_id": assignment.id,
                "department": department,
                "resource_id": assigned[0] if assigned else None,
                "status": target,
                "actor": actor,
                "timestamp": now.isoformat(),
            },
        )
    if target == EN_ROUTE and department == "TRANSPORT":
        # GPS/route support observes the human-controlled lifecycle.  It never
        # changes the assignment state and simply waits for the first real GPS
        # point when no telemetry is available yet.
        try:
            from backend.services.transport_tracking_service import ensure_active_route
            ensure_active_route(db, assignment.id)
        except Exception:
            pass
    return assignment
