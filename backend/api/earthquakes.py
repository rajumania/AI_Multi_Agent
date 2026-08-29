"""Thresholded USGS earthquake feed and explicit assessment boundary."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.deps import get_command_principal
from backend.database.database import get_db
from backend.services.disaster_intelligence_service import trigger_disaster_intelligence
from backend.services.earthquake_providers import EarthquakeProviderUnavailable, USGSEarthquakeProvider
from backend.services.risk_service import resolve_zone

router = APIRouter(prefix="/api/v1/earthquakes", tags=["Earthquake Events"])


class EarthquakeAssessmentRequest(BaseModel):
    event_id: str = Field(..., min_length=1, max_length=100)
    zone_id: str = Field(..., min_length=2, max_length=50)


@router.get("/recent")
def recent_earthquakes(
    latitude: float | None = Query(None, ge=-90, le=90),
    longitude: float | None = Query(None, ge=-180, le=180),
    radius_km: float | None = Query(None, gt=0, le=2000),
    lookback_hours: int | None = Query(None, gt=0, le=720),
    min_magnitude: float | None = Query(None, ge=-2, le=12),
    _principal=Depends(get_command_principal),
):
    if (latitude is None) != (longitude is None):
        raise HTTPException(status_code=400, detail="latitude and longitude must be supplied together")
    try:
        events = USGSEarthquakeProvider().fetch_recent(latitude, longitude, radius_km, lookback_hours, min_magnitude)
        return {"provider": "USGS", "status": "LIVE" if events else "NO_QUALIFYING_EVENT", "query": {"radius_km": radius_km, "lookback_hours": lookback_hours, "min_magnitude": min_magnitude}, "events": [event.model_dump(mode="json") for event in events], "message": None if events else "No qualifying earthquake detected in the configured window."}
    except EarthquakeProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail="Earthquake provider is unavailable") from exc


@router.post("/assess")
def assess_earthquake(payload: EarthquakeAssessmentRequest, db: Session = Depends(get_db), _principal=Depends(get_command_principal)):
    try:
        zone = resolve_zone(db, zone_id=payload.zone_id)
        events = USGSEarthquakeProvider().fetch_recent(zone.latitude, zone.longitude)
    except (EarthquakeProviderUnavailable, ValueError) as exc:
        raise HTTPException(status_code=503 if isinstance(exc, EarthquakeProviderUnavailable) else 400, detail="Earthquake provider is unavailable" if isinstance(exc, EarthquakeProviderUnavailable) else str(exc)) from exc
    event = next((item for item in events if item.event_id == payload.event_id), None)
    if event is None:
        raise HTTPException(status_code=404, detail="No threshold-qualified earthquake event found for this zone")
    result = trigger_disaster_intelligence(db, source="usgs", location=event.place, description=f"USGS earthquake M{event.magnitude:g} at {event.place}; depth {event.depth_km:g} km.", zone_id=zone.id, disaster_type="earthquake", event_id=f"USGS-{event.event_id}")
    return {"earthquake": event.model_dump(mode="json"), "analysis": result}
