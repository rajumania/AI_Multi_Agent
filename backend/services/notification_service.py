"""Targeted lifecycle notifications built on the existing notification table/socket."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.database.database import SessionLocal
from backend.database.models import IncidentDB, NotificationDB, RiskPredictionDB
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


def build_operational_details(db, incident: IncidentDB, *, department: Optional[str], response_status: str, reason: Optional[str] = None, approval_status: str = "approved") -> dict[str, Any]:
    """Build safe, structured notification context from persisted incident data."""
    detection: dict[str, Any] = {}
    try:
        parsed = json.loads(incident.detection_evidence or "{}")
        detection = parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    latest = None
    if incident.zone_id:
        latest = db.query(RiskPredictionDB).filter(RiskPredictionDB.zone_id == incident.zone_id).order_by(RiskPredictionDB.valid_from.desc()).first()
    recommendations = detection.get("department_recommendations") or []
    selected = next((item for item in recommendations if str(item.get("department", "")).upper() == str(department or "").upper()), None) if isinstance(recommendations, list) else None
    evidence_summary = detection.get("supporting_evidence") if isinstance(detection.get("supporting_evidence"), list) else []
    image = detection.get("image_analysis") if isinstance(detection.get("image_analysis"), dict) else {}
    if image.get("status") and image.get("status") != "NOT_PROVIDED":
        evidence_summary = [*evidence_summary, f"Image evidence: {image.get('status')}"]
    return {
        "incident_id": incident.incident_id,
        "department": department,
        "severity": incident.severity,
        "hazard_type": incident.disaster_type or incident.category or incident.incident_type,
        "risk_score": float(latest.risk_score) if latest and latest.risk_score is not None else None,
        "risk_level": latest.risk_level if latest and latest.risk_level else incident.severity,
        "latitude": incident.latitude,
        "longitude": incident.longitude,
        "location_label": incident.location,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "evidence_summary": [str(item) for item in evidence_summary[:12]],
        "targeting_reason": reason or (selected.get("reason") if isinstance(selected, dict) else None) or "Department was selected by the existing evidence-based routing policy.",
        "targeting_confidence": selected.get("confidence") if isinstance(selected, dict) else None,
        "approval_status": approval_status,
        "response_status": response_status,
    }


def _create_targeted(db, *, recipient_type: str, recipient_id: Optional[str], department: Optional[str], incident_id: str, title: str, message: str, level: str, priority: Optional[str] = None, event_key: Optional[str] = None, details: Optional[dict[str, Any]] = None) -> Optional[NotificationDB]:
    if event_key and db.query(NotificationDB).filter(NotificationDB.event_key == event_key).first():
        return None
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
        priority=priority or level,
        lifecycle_status="CREATED",
        event_key=event_key,
        details_json=json.dumps(details or {}, default=str, separators=(",", ":")),
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
            "priority": row.priority,
            "lifecycle_status": row.lifecycle_status,
            "delivered_at": row.delivered_at.isoformat() if row.delivered_at else None,
            "details": _safe_details(row.details_json),
        },
        db=None,
    )


def _safe_details(value: Optional[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        parsed = {}
    return parsed if isinstance(parsed, dict) else {}


def _notification_event_payload(row: NotificationDB, *, status: Optional[str] = None) -> dict[str, Any]:
    details = _safe_details(row.details_json)
    event_name = {"DELIVERED": "notification_delivered", "FAILED": "notification_failed"}.get(status, "notification_read")
    event_label = {"DELIVERED": "NOTIFICATION_DELIVERED", "FAILED": "NOTIFICATION_FAILED"}.get(status, "NOTIFICATION_READ")
    return {
        "event_name": event_name,
        "event": event_label,
        "notification_id": row.id,
        "incident_id": row.incident_id,
        "department": row.department,
        "recipient_type": row.recipient_type,
        "recipient_id": row.recipient_id,
        "title": row.title,
        "message": row.message,
        "level": row.level,
        "priority": row.priority,
        "lifecycle_status": status or row.lifecycle_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **details,
    }


def mark_notification_delivered(notification_id: int, scope) -> bool:
    """Acknowledge delivery only after an authorized socket received the row."""
    db = SessionLocal()
    try:
        row = db.query(NotificationDB).filter(NotificationDB.id == int(notification_id)).first()
        if row is None:
            return False
        allowed = bool(getattr(scope, "privileged", False))
        if getattr(scope, "subject_type", None) == "department":
            allowed = row.recipient_type == "department" and str(row.department or "").upper() == str(getattr(scope, "department", "")).upper()
        elif getattr(scope, "subject_type", None) == "user":
            allowed = row.recipient_type in {"user", "community"} and (row.recipient_type == "community" or str(row.recipient_id) == str(getattr(scope, "user_id", "")))
        if not allowed:
            return False
        if row.lifecycle_status not in {"READ", "DELIVERED"}:
            row.lifecycle_status = "DELIVERED"
            row.delivered_at = datetime.now(timezone.utc)
            db.commit()
            event_engine.publish_event("notification_delivered", row.incident_id or "system", _notification_event_payload(row, status="DELIVERED"), db=None)
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


def mark_notification_failed(notification_id: int, scope) -> bool:
    """Record a failed socket send without changing the durable audience."""
    db = SessionLocal()
    try:
        row = db.query(NotificationDB).filter(NotificationDB.id == int(notification_id)).first()
        if row is None:
            return False
        allowed = bool(getattr(scope, "privileged", False))
        if getattr(scope, "subject_type", None) == "department":
            allowed = row.recipient_type == "department" and str(row.department or "").upper() == str(getattr(scope, "department", "")).upper()
        elif getattr(scope, "subject_type", None) == "user":
            allowed = row.recipient_type == "user" and str(row.recipient_id) == str(getattr(scope, "user_id", ""))
        if not allowed or row.lifecycle_status in {"READ", "FAILED"}:
            return False
        row.lifecycle_status = "FAILED"
        db.commit()
        event_engine.publish_event("notification_failed", row.incident_id or "system", _notification_event_payload(row, status="FAILED"), db=None)
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


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
                event_key=f"user:{incident_id}:dept_on_scene:{department}",
                details=build_operational_details(db, incident, department=department, response_status="ON_SCENE", approval_status="approved"),
            )
            if row:
                rows.append((row, department))
        else:
            title, message, level = USER_MESSAGES[event_name]
            if incident.user_id:
                row = _create_targeted(
                    db, recipient_type="user", recipient_id=str(incident.user_id), department=None,
                    incident_id=incident_id, title=title, message=message, level=level,
                    event_key=f"user:{incident_id}:{event_name}",
                    details=build_operational_details(db, incident, department=None, response_status=event_name.upper(), approval_status="approved" if "approval" in event_name or "dispatch" in event_name else "pending"),
                )
                if row:
                    rows.append((row, None))
            operator_row = _create_targeted(
                db, recipient_type="admin", recipient_id=None, department=None,
                incident_id=incident_id, title=title, message=message, level=level,
                event_key=f"admin:{incident_id}:{event_name}",
                details=build_operational_details(db, incident, department=None, response_status=event_name.upper(), approval_status="approved" if "approval" in event_name or "dispatch" in event_name else "pending"),
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
