"""Evidence-based tourist travel safety checks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend.config import settings
from backend.database.models import NotificationDB, RiskPredictionDB, WeatherObservationDB, ZoneDB
from backend.services.environmental_providers import DemoEnvironmentalProvider, get_environmental_provider
from backend.services.risk_engine import RiskFeatureEngine
from backend.services.risk_service import coordinate_context
from backend.services.safe_routing import safe_routing_service
from backend.services.weather_providers import fetch_with_fallback, get_weather_provider
from backend.services.earthquake_providers import EarthquakeProviderUnavailable, USGSEarthquakeProvider
from backend.services.severe_weather_providers import SevereWeatherProviderUnavailable, get_severe_weather_provider
from backend.graph.risk_workflow import run_risk_workflow


def _coordinate_safety(db: Session, destination: str, latitude: float, longitude: float, current_location: Optional[str]) -> dict:
    context = coordinate_context(latitude, longitude, destination)
    weather, weather_error = fetch_with_fallback(get_weather_provider(), latitude, longitude, destination)
    try:
        environmental = get_environmental_provider().fetch_for_zone(context)
    except Exception:
        environmental = DemoEnvironmentalProvider().fetch_for_zone(context)
    earthquakes = []
    earthquake_status = "NOT_CONFIGURED"
    if settings.EARTHQUAKE_PROVIDER.strip().lower() == "usgs":
        try:
            earthquakes = [item.model_dump(mode="json") for item in USGSEarthquakeProvider().fetch_recent(latitude, longitude)]
            earthquake_status = "LIVE" if earthquakes else "NO_QUALIFYING_EVENT"
        except EarthquakeProviderUnavailable:
            earthquake_status = "OFFLINE"
    warnings = []
    warning_status = "NOT_CONFIGURED"
    severe_provider = get_severe_weather_provider()
    if severe_provider is not None:
        try:
            warnings = [item.model_dump(mode="json") for item in severe_provider.fetch_alerts(latitude, longitude)]
            warning_status = "LIVE" if warnings else "NO_ACTIVE_WARNING"
        except SevereWeatherProviderUnavailable:
            warning_status = "OFFLINE"
    evidence_environment = list(environmental)
    if warnings:
        severity = max({"minor": 20, "moderate": 50, "severe": 75, "extreme": 95}.get(str(item.get("severity", "unknown")).lower(), 35) for item in warnings)
        evidence_environment.append({"indicator": "weather_warning_score", "value": severity, "source": "IMD_CAP", "observed_at": datetime.now(timezone.utc), "received_at": datetime.now(timezone.utc)})
    if earthquakes:
        evidence_environment.append({"indicator": "earthquake_magnitude_score", "value": max(0.0, min(100.0, float(earthquakes[0]["magnitude"]) / 8 * 100)), "source": "USGS", "observed_at": earthquakes[0]["time"], "received_at": datetime.now(timezone.utc)})
    features = RiskFeatureEngine().build(context, weather, evidence_environment, [])
    result = run_risk_workflow("severe_weather", destination, features)["result"]
    route = safe_routing_service.calculate(current_location or "Current location", destination, destination_lat=latitude, destination_lng=longitude) if current_location else {"route_status": "not_requested"}
    source_values = {str(weather.source).upper()}
    source_values.update(str(item.get("source", "")).upper() for item in environmental if item.get("source"))
    hazards = [str(weather.condition).replace("_", " ").title()] if str(weather.condition).lower() not in {"unknown", "clear", "cloudy"} else []
    hazards.extend(str(item.get("event") or item.get("title") or "Severe weather warning") for item in warnings)
    if earthquakes:
        hazards.append(f"Earthquake M{float(earthquakes[0]['magnitude']):g} at {float(earthquakes[0]['distance_km']):g} km")
    reasons = result.contributing_factors or ["No current elevated evidence returned"]
    if not earthquakes:
        reasons.append("No qualifying earthquake detected in the configured window.")
    return {
        "destination": destination,
        "latitude": latitude,
        "longitude": longitude,
        "risk_score": result.score,
        "risk_level": result.level.value,
        "hazards": hazards,
        "weather_summary": f"{weather.condition}; source {weather.source}; status {weather.status}; observed {weather.timestamp.isoformat()}",
        "active_alerts": [str(item.get("title") or item.get("event") or "Severe weather warning") for item in warnings],
        "route_status": route.get("route_status", "route_unavailable"),
        "recommendation": "NOT_RECOMMENDED" if result.score >= 75 else "CAUTION" if result.score >= 25 else "SAFE",
        "reasons": reasons,
        "safer_alternatives": [],
        "last_updated": weather.received_at,
        "data_status": "FALLBACK" if weather_error else result.data_status,
        "data_sources": sorted(source_values | ({"USGS"} if earthquakes else set()) | ({"IMD_CAP"} if warnings else set())),
        "freshness_seconds": weather.freshness_seconds,
        "provider_status": {"weather": weather.status, "environment": "LIVE" if environmental and not any("DEMO" in str(item.get("source", "")).upper() for item in environmental) else "FALLBACK", "earthquake": earthquake_status, "severe_weather": warning_status},
        "warnings": warnings,
        "earthquakes": earthquakes,
    }


def check_travel_safety(db: Session, destination: str, current_location: Optional[str] = None, latitude: Optional[float] = None, longitude: Optional[float] = None) -> dict:
    if latitude is not None and longitude is not None:
        return _coordinate_safety(db, destination, latitude, longitude, current_location)
    zone = db.query(ZoneDB).filter((ZoneDB.id == destination) | (ZoneDB.name.ilike(f"%{destination}%"))).first()
    if zone is None:
        raise ValueError("Destination is not in the verified zone catalog")
    predictions = db.query(RiskPredictionDB).filter(RiskPredictionDB.zone_id == zone.id).order_by(RiskPredictionDB.valid_from.desc()).limit(10).all()
    latest = max(predictions, key=lambda row: float(row.risk_score or 0), default=None)
    weather = db.query(WeatherObservationDB).filter(WeatherObservationDB.zone_id == zone.id).order_by(WeatherObservationDB.observed_at.desc()).first()
    alerts = db.query(NotificationDB).filter(NotificationDB.zone_id == zone.id, NotificationDB.alert_type.in_(["early_warning", "community_alert"])).order_by(NotificationDB.created_at.desc()).limit(10).all()
    score = float(latest.risk_score or 0) if latest else 0.0
    level = str(latest.risk_level).lower() if latest else "unknown"
    hazards = sorted({str(row.disaster_type).replace("_", " ").title() for row in predictions if float(row.risk_score or 0) >= 50})
    reasons = []
    if latest:
        try:
            import json
            reasons.extend(json.loads(latest.contributing_factors or "[]")[:5])
        except (TypeError, ValueError):
            pass
    route_status = "not_requested"
    if current_location:
        route_status = safe_routing_service.calculate(current_location, zone.name, destination_lat=zone.latitude, destination_lng=zone.longitude).get("route_status", "route_unavailable")
    recommendation = "NOT_RECOMMENDED" if score >= 75 else "CAUTION" if score >= 25 else "SAFE"
    return {"destination": zone.name, "latitude": zone.latitude, "longitude": zone.longitude, "risk_score": score, "risk_level": level, "hazards": hazards, "weather_summary": f"{weather.condition if weather else 'No weather observation'}; source {weather.source if weather else 'unknown'}" + (f", observed {weather.observed_at.isoformat()}" if weather else ""), "active_alerts": [alert.title for alert in alerts], "route_status": route_status, "recommendation": recommendation, "reasons": reasons or (["No current prediction is available"] if not latest else ["Current evidence indicates elevated conditions"]), "safer_alternatives": [], "last_updated": latest.valid_from if latest else datetime.now(timezone.utc), "data_status": ("FALLBACK" if weather and "DEMO" in str(weather.source).upper() else "STALE" if weather and latest and weather.observed_at < datetime.now(timezone.utc) - timedelta(minutes=30) else "LIVE") if weather else "OFFLINE", "data_sources": sorted({str(weather.source).upper()} if weather else set()), "freshness_seconds": ((datetime.now(timezone.utc) - (weather.observed_at.replace(tzinfo=timezone.utc) if weather and weather.observed_at.tzinfo is None else weather.observed_at)).total_seconds() if weather else None)}
