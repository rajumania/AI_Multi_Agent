"""Application service joining providers, feature scoring, persistence and alerts."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database.models import EnvironmentalObservationDB, IncidentDB, RescueRequestDB, RiskPredictionDB, WeatherObservationDB, ZoneDB
from backend.graph.risk_workflow import run_risk_workflow
from backend.models.domain import EnvironmentalObservationCreate, RiskPredictRequest, RiskPredictionResponse, WeatherObservationCreate
from backend.models.incident import DisasterType
from backend.services.early_warning import early_warning_service
from backend.services.environmental_providers import DemoEnvironmentalProvider, get_environmental_provider
from backend.services.event_engine import event_engine
from backend.services.weather_providers import NormalizedWeather, fetch_with_fallback, get_weather_provider
from backend.services.provider_health import provider_health

logger = logging.getLogger(__name__)


def resolve_zone(db: Session, zone_id: Optional[str] = None, location: Optional[str] = None, region_id: Optional[str] = None) -> ZoneDB:
    query = db.query(ZoneDB)
    if zone_id:
        query = query.filter(ZoneDB.id == zone_id)
    elif location:
        query = query.filter(or_(ZoneDB.name.ilike(f"%{location}%"), ZoneDB.id.ilike(f"%{location}%")))
    elif region_id:
        query = query.filter(ZoneDB.region_id == region_id)
    zone = query.order_by(ZoneDB.name.asc()).first()
    if zone is None:
        raise ValueError("A valid zone_id, location, or region_id is required")
    return zone


def coordinate_context(latitude: float, longitude: float, location: str = "Reported coordinates", base: Any = None) -> Any:
    """Build a non-persisted geographic context for an arbitrary real point.

    Existing zone records remain the source of terrain/population metadata when
    available. A user can still report outside that catalog: the exact point is
    retained, provider calls use it directly, and absent GIS metadata stays
    absent instead of being replaced with a demo zone.
    """
    context = SimpleNamespace(
        id=None,
        region_id=None,
        name=location or f"{latitude:.6f}, {longitude:.6f}",
        latitude=latitude,
        longitude=longitude,
        population=None,
        elevation_m=None,
        slope_deg=None,
        vulnerability_score=None,
        historical_disaster_frequency=None,
        river_proximity_km=None,
        drainage_vulnerability=None,
        coastal_vulnerability=None,
        hazard_classification=None,
        exact_coordinates=True,
    )
    if base is not None:
        for field in ("id", "region_id", "population", "elevation_m", "slope_deg", "vulnerability_score", "historical_disaster_frequency", "river_proximity_km", "drainage_vulnerability", "coastal_vulnerability", "hazard_classification"):
            if hasattr(base, field):
                setattr(context, field, getattr(base, field))
    return context


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _weather_row(data: Any, zone: ZoneDB, source: Optional[str] = None) -> WeatherObservationDB:
    observed = data.observed_at or _now() if isinstance(data, WeatherObservationCreate) else _value(data, "timestamp") or _value(data, "observed_at") or _now()
    received = _now()
    latitude = _value(data, "latitude")
    longitude = _value(data, "longitude")
    return WeatherObservationDB(region_id=zone.region_id, zone_id=zone.id, location=_value(data, "location") or zone.name, latitude=latitude if latitude is not None else zone.latitude, longitude=longitude if longitude is not None else zone.longitude, observed_at=observed, received_at=received, condition=_value(data, "condition", "unknown"), temperature_c=_value(data, "temperature_c"), humidity=_value(data, "humidity"), rainfall_mm=_value(data, "rainfall_mm"), rainfall_intensity=_value(data, "rainfall_intensity"), wind_speed_kph=_value(data, "wind_speed_kph"), wind_direction=_value(data, "wind_direction"), pressure=_value(data, "pressure"), precipitation_probability=_value(data, "precipitation_probability"), source=source or _value(data, "source", "manual"))


def _value(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)


def ingest_weather(db: Session, data: Any, zone: ZoneDB, source: Optional[str] = None) -> WeatherObservationDB:
    row = _weather_row(data, zone, source)
    db.add(row)
    db.flush()
    event_engine.publish_event("weather_updated", f"risk:weather:{row.id}", {"event_name": "weather_updated", "event": "WEATHER_UPDATED", "observation_id": row.id, "zone_id": zone.id, "source": row.source}, db=db)
    return row


def ingest_environment(db: Session, data: EnvironmentalObservationCreate, zone: ZoneDB) -> EnvironmentalObservationDB:
    now = _now()
    row = EnvironmentalObservationDB(region_id=zone.region_id, zone_id=zone.id, location=data.location or zone.name, latitude=data.latitude if data.latitude is not None else zone.latitude, longitude=data.longitude if data.longitude is not None else zone.longitude, observed_at=data.observed_at or now, received_at=now, indicator=data.indicator.strip().lower(), value=data.value, unit=data.unit, source=data.source)
    db.add(row)
    db.flush()
    event_engine.publish_event("environment_updated", f"risk:environment:{row.id}", {"event_name": "environment_updated", "event": "ENVIRONMENT_UPDATED", "observation_id": row.id, "zone_id": zone.id, "source": row.source}, db=db)
    return row


def latest_weather(db: Session, zone: ZoneDB) -> Optional[WeatherObservationDB]:
    return db.query(WeatherObservationDB).filter(WeatherObservationDB.zone_id == zone.id).order_by(WeatherObservationDB.observed_at.desc()).first()


def latest_environment(db: Session, zone: ZoneDB) -> list[EnvironmentalObservationDB]:
    rows = db.query(EnvironmentalObservationDB).filter(EnvironmentalObservationDB.zone_id == zone.id).order_by(EnvironmentalObservationDB.observed_at.desc()).limit(100).all()
    seen: set[str] = set()
    result = []
    for row in rows:
        if row.indicator not in seen:
            result.append(row)
            seen.add(row.indicator)
    return result


def _community_rows(db: Session, zone: Any) -> list[Any]:
    query = db.query(RescueRequestDB).filter(RescueRequestDB.created_at >= _now() - timedelta(hours=24))
    if getattr(zone, "id", None):
        return query.filter(RescueRequestDB.zone_id == zone.id).all()
    latitude, longitude = getattr(zone, "latitude", None), getattr(zone, "longitude", None)
    if latitude is None or longitude is None:
        return []
    rows = query.filter(RescueRequestDB.latitude.is_not(None), RescueRequestDB.longitude.is_not(None)).all()
    return [row for row in rows if ((float(row.latitude) - latitude) ** 2 + (float(row.longitude) - longitude) ** 2) ** 0.5 * 111_000 <= 10_000]


def _response(row: RiskPredictionDB, zone_name: str) -> RiskPredictionResponse:
    return RiskPredictionResponse(prediction_id=row.prediction_id or str(row.id), disaster_type=row.disaster_type, zone_id=row.zone_id, zone=zone_name, region_id=row.region_id, risk_score=float(row.risk_score or 0), risk_level=row.risk_level, confidence=float(row.confidence or 0), contributing_factors=_json_list(row.contributing_factors), recommendations=_json_list(row.recommendations), explanation=row.explanation or row.rationale or "", features=_json_dict(row.features), data_status=row.data_status, data_freshness_seconds=row.data_freshness_seconds, stale=bool(row.stale), created_at=row.valid_from)


def _json_list(value: Any) -> list[str]:
    try:
        parsed = value if isinstance(value, list) else json.loads(value or "[]")
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def _json_dict(value: Any) -> dict[str, float]:
    try:
        parsed = value if isinstance(value, dict) else json.loads(value or "{}")
        return {str(k): float(v) for k, v in parsed.items()} if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def predict(db: Session, request: RiskPredictRequest, *, location_context: Any = None) -> tuple[RiskPredictionDB, str, Optional[Any]]:
    zone = location_context or resolve_zone(db, request.zone_id, request.location, request.region_id)
    zone_id = getattr(zone, "id", None)
    weather = None
    if request.weather:
        weather = ingest_weather(db, request.weather, zone)
    elif request.use_latest_data:
        weather = latest_weather(db, zone) if zone_id and not getattr(zone, "exact_coordinates", False) else None
        if weather is None:
            provider = get_weather_provider()
            weather_data, provider_error = fetch_with_fallback(provider, zone.latitude, zone.longitude, zone.name)
            if provider_error:
                logger.warning("Weather provider unavailable; using fallback: %s", provider_error)
            weather = ingest_weather(db, weather_data, zone)
    environments = [ingest_environment(db, item, zone) for item in request.environmental]
    if request.use_latest_data:
        environments = environments or (latest_environment(db, zone) if zone_id and not getattr(zone, "exact_coordinates", False) else [])
        if not environments:
            provider = get_environmental_provider()
            try:
                environments = [type("ExternalObservation", (), item)() for item in provider.fetch_for_zone(zone)]
            except Exception as exc:
                if not settings.ALLOW_DETERMINISTIC_FALLBACK:
                    raise
                provider_health.mark_fallback("ENVIRONMENT", source="demo")
                logger.warning("environment provider fallback provider=%s error_type=%s", type(provider).__name__, type(exc).__name__)
                environments = [type("DemoObservation", (), item)() for item in DemoEnvironmentalProvider().fetch_for_zone(zone)]
    features = __import__("backend.services.risk_engine", fromlist=["RiskFeatureEngine"]).RiskFeatureEngine().build(zone, weather, environments, _community_rows(db, zone))
    graph_state = run_risk_workflow(request.disaster_type.value, zone.name, features)
    result = graph_state["result"]
    now = _now()
    prediction_id = f"RISK-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    row = RiskPredictionDB(prediction_id=prediction_id, region_id=zone.region_id, zone_id=zone.id, disaster_type=request.disaster_type.value, risk_level=result.level.value, probability=result.score / 100.0, risk_score=result.score, confidence=result.confidence, features=json.dumps(result.features), contributing_factors=json.dumps(graph_state.get("contributing_factors", result.contributing_factors)), recommendations=json.dumps(graph_state.get("recommendations", result.recommendations)), explanation=graph_state.get("explanation", result.explanation), data_status=result.data_status, data_freshness_seconds=result.freshness_seconds, stale=1 if result.stale else 0, rationale=result.explanation, valid_from=now, valid_until=now + timedelta(hours=1), status="active")
    db.add(row)
    db.flush()
    alert = early_warning_service.evaluate(db, row, zone.name)
    event_engine.publish_event("risk_updated", f"risk:{prediction_id}", {"event_name": "risk_updated", "event": "RISK_UPDATED", "prediction_id": prediction_id, "zone_id": zone.id, "risk_score": result.score, "risk_level": result.level.value, "confidence": result.confidence, "data_status": result.data_status, "stale": result.stale}, db=db)
    db.commit()
    db.refresh(row)
    return row, zone.name, alert


def fetch_current_weather(db: Session, zone: ZoneDB) -> tuple[WeatherObservationDB, Optional[str]]:
    previous = latest_weather(db, zone)
    data, error = fetch_with_fallback(get_weather_provider(), zone.latitude, zone.longitude, zone.name)
    if error and previous is not None:
        # Keep the last valid observation visible when a refresh fails. Its
        # derived API status/freshness makes staleness explicit to callers.
        return previous, error
    row = ingest_weather(db, data, zone)
    db.commit()
    db.refresh(row)
    return row, error
