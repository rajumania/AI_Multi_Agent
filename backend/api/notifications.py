import json
from datetime import datetime, timezone
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_principal
from backend.database.database import get_db
from backend.database.models import NotificationDB
from backend.models.notification import NotificationRead
from backend.services.departments import normalize_department

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


alerts_router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"])


def _visible(notification: NotificationDB, principal) -> bool:
    if principal.is_privileged:
        return notification.recipient_type == "admin"
    if principal.is_department:
        return notification.recipient_type == "department" and normalize_department(notification.department) == normalize_department(principal.department)
    return (
        (notification.recipient_type == "user" and notification.recipient_id == str(principal.id))
        or (notification.recipient_type == "community" and notification.audience == "community")
    )


def _details(row: NotificationDB) -> dict[str, Any]:
    try:
        value = json.loads(row.details_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        value = {}
    return value if isinstance(value, dict) else {}


def _serialize(row: NotificationDB) -> dict[str, Any]:
    return {
        "id": row.id, "recipient_type": row.recipient_type,
        "department": row.department, "incident_id": row.incident_id,
        "title": row.title, "message": row.message, "level": row.level,
        "read": row.read, "created_at": row.created_at,
        "alert_type": row.alert_type, "audience": row.audience,
        "region_id": row.region_id, "zone_id": row.zone_id,
        "expires_at": row.expires_at, "is_demo": row.is_demo,
        "priority": row.priority or row.level or "medium",
        "lifecycle_status": row.lifecycle_status or ("READ" if row.read else "CREATED"),
        "delivered_at": row.delivered_at, "read_at": row.read_at,
        "details": _details(row),
    }


@router.get("", response_model=List[NotificationRead])
def get_notifications(db: Session = Depends(get_db), principal=Depends(get_current_principal)):
    rows = db.query(NotificationDB).order_by(NotificationDB.created_at.desc()).limit(100).all()
    return [_serialize(row) for row in rows if _visible(row, principal)]


@alerts_router.get("", response_model=List[NotificationRead])
def get_alerts(db: Session = Depends(get_db), principal=Depends(get_current_principal)):
    """Alert-compatible read alias over the existing persisted notification system."""
    rows = db.query(NotificationDB).order_by(NotificationDB.created_at.desc()).limit(100).all()
    return [_serialize(row) for row in rows if _visible(row, principal)]


@router.post("/read-all", response_model=List[NotificationRead])
def mark_all_notifications_read(db: Session = Depends(get_db), principal=Depends(get_current_principal)):
    rows = db.query(NotificationDB).all()
    visible = [row for row in rows if _visible(row, principal)]
    now = datetime.now(timezone.utc)
    for row in visible:
        row.read = 1
        row.lifecycle_status = "READ"
        row.read_at = now
    db.commit()
    for row in visible:
        _publish_read(row)
    return [_serialize(row) for row in visible]


@router.post("/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(notification_id: int, db: Session = Depends(get_db), principal=Depends(get_current_principal)):
    row = db.query(NotificationDB).filter(NotificationDB.id == notification_id).first()
    if row is None or not _visible(row, principal):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    row.read = 1
    row.lifecycle_status = "READ"
    row.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    _publish_read(row)
    return _serialize(row)


def _publish_read(row: NotificationDB) -> None:
    from backend.services.event_engine import event_engine
    from backend.services.notification_service import _notification_event_payload
    event_engine.publish_event(
        "notification_read", row.incident_id or "system",
        _notification_event_payload(row, status="READ"), db=None,
    )
