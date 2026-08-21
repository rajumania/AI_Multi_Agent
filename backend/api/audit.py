import json
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.services.audit_service import audit_service
from backend.models.audit import AuditLogRead

router = APIRouter(prefix="/api/v1/activity", tags=["Audit & Activity Logs"])


def serialize_audit_log(entry) -> Dict[str, Any]:
    return {
        "id": entry.id,
        "incident_id": entry.incident_id,
        "plan_id": entry.plan_id,
        "action_type": entry.action_type,
        "actor": entry.actor,
        "description": entry.description,
        "details": json.loads(entry.details) if entry.details and isinstance(entry.details, str) else None,
        "timestamp": entry.timestamp,
    }


@router.get("", response_model=List[AuditLogRead])
def get_activity_timeline(
    incident_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Retrieve real audit timeline events for live command center telemetry.
    """
    logs = audit_service.get_logs(incident_id=incident_id, limit=limit, db=db)
    return [serialize_audit_log(l) for l in logs]


@router.get("/{incident_id}", response_model=List[AuditLogRead])
def get_incident_activity(
    incident_id: str,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Retrieve audit history specific to one incident dossier.
    """
    logs = audit_service.get_logs(incident_id=incident_id, limit=limit, db=db)
    return [serialize_audit_log(l) for l in logs]
