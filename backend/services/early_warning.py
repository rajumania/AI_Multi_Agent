"""Threshold-based early warnings backed by the existing notifications system."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.config import settings
from backend.database.models import NotificationDB, RiskPredictionDB
from backend.services.event_engine import event_engine


class EarlyWarningService:
    def evaluate(self, db: Session, prediction: RiskPredictionDB, zone_name: str) -> Optional[NotificationDB]:
        level = str(prediction.risk_level).lower()
        if level not in {"high", "critical"}:
            return None
        now = datetime.now(timezone.utc)
        cooldown = now - timedelta(minutes=max(1, int(settings.RISK_ALERT_COOLDOWN_MINUTES)))
        existing = db.query(NotificationDB).filter(
            NotificationDB.alert_type == "early_warning",
            NotificationDB.zone_id == prediction.zone_id,
            NotificationDB.created_at >= cooldown,
        ).order_by(NotificationDB.created_at.desc()).first()
        current_rank = {"high": 1, "critical": 2}[level]
        existing_rank = {"high": 1, "critical": 2}.get(str(existing.level).lower(), 0) if existing else 0
        # A severity escalation (HIGH -> CRITICAL) is meaningful; repeated
        # predictions at the same or lower level remain within cooldown.
        if existing and existing_rank >= current_rank:
            return None
        factors = _json_list(prediction.contributing_factors)
        recommendations = _json_list(prediction.recommendations)
        title = f"{level.upper()} {str(prediction.disaster_type).upper()} WARNING"
        message = (
            f"Zone: {zone_name}\nRisk Score: {prediction.risk_score:g}/100\n"
            f"Confidence: {prediction.confidence:g}%\n"
            f"Reasons: {', '.join(factors) or 'limited available evidence'}\n"
            f"Recommended: {'; '.join(recommendations)}"
        )
        row = NotificationDB(
            recipient_type="admin",
            recipient_id=None,
            incident_id=f"risk:{prediction.prediction_id}",
            title=title,
            message=message,
            level="critical" if level == "critical" else "alert",
            read=0,
            alert_type="early_warning",
            audience="rescue_teams",
            region_id=prediction.region_id,
            zone_id=prediction.zone_id,
            expires_at=now + timedelta(minutes=max(1, int(settings.RISK_ALERT_COOLDOWN_MINUTES))),
            is_demo=1 if str(prediction.data_status).upper() in {"DEMO", "MIXED"} else 0,
            created_at=now,
        )
        db.add(row)
        db.flush()
        event_engine.publish_event(
            "early_warning_created",
            f"risk:{prediction.prediction_id}",
            {"event_name": "early_warning_created", "event": "EARLY_WARNING_CREATED", "alert_id": row.id, "prediction_id": prediction.prediction_id, "zone_id": prediction.zone_id, "risk_level": level, "risk_score": prediction.risk_score},
            db=db,
        )
        return row


def _json_list(value: Any) -> list[str]:
    import json
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        parsed = json.loads(value or "[]")
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


early_warning_service = EarlyWarningService()
