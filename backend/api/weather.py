"""Weather and environmental observation APIs; providers remain backend-only."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.api.deps import get_command_principal
from backend.database.models import EnvironmentalObservationDB, WeatherObservationDB
from backend.models.domain import EnvironmentalObservationCreate, EnvironmentalObservationRead, WeatherObservationCreate, WeatherObservationRead
from backend.services.risk_service import fetch_current_weather, ingest_environment, ingest_weather, latest_weather, resolve_zone
from backend.services.weather_providers import fetch_with_fallback, get_weather_provider

router = APIRouter(prefix="/api/v1/weather", tags=["Weather & Environment"])


@router.get("/current", response_model=WeatherObservationRead)
def current_weather(zone_id: Optional[str] = Query(None), location: Optional[str] = Query(None), db: Session = Depends(get_db)):
    try:
        row, _ = fetch_current_weather(db, resolve_zone(db, zone_id, location))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return row


@router.get("/current-exact")
def current_exact_weather(latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180), location: str = Query("Selected coordinates", min_length=2)):
    """Fetch weather for an arbitrary exact point without inventing a zone or persisting a row."""
    data, error = fetch_with_fallback(get_weather_provider(), latitude, longitude, location)
    result = data.model_dump(mode="json")
    if error:
        result["provider_error"] = error
    return result


@router.get("/history", response_model=list[WeatherObservationRead])
def weather_history(zone_id: Optional[str] = Query(None), limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    query = db.query(WeatherObservationDB)
    if zone_id:
        query = query.filter(WeatherObservationDB.zone_id == zone_id)
    return query.order_by(WeatherObservationDB.observed_at.desc()).limit(limit).all()


@router.get("/zone/{zone_id}", response_model=list[WeatherObservationRead])
def zone_weather(zone_id: str, limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    return db.query(WeatherObservationDB).filter(WeatherObservationDB.zone_id == zone_id).order_by(WeatherObservationDB.observed_at.desc()).limit(limit).all()


@router.post("/ingest", response_model=WeatherObservationRead, status_code=status.HTTP_201_CREATED)
def ingest_weather_observation(payload: WeatherObservationCreate, db: Session = Depends(get_db), _principal=Depends(get_command_principal)):
    try:
        zone = resolve_zone(db, payload.zone_id, payload.location, payload.region_id)
        row = ingest_weather(db, payload, zone)
        db.commit()
        db.refresh(row)
        return row
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/environment", response_model=EnvironmentalObservationRead, status_code=status.HTTP_201_CREATED)
def ingest_environment_observation(payload: EnvironmentalObservationCreate, db: Session = Depends(get_db), _principal=Depends(get_command_principal)):
    try:
        zone = resolve_zone(db, payload.zone_id, payload.location, payload.region_id)
        row = ingest_environment(db, payload, zone)
        db.commit()
        db.refresh(row)
        return row
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/environment", response_model=list[EnvironmentalObservationRead])
def environmental_history(zone_id: Optional[str] = Query(None), limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    query = db.query(EnvironmentalObservationDB)
    if zone_id:
        query = query.filter(EnvironmentalObservationDB.zone_id == zone_id)
    return query.order_by(EnvironmentalObservationDB.observed_at.desc()).limit(limit).all()
