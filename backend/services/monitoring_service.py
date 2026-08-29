"""Monitoring checks that can safely start a new approval-gated plan."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.database.models import IncidentDB
from backend.services.disaster_intelligence_service import trigger_disaster_intelligence


def replan_event(db: Session, event_id: str) -> dict:
    event = db.query(IncidentDB).filter(IncidentDB.incident_id == event_id).first()
    if event is None:
        raise ValueError("Event not found")
    # Preserve the reporter's exact point when the incident is outside the
    # catalog. Re-planning must re-run the same real providers at that point;
    # resolving only by the display label can incorrectly fail with no zone.
    return trigger_disaster_intelligence(
        db,
        source="monitoring",
        location=event.location,
        description=event.description,
        zone_id=event.zone_id,
        region_id=event.region_id,
        latitude=event.latitude,
        longitude=event.longitude,
        disaster_type=event.disaster_type,
        event_id=event.incident_id,
        user_id=event.user_id,
        image_url=event.image_url,
        replan=True,
    )
