from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_principal
from backend.database.database import get_db
from backend.database.models import NotificationDB
from backend.models.notification import NotificationRead
from backend.services.departments import normalize_department

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


def _visible(notification: NotificationDB, principal) -> bool:
    if principal.is_privileged:
        return notification.recipient_type == "admin"
    if principal.is_department:
        return notification.recipient_type == "department" and notification.department == normalize_department(principal.department)
    return notification.recipient_type == "user" and notification.recipient_id == str(principal.id)


@router.get("", response_model=List[NotificationRead])
def get_notifications(db: Session = Depends(get_db), principal=Depends(get_current_principal)):
    rows = db.query(NotificationDB).order_by(NotificationDB.created_at.desc()).limit(100).all()
    return [row for row in rows if _visible(row, principal)]


@router.post("/read-all", response_model=List[NotificationRead])
def mark_all_notifications_read(db: Session = Depends(get_db), principal=Depends(get_current_principal)):
    rows = db.query(NotificationDB).all()
    visible = [row for row in rows if _visible(row, principal)]
    for row in visible:
        row.read = 1
    db.commit()
    return visible


@router.post("/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(notification_id: int, db: Session = Depends(get_db), principal=Depends(get_current_principal)):
    row = db.query(NotificationDB).filter(NotificationDB.id == notification_id).first()
    if row is None or not _visible(row, principal):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    row.read = 1
    db.commit()
    db.refresh(row)
    return row
