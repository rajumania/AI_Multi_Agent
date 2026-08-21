import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.database.database import SessionLocal
from backend.database.models import AuditLogDB


class AuditService:
    """
    Centralized Audit Trail Service:
    Records every critical lifecycle event for compliance, human review, and replayability.
    """

    def log(
        self,
        action_type: str,
        description: str,
        incident_id: Optional[str] = None,
        plan_id: Optional[str] = None,
        actor: str = "system",
        details: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None
    ) -> AuditLogDB:
        """Persists an audit event to SQLite database."""
        should_close = False
        if db is None:
            db = SessionLocal()
            should_close = True

        try:
            entry = AuditLogDB(
                incident_id=incident_id,
                plan_id=plan_id,
                action_type=action_type,
                actor=actor,
                description=description,
                details=json.dumps(details) if details else None,
                timestamp=datetime.now(timezone.utc)
            )
            db.add(entry)
            db.commit()
            db.refresh(entry)
            return entry
        finally:
            if should_close:
                db.close()

    def get_logs(
        self,
        incident_id: Optional[str] = None,
        limit: int = 50,
        db: Optional[Session] = None
    ) -> List[AuditLogDB]:
        """Retrieves audit trail entries, optionally filtered by incident."""
        should_close = False
        if db is None:
            db = SessionLocal()
            should_close = True

        try:
            query = db.query(AuditLogDB)
            if incident_id:
                query = query.filter(AuditLogDB.incident_id == incident_id)
            return query.order_by(desc(AuditLogDB.timestamp)).limit(limit).all()
        finally:
            if should_close:
                db.close()


audit_service = AuditService()
