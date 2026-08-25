"""Targeted lifecycle notifications built on the existing notification table/socket."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

from backend.database.database import SessionLocal
from backend.database.models import IncidentDB, NotificationDB
from backend.services.event_engine import event_engine


USER_MESSAGES: Dict[str, tuple[str, str, str]] = {
    "incident_created": ("Emergency report received", "Your emergency report has been received.", "info"),
    "incident_assessed": ("Emergency report assessed", "Your emergency report has been assessed.", "info"),
    "approval_granted": ("Emergency response authorized", "Emergency response has been authorized.", "alert"),
    "approval_approved": ("Emergency response authorized", "Emergency response has been authorized.", "alert"),
    "response_dispatched": ("Response teams dispatched", "Response teams have been dispatched.", "alert"),
    "dispatch_started": ("Response teams dispatched", "Response teams have been dispatched.", "alert"),
    "incident_resolved": ("Emergency incident resolved", "Your emergency incident has been resolved.", "info"),
}


def _create_targeted(db, *, recipient_type: str, recipient_id: Optional[str], department: Optional[str], incident_id: str, title: str, message: str, level: str) -> Optional[NotificationDB]:
    existing = db.query(NotificationDB).filter(
        NotificationDB.recipient_type == recipient_type,
        NotificationDB.recipient_id == recipient_id,
        NotificationDB.incident_id == incident_id,
        NotificationDB.title == title,
        NotificationDB.message == message,
    ).first()
    if existing:
        return None
    row = NotificationDB(
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        department=department,
        incident_id=incident_id,
        title=title,
        message=message,
        level=level,
        read=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()
    return row


def _publish(row: NotificationDB, *, incident_id: str, department: Optional[str] = None) -> None:
    event_engine.publish_event(
        "notification_created",
        incident_id,
        {
            "event_name": "notification_created",
            "event": "notification_created",
            "notification_id": row.id,
            "recipient_type": row.recipient_type,
            "recipient_id": row.recipient_id,
            "department": department or row.department,
            "incident_id": incident_id,
            "title": row.title,
            "message": row.message,
            "level": row.level,
        },
        db=None,
    )


def handle_lifecycle_event(incident_id: str, payload: dict, _event_db=None) -> None:
    event_name = str(payload.get("event_name") or "")
    if event_name not in USER_MESSAGES and event_name not in {"dept_on_scene"}:
        return
    db = SessionLocal()
    rows = []
    try:
        incident = db.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
        if incident is None:
            return
        if event_name == "dept_on_scene":
            if not incident.user_id:
                return
            department = str(payload.get("department") or "response").upper()
            row = _create_targeted(
                db, recipient_type="user", recipient_id=str(incident.user_id), department=department,
                incident_id=incident_id, title="Response team on scene",
                message=f"A {department} response team has arrived at the reported location.", level="alert",
            )
            if row:
                rows.append((row, department))
        else:
            title, message, level = USER_MESSAGES[event_name]
            if incident.user_id:
                row = _create_targeted(
                    db, recipient_type="user", recipient_id=str(incident.user_id), department=None,
                    incident_id=incident_id, title=title, message=message, level=level,
                )
                if row:
                    rows.append((row, None))
            operator_row = _create_targeted(
                db, recipient_type="admin", recipient_id=None, department=None,
                incident_id=incident_id, title=title, message=message, level=level,
            )
            if operator_row:
                rows.append((operator_row, None))
        if rows:
            db.commit()
        for row, department in rows:
            _publish(row, incident_id=incident_id, department=department)
    except Exception as exc:
        db.rollback()
        print(f"[NotificationService] lifecycle notification failed: {type(exc).__name__}", flush=True)
    finally:
        db.close()


def register_lifecycle_notifications() -> None:
    for event_name in (*USER_MESSAGES.keys(), "dept_on_scene"):
        event_engine.subscribe(event_name, handle_lifecycle_event)

