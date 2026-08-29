"""Single, non-persisting evidence-fusion boundary for real locations."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.intelligence import IntelligencePreviewRequest
from backend.services.departments import departments_for_incident
from backend.services.earthquake_providers import EarthquakeProviderUnavailable, USGSEarthquakeProvider
from backend.services.environmental_providers import DemoEnvironmentalProvider, get_environmental_provider
from backend.services.provider_health import provider_health
from backend.services.risk_engine import RiskFeatureEngine, DeterministicRiskEngine
from backend.services.risk_service import coordinate_context
from backend.services.safe_routing import safe_routing_service
from backend.services.severe_weather_providers import SevereWeatherProviderUnavailable, get_severe_weather_provider
from backend.services.weather_providers import ProviderUnavailable, fetch_with_fallback, get_weather_provider
from backend.services.resource_coordination import available_resources
from backend.services.vision_provider import analyze_image_reference, image_hazard_class


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _status_sources(items: list[dict[str, Any]]) -> set[str]:
    return {str(item.get("source", "")).upper() for item in items if item.get("source")}


def _collection_status(items: list[dict[str, Any]], default: str = "OFFLINE") -> str:
    states = {str(item.get("status", "")).upper() for item in items}
    if "OFFLINE" in states:
        return "OFFLINE"
    if "FALLBACK" in states:
        return "FALLBACK"
    if "STALE" in states:
        return "STALE"
    return "LIVE" if items else default


def _department_reasons(disaster_type: str, risk_level: str, injured_count: int | None, image_analysis: dict[str, Any], text: str) -> list[dict[str, Any]]:
    departments = departments_for_incident("weather", risk_level, disaster_type)
    if injured_count and "MEDICAL" not in departments:
        departments.insert(0, "MEDICAL")
    reasons = {
        "MEDICAL": "Injury or medical triage may be required." if injured_count else "Standby medical triage and hospital coordination.",
        "SEARCH_AND_RESCUE": "Assess access, trapped persons, and rescue priority.",
        "FIRE": "Control fire, smoke, or hazardous-weather ignition risks.",
        "SECURITY": "Protect the scene, public access, and responder safety.",
        "TRANSPORT": "Coordinate responder movement and route conditions.",
        "COMMUNICATION": "Issue verified public information after authorization.",
        "FACILITIES": "Inspect infrastructure, drainage, utilities, or buildings.",
        "SHELTER": "Check safe accommodation and relief capacity for displaced people.",
    }
    supporting = [f"Selected hazard class: {disaster_type}"]
    if text.strip():
        supporting.append("Reporter description supplied")
    if str(image_analysis.get("status", "")).upper() == "LIVE":
        supporting.append("Vision analysis supplied supporting visual indicators")
    confidence = image_analysis.get("confidence") if str(image_analysis.get("status", "")).upper() == "LIVE" else None
    return [{"department": item, "reason": reasons.get(item, "Relevant operational support for this evidence set."), "supporting_evidence": supporting, "confidence": confidence} for item in departments]


def analyze_location(db: Session, request: IntelligencePreviewRequest) -> dict[str, Any]:
    """Collect provider evidence and score it without creating database rows."""
    context = coordinate_context(request.latitude, request.longitude, request.location)
    weather, weather_error = fetch_with_fallback(get_weather_provider(), request.latitude, request.longitude, request.location)
    image_analysis = analyze_image_reference(request.image_url, request.description)
    effective_hazard = request.disaster_type.value
    image_hazard = image_hazard_class(image_analysis)
    if effective_hazard == "other" and image_hazard:
        effective_hazard = image_hazard
    environmental: list[dict[str, Any]] = []
    environment_status = "OFFLINE"
    try:
        environmental = [dict(item) for item in get_environmental_provider().fetch_for_zone(context)]
        environment_status = _collection_status(environmental)
        if environment_status == "LIVE" and any("DEMO" in str(item.get("source", "")).upper() for item in environmental):
            environment_status = "FALLBACK"
    except Exception as exc:
        provider_health.failure("ENVIRONMENT", latency_ms=0, error_type=type(exc).__name__, source="environment")
        if settings.ALLOW_DETERMINISTIC_FALLBACK:
            environmental = [dict(item) for item in DemoEnvironmentalProvider().fetch_for_zone(context)]
            for item in environmental:
                item.update({"status": "FALLBACK", "freshness_seconds": None})
            environment_status = "FALLBACK"
        else:
            environment_status = "OFFLINE"

    earthquakes: list[dict[str, Any]] = []
    earthquake_status = "OFFLINE"
    if settings.EARTHQUAKE_PROVIDER.strip().lower() == "usgs":
        try:
            provider = USGSEarthquakeProvider()
            earthquakes = [
                _jsonable(item)
                for item in provider.fetch_recent(
                    request.latitude,
                    request.longitude,
                    radius_km=request.earthquake_radius_km,
                    lookback_hours=request.earthquake_lookback_hours,
                    min_magnitude=request.earthquake_min_magnitude,
                )
            ]
            earthquake_status = "STALE" if any(str(item.get("status", "")).upper() == "STALE" for item in earthquakes) else "LIVE" if earthquakes else "NO_QUALIFYING_EVENT"
        except EarthquakeProviderUnavailable:
            earthquake_status = "OFFLINE"
    else:
        earthquake_status = "NOT_CONFIGURED"

    severe_weather: list[dict[str, Any]] = []
    severe_weather_status = "NOT_CONFIGURED"
    severe_provider = get_severe_weather_provider()
    if severe_provider is not None:
        try:
            severe_weather = [_jsonable(item) for item in severe_provider.fetch_alerts(request.latitude, request.longitude)]
            severe_weather_status = "STALE" if any(str(item.get("status", "")).upper() == "STALE" for item in severe_weather) else "LIVE" if severe_weather else "NO_ACTIVE_WARNING"
        except SevereWeatherProviderUnavailable:
            severe_weather_status = "OFFLINE"

    # Warning and earthquake evidence enter the existing deterministic feature
    # engine as normalized indicators; no second risk engine is introduced.
    evidence_environment = list(environmental)
    if severe_weather:
        severity_score = max({"minor": 20, "moderate": 50, "severe": 75, "extreme": 95}.get(str(item.get("severity", "unknown")).lower(), 35) for item in severe_weather)
        evidence_environment.append({"indicator": "weather_warning_score", "value": severity_score, "unit": "score", "source": "IMD_CAP", "observed_at": datetime.now(timezone.utc), "received_at": datetime.now(timezone.utc)})
    if earthquakes:
        evidence_environment.append({"indicator": "earthquake_magnitude_score", "value": max(0.0, min(100.0, float(item["magnitude"]) / 8 * 100)) , "unit": "score", "source": "USGS", "observed_at": max(item["time"] for item in earthquakes), "received_at": datetime.now(timezone.utc)})
    if str(image_analysis.get("status", "")).upper() == "LIVE" and image_hazard:
        evidence_environment.append({"indicator": "image_evidence_score", "value": max(0.0, min(100.0, float(image_analysis.get("confidence") or 0.0) * 100)), "unit": "score", "source": "VISION", "status": "LIVE", "observed_at": image_analysis.get("timestamp"), "received_at": datetime.now(timezone.utc)})

    features = RiskFeatureEngine().build(context, weather, evidence_environment, [], now=datetime.now(timezone.utc))
    result = DeterministicRiskEngine().score(effective_hazard, features)

    routes: list[dict[str, Any]] = []
    if db is not None:
        for resource in [item for item in available_resources(db) if item.get("latitude") is not None and item.get("longitude") is not None][:5]:
            route = safe_routing_service.calculate(
                resource.get("location") or "Emergency resource",
                request.location,
                origin_lat=resource["latitude"], origin_lng=resource["longitude"],
                destination_lat=request.latitude, destination_lng=request.longitude,
                prefer_external=True,
            )
            routes.append({"resource_id": resource.get("resource_id"), "resource_name": resource.get("name"), **route})

    sources = {str(weather.source).upper()} | _status_sources(environmental) | ({"USGS"} if earthquakes else set()) | ({"IMD_CAP"} if severe_weather else set())
    provider_states = {str(weather.status).upper(), environment_status, earthquake_status, severe_weather_status}
    has_live = "LIVE" in provider_states
    has_fallback = "FALLBACK" in provider_states or any("DEMO" in source for source in sources)
    has_stale = "STALE" in provider_states
    has_offline = "OFFLINE" in provider_states
    if has_live and (has_fallback or has_stale or has_offline):
        data_status = "MIXED"
    elif has_fallback:
        data_status = "FALLBACK"
    elif has_stale:
        data_status = "STALE"
    elif has_live:
        data_status = "LIVE"
    else:
        data_status = "OFFLINE"
    evidence = {
        "text": {"status": "REPORTED", "description": request.description, "timestamp": datetime.now(timezone.utc).isoformat(), "confidence": 0.6},
        "photo": {"status": image_analysis.get("status", "NOT_PROVIDED"), "reference": request.image_url, "confidence": image_analysis.get("confidence"), "note": "Image evidence is supporting evidence and cannot independently confirm a disaster."},
        "image_analysis": image_analysis,
        "weather": {"source": weather.source, "status": weather.status, "timestamp": weather.timestamp, "freshness_seconds": weather.freshness_seconds},
        "environment": {"source": sorted(_status_sources(environmental)), "status": environment_status, "observation_count": len(environmental)},
        "earthquakes": {"source": "USGS", "status": earthquake_status, "event_count": len(earthquakes)},
        "severe_weather": {"source": "IMD_CAP", "status": severe_weather_status, "warning_count": len(severe_weather)},
        "location": {"latitude": request.latitude, "longitude": request.longitude, "label": request.location, "source": "USER_SELECTED_COORDINATES"},
    }
    return {
        "location": request.location, "latitude": request.latitude, "longitude": request.longitude,
        # Return the normalized evidence collection used by the existing risk
        # engine, including authoritative hazard indicators and supporting
        # image evidence. This keeps the preview explainable and avoids a
        # second hidden feature path.
        "weather": _jsonable(weather), "environmental": [_jsonable(item) for item in evidence_environment],
        "earthquakes": earthquakes, "earthquake_status": earthquake_status,
        "severe_weather": severe_weather, "severe_weather_status": severe_weather_status,
        "geographic": {"latitude": request.latitude, "longitude": request.longitude, "hazard_classification": None, "data_status": "NOT_IN_CATALOG"},
        "routes": routes, "evidence": evidence,
        "risk": _jsonable(result), "departments": _department_reasons(effective_hazard, result.level.value, request.injured_count, image_analysis, request.description),
        "image_analysis": image_analysis, "provider_status": provider_health.snapshot(),
        "analyzed_at": datetime.now(timezone.utc).isoformat(), "data_status": data_status,
        "weather_error": weather_error,
    }
