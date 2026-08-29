"""Converging human/sensor triggers into the shared disaster LangGraph."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.database.models import AgentRunDB, EnvironmentalObservationDB, IncidentDB, NotificationDB, RescueRequestDB, SensorEventDB, SensorObservationDB, WeatherObservationDB, ZoneDB
from backend.graph.disaster_workflow import DisasterIntelligenceState, run_disaster_workflow
from backend.models.domain import EnvironmentalObservationCreate, RiskPredictRequest
from backend.services.audit_service import audit_service
from backend.services.departments import departments_for_incident
from backend.services.intelligence_service import _department_reasons
from backend.services.earthquake_providers import EarthquakeProviderUnavailable, USGSEarthquakeProvider
from backend.services.severe_weather_providers import SevereWeatherProviderUnavailable, get_severe_weather_provider
from backend.services.event_engine import event_engine
from backend.services.vision_provider import analyze_image_reference, image_hazard_class
from backend.services.risk_service import _response, latest_environment, latest_weather, predict, resolve_zone
from backend.services.risk_service import coordinate_context


def infer_disaster_type(description: str, requested: Optional[str] = None) -> str:
    if requested:
        return requested.lower()
    text = description.lower()
    if "landslide" in text or "slope" in text or "ground movement" in text:
        return "landslide"
    if "heat" in text or "temperature" in text:
        return "heatwave"
    if "cyclone" in text or "wind" in text:
        return "cyclone"
    if "rain" in text or "flood" in text or "river" in text:
        return "flood"
    return "severe_weather"


def _new_event(db: Session, *, event_id: str, source: str, location: str, description: str, zone: Any, disaster_type: str, latitude: Optional[float] = None, longitude: Optional[float] = None, user_id: Optional[str] = None, people_count: int = 1, image_url: Optional[str] = None) -> IncidentDB:
    exact_latitude = latitude if latitude is not None else zone.latitude
    exact_longitude = longitude if longitude is not None else zone.longitude
    row = IncidentDB(incident_id=event_id, description=description, incident_type="weather" if disaster_type in {"flood", "cyclone", "heatwave", "severe_weather"} else "other", location=location, severity="unknown", evidence_source=source, reported_by="Community Reporter" if source in {"community", "human"} else "Sensor Monitoring", status="reported", user_id=user_id, latitude=exact_latitude, longitude=exact_longitude, category=disaster_type, disaster_type=disaster_type, region_id=getattr(zone, "region_id", None), zone_id=getattr(zone, "id", None), image_url=image_url)
    db.add(row)
    if source in {"community", "human"}:
        db.add(RescueRequestDB(request_id=f"RES-{uuid.uuid4().hex[:12].upper()}", location=location, latitude=exact_latitude, longitude=exact_longitude, people_count=people_count, description=description, hazard_level="unknown", status="reported", incident_id=event_id, region_id=getattr(zone, "region_id", None), zone_id=getattr(zone, "id", None), user_id=user_id, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
    db.flush()
    return row


def _state(db: Session, event: IncidentDB, zone: Any, prediction, source: str, *, earthquake_data: Optional[list[dict[str, Any]]] = None, earthquake_status: str = "NOT_REQUESTED", severe_weather_data: Optional[list[dict[str, Any]]] = None, severe_weather_status: str = "NOT_CONFIGURED", image_analysis: Optional[dict[str, Any]] = None) -> DisasterIntelligenceState:
    zone_id = getattr(zone, "id", None)
    exact_point = event.latitude is not None and event.longitude is not None and getattr(zone, "exact_coordinates", False)
    if zone_id:
        weather = db.query(WeatherObservationDB).filter(WeatherObservationDB.zone_id == zone_id, WeatherObservationDB.latitude == event.latitude, WeatherObservationDB.longitude == event.longitude).order_by(WeatherObservationDB.observed_at.desc()).first() if exact_point else latest_weather(db, zone)
        environments = db.query(EnvironmentalObservationDB).filter(EnvironmentalObservationDB.zone_id == zone_id, EnvironmentalObservationDB.latitude == event.latitude, EnvironmentalObservationDB.longitude == event.longitude).order_by(EnvironmentalObservationDB.observed_at.desc()).limit(100).all() if exact_point else latest_environment(db, zone)
        requests = db.query(RescueRequestDB).filter(RescueRequestDB.zone_id == zone_id, RescueRequestDB.status != "closed").all()
        observations = db.query(SensorObservationDB).filter(SensorObservationDB.zone_id == zone_id).order_by(SensorObservationDB.received_at.desc()).limit(200).all()
        sensor_events = db.query(SensorEventDB).filter(SensorEventDB.zone_id == zone_id).order_by(SensorEventDB.created_at.desc()).limit(50).all()
    else:
        weather = db.query(WeatherObservationDB).filter(WeatherObservationDB.latitude == zone.latitude, WeatherObservationDB.longitude == zone.longitude).order_by(WeatherObservationDB.observed_at.desc()).first()
        environments = db.query(EnvironmentalObservationDB).filter(EnvironmentalObservationDB.latitude == zone.latitude, EnvironmentalObservationDB.longitude == zone.longitude).order_by(EnvironmentalObservationDB.observed_at.desc()).limit(100).all()
        requests = db.query(RescueRequestDB).filter(RescueRequestDB.incident_id == event.incident_id, RescueRequestDB.status != "closed").all()
        observations = [item for item in db.query(SensorObservationDB).order_by(SensorObservationDB.received_at.desc()).limit(200).all() if item.latitude is not None and item.longitude is not None and ((item.latitude - zone.latitude) ** 2 + (item.longitude - zone.longitude) ** 2) ** 0.5 * 111_000 <= 10_000]
        sensor_events = [item for item in db.query(SensorEventDB).order_by(SensorEventDB.created_at.desc()).limit(50).all() if item.zone_id and any(obs.zone_id == item.zone_id for obs in observations)]
    latest_sensors = {}
    for observation in observations:
        latest_sensors.setdefault(observation.sensor_id, observation)
    sensor_rows = [_model_dict(item) for item in latest_sensors.values()]
    sensor_event_rows = [_model_dict(item) for item in sensor_events]
    correlation = {
        "community_report_count": len(requests),
        "sensor_observation_count": len(sensor_rows),
        "sensor_anomaly_count": len(sensor_event_rows),
        "corroborated": bool(requests and sensor_rows),
        "sources": sorted({str(item.get("source")) for item in sensor_rows if item.get("source")}),
    }
    try:
        recommendations = json.loads(prediction.recommendations or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        recommendations = []
    return {
        "event_id": event.incident_id, "event_source": source, "disaster_type": event.disaster_type or "other", "location": event.location, "region": event.region_id or getattr(zone, "region_id", None), "zone": zone.name, "zone_id": zone_id, "region_id": getattr(zone, "region_id", None), "description": event.description, "severity": prediction.risk_level.value if hasattr(prediction.risk_level, "value") else str(prediction.risk_level), "risk_score": prediction.risk_score, "risk_level": prediction.risk_level.value if hasattr(prediction.risk_level, "value") else str(prediction.risk_level), "risk_confidence": prediction.confidence, "weather_data": _model_dict(weather), "environmental_data": [_model_dict(item) for item in environments], "sensor_data": sensor_rows, "sensor_events": sensor_event_rows, "earthquake_data": earthquake_data or [], "earthquake_status": earthquake_status, "severe_weather_data": severe_weather_data or [], "severe_weather_status": severe_weather_status, "image_analysis": image_analysis or {"status": "NOT_PROVIDED"}, "exact_latitude": event.latitude, "exact_longitude": event.longitude, "correlation": correlation, "geographic_data": {key: getattr(zone, key, None) for key in ("latitude", "longitude", "elevation_m", "slope_deg", "vulnerability_score", "river_proximity_km", "drainage_vulnerability", "hazard_classification", "coastal_vulnerability")}, "historical_data": {"frequency": getattr(zone, "historical_disaster_frequency", None)}, "community_reports": [_model_dict(item) for item in requests], "rescue_requests": [_model_dict(item) for item in requests], "vulnerable_zones": [zone_id] if zone_id and str(prediction.risk_level).lower() in {"high", "critical"} else [], "context": {"db": db}, "agent_results": {}, "agent_errors": [], "audit_events": [],
    }


def _model_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    result = {}
    for key in ("id", "request_id", "event_id", "sensor_id", "sensor_type", "indicator", "value", "current_value", "previous_value", "change_value", "anomaly_level", "status", "source", "condition", "temperature_c", "rainfall_mm", "rainfall_intensity", "wind_speed_kph", "humidity", "pressure", "received_at", "observed_at", "created_at", "latitude", "longitude", "unit", "injured_count", "children_count", "elderly_count", "people_count", "medical_emergency", "description"):
        value = getattr(row, key, None)
        result[key] = value.isoformat() if isinstance(value, datetime) else value
    return result


def _community_alert(db: Session, event: IncidentDB, prediction, zone: ZoneDB) -> Optional[NotificationDB]:
    if str(prediction.risk_level).lower() != "critical":
        return None
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    if db.query(NotificationDB).filter(NotificationDB.alert_type == "community_alert", NotificationDB.zone_id == zone.id, NotificationDB.created_at >= cutoff).first():
        return None
    factors = json.loads(prediction.contributing_factors or "[]")
    row = NotificationDB(recipient_type="community", title="CRITICAL COMMUNITY WARNING", message=f"You may be near a high-risk area: {zone.name}. Risk estimated as {prediction.risk_score:g}/100. Reasons: {', '.join(factors)}. Follow verified emergency guidance and move toward a safe location when authorized.", level="critical", read=0, incident_id=event.incident_id, alert_type="community_alert", audience="community", region_id=zone.region_id, zone_id=zone.id, is_demo=1 if str(prediction.data_status).upper() in {"DEMO", "MIXED"} else 0, created_at=datetime.now(timezone.utc))
    db.add(row)
    db.flush()
    event_engine.publish_event("community_alert", event.incident_id, {"event_name": "community_alert", "event": "COMMUNITY_ALERT", "alert_id": row.id, "zone_id": zone.id, "risk_score": prediction.risk_score})
    return row


def _detection_summary(
    *,
    disaster: str,
    description: str,
    latitude: Optional[float],
    longitude: Optional[float],
    prediction,
    weather: Any,
    environments: list[Any],
    sensor_rows: list[dict[str, Any]],
    earthquake_data: list[dict[str, Any]],
    earthquake_status: str,
    severe_weather_data: list[dict[str, Any]],
    severe_weather_status: str,
    image_url: Optional[str],
    image_analysis: dict[str, Any],
) -> dict[str, Any]:
    """Return transparent evidence fusion metadata; it is not an image claim."""
    text = description.lower()
    terms = {
        "flood": ("flood", "water entering", "waterlogging", "heavy rain", "rain entering", "inundat"),
        "cyclone": ("cyclone", "storm", "squall", "high wind"),
        "landslide": ("landslide", "slope failure", "ground movement", "mudslide"),
        "earthquake": ("earthquake", "tremor", "shaking", "seismic"),
        "fire": ("fire", "smoke", "flame", "burning"),
    }
    matched = next((hazard for hazard, words in terms.items() if any(word in text for word in words)), None)
    weather_source = str(getattr(weather, "source", "") or "").upper()
    weather_condition = str(getattr(weather, "condition", "") or "").lower()
    weather_signal = weather is not None and (
        weather_condition not in {"", "unknown", "clear", "cloudy"}
        or float(getattr(weather, "rainfall_mm", 0) or 0) > 0
        or float(getattr(weather, "wind_speed_kph", 0) or 0) >= 45
    )
    sensor_count = len(sensor_rows)
    supporting: list[str] = []
    if matched:
        supporting.append(f"Text signal matched {matched} indicators")
    if weather is not None:
        supporting.append(f"Weather observation: {weather_source or 'UNKNOWN'} / {getattr(weather, 'status', 'UNKNOWN')}")
    if environments:
        supporting.append(f"Environmental observations available: {len(environments)}")
    if sensor_count:
        supporting.append(f"Nearby sensor observations correlated: {sensor_count}")
    if earthquake_status != "NOT_REQUESTED":
        supporting.append(f"USGS earthquake check: {earthquake_status}")
    if severe_weather_status != "NOT_CONFIGURED":
        supporting.append(f"IMD severe-weather check: {severe_weather_status}")
    if image_url:
        supporting.append(f"IMAGE_ANALYSIS: {image_analysis.get('status', 'UNKNOWN')}")
        if str(image_analysis.get("status", "")).upper() == "LIVE":
            supporting.append("Vision findings are supporting evidence only")
    if not supporting:
        supporting.append("Insufficient evidence / monitoring required")
    confidence = 0.25
    if matched:
        confidence += 0.40
    if weather is not None and weather_source not in {"DEMO", "DEMO_FALLBACK"}:
        confidence += 0.15
    if environments and any(str(getattr(item, "source", "")).upper() not in {"DEMO", "DEMO_FALLBACK"} for item in environments):
        confidence += 0.10
    if sensor_count:
        confidence += 0.10
    confidence = min(0.95, round(confidence, 3))
    try:
        recommendations = json.loads(getattr(prediction, "recommendations", "[]") or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        recommendations = []
    weather_supports_hazard = disaster in {"flood", "urban_flood", "cyclone", "severe_weather"}
    authoritative_signal = bool(earthquake_data or severe_weather_data or sensor_count or (weather_signal and weather_supports_hazard and weather_source not in {"DEMO", "DEMO_FALLBACK"}))
    sufficient = bool(matched or authoritative_signal)
    return {
        "detected_hazard": disaster if sufficient else "other",
        "likely_hazard": disaster,
        "severity": str(getattr(prediction.risk_level, "value", prediction.risk_level)),
        "confidence": confidence,
        "evidence_status": "SUPPORTED" if sufficient else "INSUFFICIENT_EVIDENCE",
        "supporting_evidence": supporting,
        "latitude": latitude,
        "longitude": longitude,
        "affected_radius_km": None,
        "data_sources": sorted({value for value in [weather_source, "USGS" if earthquake_data else None, "IMD_CAP" if severe_weather_data else None, "VISION" if str(image_analysis.get("status", "")).upper() == "LIVE" else None] if value and value != "NOT_REQUESTED"} | {str(getattr(item, "source", "")).upper() for item in environments if getattr(item, "source", None)}),
        "freshness_seconds": getattr(weather, "freshness_seconds", None) if weather is not None else None,
        "recommended_departments": departments_for_incident("weather", str(getattr(prediction.risk_level, "value", prediction.risk_level)), disaster),
        "department_recommendations": _department_reasons(disaster, str(getattr(prediction.risk_level, "value", prediction.risk_level)), None, image_analysis, description),
        "recommended_actions": [str(item) for item in recommendations] if isinstance(recommendations, list) else [],
        "image_analysis": image_analysis,
        "severe_weather": severe_weather_data,
        "severe_weather_status": severe_weather_status,
    }


def _external_hazard_evidence(latitude: Optional[float], longitude: Optional[float], selected_coordinates: bool) -> tuple[list[dict[str, Any]], str, list[dict[str, Any]], str, list[EnvironmentalObservationCreate]]:
    """Fetch real hazard feeds once and turn qualifying values into risk inputs."""
    earthquakes: list[dict[str, Any]] = []
    earthquake_status = "NOT_REQUESTED"
    severe_weather: list[dict[str, Any]] = []
    severe_status = "NOT_CONFIGURED"
    normalized: list[EnvironmentalObservationCreate] = []
    if not selected_coordinates or latitude is None or longitude is None:
        return earthquakes, earthquake_status, severe_weather, severe_status, normalized
    try:
        earthquakes = [item.model_dump(mode="json") for item in USGSEarthquakeProvider().fetch_recent(latitude, longitude)]
        earthquake_status = "LIVE" if earthquakes else "NO_QUALIFYING_EVENT"
        if earthquakes:
            observed = datetime.fromisoformat(str(earthquakes[0]["time"]).replace("Z", "+00:00"))
            normalized.append(EnvironmentalObservationCreate(indicator="earthquake_magnitude_score", value=max(0.0, min(100.0, float(earthquakes[0]["magnitude"]) / 8 * 100)), unit="score", source="USGS", observed_at=observed, latitude=latitude, longitude=longitude, location="Selected coordinates"))
    except EarthquakeProviderUnavailable:
        earthquake_status = "OFFLINE"
    severe_provider = get_severe_weather_provider()
    if severe_provider is not None:
        try:
            severe_weather = [item.model_dump(mode="json") for item in severe_provider.fetch_alerts(latitude, longitude)]
            severe_status = "LIVE" if severe_weather else "NO_ACTIVE_WARNING"
            if severe_weather:
                severity_score = max({"minor": 20, "moderate": 50, "severe": 75, "extreme": 95}.get(str(item.get("severity", "unknown")).lower(), 35) for item in severe_weather)
                normalized.append(EnvironmentalObservationCreate(indicator="weather_warning_score", value=severity_score, unit="score", source="IMD_CAP", observed_at=datetime.now(timezone.utc), latitude=latitude, longitude=longitude, location="Selected coordinates"))
        except SevereWeatherProviderUnavailable:
            severe_status = "OFFLINE"
    return earthquakes, earthquake_status, severe_weather, severe_status, normalized


def trigger_disaster_intelligence(db: Session, *, source: str, location: str, description: str, zone_id: Optional[str] = None, region_id: Optional[str] = None, latitude: Optional[float] = None, longitude: Optional[float] = None, disaster_type: Optional[str] = None, event_id: Optional[str] = None, user_id: Optional[str] = None, people_count: int = 1, community_reports: int = 0, image_url: Optional[str] = None, replan: bool = False) -> dict[str, Any]:
    selected_coordinates = latitude is not None and longitude is not None
    try:
        zone = resolve_zone(db, zone_id, location, region_id)
        if latitude is not None and longitude is not None:
            zone = coordinate_context(latitude, longitude, location, base=zone)
    except ValueError:
        if latitude is None or longitude is None:
            raise
        zone = coordinate_context(latitude, longitude, location)
    disaster = infer_disaster_type(description, disaster_type)
    event = db.query(IncidentDB).filter(IncidentDB.incident_id == event_id).first() if event_id else None
    if event is None:
        event = _new_event(db, event_id=event_id or f"DIS-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}", source=source, location=location, description=description, zone=zone, disaster_type=disaster, latitude=latitude, longitude=longitude, user_id=user_id, people_count=people_count, image_url=image_url)
    else:
        # A single environmental event can expose more than one hazard (for
        # example, the Nepal demo produces flood and landslide analyses). Keep
        # the shared incident compatible while ensuring each run is routed for
        # the explicitly requested hazard.
        event.disaster_type = disaster
        event.category = disaster
        if latitude is not None and longitude is not None:
            event.latitude = latitude
            event.longitude = longitude
    if latitude is None:
        latitude = event.latitude
    if longitude is None:
        longitude = event.longitude
    image_analysis = analyze_image_reference(image_url or event.image_url, description)
    if image_url or event.image_url:
        event_engine.publish_event("evidence_received", event.incident_id, {"event_name": "evidence_received", "event": "EVIDENCE_RECEIVED", "image_reference": True, "description": "Reporter image evidence received."}, db=db)
        event_engine.publish_event("image_analysis_started", event.incident_id, {"event_name": "image_analysis_started", "event": "IMAGE_ANALYSIS_STARTED", "description": "Backend image evidence analysis started."}, db=db)
        event_engine.publish_event("image_analysis_completed", event.incident_id, {"event_name": "image_analysis_completed", "event": "IMAGE_ANALYSIS_COMPLETED", "status": image_analysis.get("status"), "provider": image_analysis.get("provider"), "confidence": image_analysis.get("confidence"), "description": "Backend image evidence analysis completed."}, db=db)
    image_hazard = image_hazard_class(image_analysis)
    if (not disaster_type or str(disaster_type).lower() == "other") and image_hazard:
        disaster = image_hazard
        event.disaster_type = disaster
        event.category = disaster
    if community_reports:
        db.add(EnvironmentalObservationDB(region_id=zone.region_id, zone_id=zone.id, location=zone.name, latitude=zone.latitude, longitude=zone.longitude, indicator="community_reports", value=community_reports, unit="reports", source="COMMUNITY_EVENT", observed_at=datetime.now(timezone.utc), received_at=datetime.now(timezone.utc)))
    earthquake_data, earthquake_status, severe_weather_data, severe_weather_status, external_environment = _external_hazard_evidence(latitude, longitude, selected_coordinates)
    if image_hazard:
        external_environment.append(EnvironmentalObservationCreate(indicator="image_evidence_score", value=max(0.0, min(100.0, float(image_analysis.get("confidence") or 0.0) * 100)), unit="score", source="VISION", observed_at=datetime.now(timezone.utc), latitude=latitude, longitude=longitude, location="Selected coordinates"))
    db.commit()
    prediction_row, zone_name, _ = predict(db, RiskPredictRequest(disaster_type=disaster, zone_id=getattr(zone, "id", None), use_latest_data=True, environmental=external_environment), location_context=zone)
    provider_states = {str(prediction_row.data_status or "").upper(), str(earthquake_status).upper(), str(severe_weather_status).upper()}
    if "OFFLINE" in provider_states:
        event.ai_provider_status = "MIXED"
    elif "FALLBACK" in provider_states:
        event.ai_provider_status = "FALLBACK"
    elif "STALE" in provider_states:
        event.ai_provider_status = "STALE"
    else:
        event.ai_provider_status = "LIVE"
    event.severity = prediction_row.risk_level.value if hasattr(prediction_row.risk_level, "value") else str(prediction_row.risk_level)
    event.required_departments = json.dumps(departments_for_incident("weather", event.severity, event.disaster_type))
    department_recommendations = _department_reasons(event.disaster_type or disaster, event.severity, None, image_analysis, description)
    event_engine.publish_event("departments_targeted", event.incident_id, {"event_name": "departments_targeted", "event": "DEPARTMENTS_TARGETED", "departments": json.loads(event.required_departments or "[]"), "recommendations": department_recommendations, "reason": "Targeting derived from the selected hazard and fused evidence; approval remains required."}, db=db)
    event.summary = prediction_row.explanation
    event.current_step = "Multi-agent disaster intelligence completed; awaiting authorized response."
    event.next_action = "Review response plan and human approval status."
    event.updated_at = datetime.now(timezone.utc)
    execution_id = f"RUN-{uuid.uuid4().hex[:12].upper()}"
    state = _state(db, event, zone, prediction_row, source, earthquake_data=earthquake_data, earthquake_status=earthquake_status, severe_weather_data=severe_weather_data, severe_weather_status=severe_weather_status, image_analysis=image_analysis)
    detection = _detection_summary(disaster=disaster, description=description, latitude=latitude, longitude=longitude, prediction=prediction_row, weather=db.query(WeatherObservationDB).filter(WeatherObservationDB.latitude == zone.latitude, WeatherObservationDB.longitude == zone.longitude).order_by(WeatherObservationDB.observed_at.desc()).first(), environments=db.query(EnvironmentalObservationDB).filter(EnvironmentalObservationDB.latitude == zone.latitude, EnvironmentalObservationDB.longitude == zone.longitude).order_by(EnvironmentalObservationDB.observed_at.desc()).limit(100).all(), sensor_rows=state.get("sensor_data", []), earthquake_data=earthquake_data, earthquake_status=earthquake_status, severe_weather_data=severe_weather_data, severe_weather_status=severe_weather_status, image_url=image_url or event.image_url, image_analysis=image_analysis)
    detection["image_analysis"] = image_analysis
    detection["department_recommendations"] = department_recommendations
    event.detection_evidence = json.dumps(detection)
    state["execution_id"] = execution_id
    state["context"]["replan"] = replan
    event_engine.publish_event("evidence_fused", event.incident_id, {"event_name": "evidence_fused", "event": "EVIDENCE_FUSED", "source": source, "disaster_type": disaster, "image_status": image_analysis.get("status"), "zone_id": zone.id, "description": "Text, exact location, image, provider, sensor, and geographic evidence were normalized."}, db=db)
    event_engine.publish_event("event_fused", event.incident_id, {"event_name": "event_fused", "event": "EVENT_FUSED", "source": source, "disaster_type": disaster, "zone_id": zone.id, "community_report_count": state.get("correlation", {}).get("community_report_count", 0), "sensor_observation_count": state.get("correlation", {}).get("sensor_observation_count", 0), "sensor_anomaly_count": state.get("correlation", {}).get("sensor_anomaly_count", 0), "corroborated": state.get("correlation", {}).get("corroborated", False), "replan": replan, "description": "Community and sensor evidence normalized at the shared event-fusion boundary."}, db=db)
    event_engine.publish_event("risk_updated", event.incident_id, {"event_name": "risk_updated", "event": "RISK_UPDATED", "risk_score": prediction_row.risk_score, "risk_level": str(prediction_row.risk_level.value if hasattr(prediction_row.risk_level, "value") else prediction_row.risk_level), "confidence": prediction_row.confidence, "zone_id": zone.id, "description": prediction_row.explanation}, db=db)
    result_state = run_disaster_workflow(state)
    event.status = "awaiting_approval" if result_state.get("approval_status") == "pending" else event.status
    event.current_step = "Updated disaster analysis completed; response plan is awaiting human approval." if replan else "Parallel disaster analysis completed; response plan is awaiting human approval."
    event.next_action = "Department command center must review and approve the updated response plan." if replan else "Department command center must review and approve the response plan."
    event.updated_at = datetime.now(timezone.utc)
    community_alert = _community_alert(db, event, prediction_row, zone)
    run_now = datetime.now(timezone.utc)
    run = AgentRunDB(run_id=execution_id, event_id=event.incident_id, incident_id=event.incident_id, agent="disaster_intelligence", department="WEATHER_ENVIRONMENT", summary="Multi-agent disaster intelligence execution", status="completed" if not result_state.get("agent_errors") else "completed_with_errors", required_agents=json.dumps(result_state.get("required_agents", [])), agent_results=json.dumps(result_state.get("agent_results", {}), default=str), agent_errors=json.dumps(result_state.get("agent_errors", [])), created_at=run_now, started_at=run_now, completed_at=run_now)
    db.add(run)
    db.commit()
    previous_plan_id = result_state.get("response_plan", {}).get("previous_plan_id")
    audit_service.log("disaster_intelligence_completed", f"Multi-agent analysis completed for {event.incident_id}.", incident_id=event.incident_id, actor="Disaster Intelligence System", details={"source": source, "risk_score": prediction_row.risk_score, "risk_level": prediction_row.risk_level, "agent_count": len(result_state.get("agent_results", {})), "execution_id": execution_id, "correlation": result_state.get("correlation", {}), "replan": replan, "previous_plan_id": previous_plan_id}, db=db)
    event_engine.publish_event("response_plan_updated", event.incident_id, {"event_name": "response_plan_updated", "event": "RESPONSE_PLAN_UPDATED", "plan_id": result_state.get("response_plan", {}).get("plan_id"), "previous_plan_id": previous_plan_id, "approval_status": result_state.get("approval_status")})
    if replan:
        event_engine.publish_event("replan_triggered", event.incident_id, {"event_name": "replan_triggered", "event": "REPLAN_TRIGGERED", "plan_id": result_state.get("response_plan", {}).get("plan_id"), "previous_plan_id": previous_plan_id, "execution_id": execution_id, "description": "Changed conditions were fused into a new approval-gated response plan."}, db=db)
    return {"event_id": event.incident_id, "prediction": _response(prediction_row, zone_name).model_dump(mode="json"), "detection": detection, "earthquake_data": earthquake_data, "earthquake_status": earthquake_status, "severe_weather": severe_weather_data, "severe_weather_status": severe_weather_status, "exact_location": {"latitude": latitude, "longitude": longitude}, "response_plan": result_state.get("response_plan"), "approval_status": result_state.get("approval_status"), "agent_run_id": run.run_id, "execution_id": execution_id, "correlation": result_state.get("correlation", {}), "agent_results": result_state.get("agent_results", {}), "agent_errors": result_state.get("agent_errors", []), "community_alert_id": community_alert.id if community_alert else None}
