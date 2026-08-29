"""Consolidated, privacy-aware map data assembled from persisted backend state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.database.models import (
    CampusResourceDB,
    IncidentDB,
    NotificationDB,
    RescueRequestDB,
    RiskPredictionDB,
    RouteDB,
    SensorObservationDB,
    ZoneDB,
)
from backend.services.campus_locations import CAMPUS_NODE_COORDINATES


def _finite_coordinate(lat: Any, lng: Any) -> Optional[list[float]]:
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return [lat, lng]


def _point(lat: Any, lng: Any) -> Optional[dict[str, Any]]:
    coords = _finite_coordinate(lat, lng)
    return {"type": "Point", "coordinates": [coords[1], coords[0]]} if coords else None


def _polygon(lat: Any, lng: Any, size: float = 0.01) -> Optional[dict[str, Any]]:
    coords = _finite_coordinate(lat, lng)
    if not coords:
        return None
    lat, lng = coords
    ring = [[lng - size, lat - size], [lng + size, lat - size], [lng + size, lat + size], [lng - size, lat + size], [lng - size, lat - size]]
    return {"type": "Polygon", "coordinates": [ring]}


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if isinstance(value, datetime) else value


def _resource(row: CampusResourceDB) -> dict[str, Any]:
    return {"id": row.resource_id, "name": row.name, "type": row.resource_type, "location": row.location, "latitude": row.latitude, "longitude": row.longitude, "status": row.availability_status, "capacity": row.capacity, "occupied": None, "current_assignment": getattr(row, "current_assignment", None), "contact": row.contact, "last_updated": _iso(row.last_updated), "is_demo": bool(getattr(row, "is_demo", 0))}


def _route_coordinates(row: RouteDB) -> list[list[float]]:
    try:
        raw = json.loads(row.path or "[]")
    except (TypeError, ValueError):
        return []
    result: list[list[float]] = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, str) and item in CAMPUS_NODE_COORDINATES:
            lat, lng = CAMPUS_NODE_COORDINATES[item]
            result.append([lng, lat])
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            coords = _finite_coordinate(item[0], item[1])
            if coords:
                result.append([coords[1], coords[0]])
    return result


def _risk_rows(db: Session, zone_id: Optional[str], disaster_type: Optional[str], risk_level: Optional[str]) -> list[RiskPredictionDB]:
    query = db.query(RiskPredictionDB)
    if zone_id:
        query = query.filter(RiskPredictionDB.zone_id == zone_id)
    if disaster_type:
        query = query.filter(RiskPredictionDB.disaster_type == disaster_type.lower())
    if risk_level:
        query = query.filter(RiskPredictionDB.risk_level == risk_level.lower())
    rows = query.order_by(RiskPredictionDB.valid_from.desc()).limit(500).all()
    seen: set[str] = set()
    latest = []
    for row in rows:
        key = f"{row.zone_id}:{row.disaster_type}"
        if key in seen:
            continue
        seen.add(key)
        latest.append(row)
    return latest


def build_map_overview(
    db: Session,
    *,
    zone_id: Optional[str] = None,
    region_id: Optional[str] = None,
    disaster_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    resource_status: Optional[str] = None,
    sensor_status: Optional[str] = None,
    alert_status: Optional[str] = None,
) -> dict[str, Any]:
    zones_query = db.query(ZoneDB)
    if zone_id:
        zones_query = zones_query.filter(ZoneDB.id == zone_id)
    if region_id:
        zones_query = zones_query.filter(ZoneDB.region_id == region_id)
    zones = zones_query.all()
    zone_by_id = {row.id: row for row in zones}
    risks = _risk_rows(db, zone_id, disaster_type, risk_level)
    risk_by_zone: dict[str, RiskPredictionDB] = {}
    for row in risks:
        risk_by_zone.setdefault(row.zone_id, row)

    risk_items = []
    zone_items = []
    hazard_items = []
    for zone in zones:
        risk = risk_by_zone.get(zone.id)
        geometry = _polygon(zone.latitude, zone.longitude, 0.025 if zone.id == "DEMO-N14" else 0.004)
        zone_item = {"id": zone.id, "region_id": zone.region_id, "name": zone.name, "population": zone.population, "latitude": zone.latitude, "longitude": zone.longitude, "elevation_m": zone.elevation_m, "slope_deg": zone.slope_deg, "vulnerability_score": zone.vulnerability_score, "historical_disaster_frequency": zone.historical_disaster_frequency, "river_proximity_km": zone.river_proximity_km, "drainage_vulnerability": zone.drainage_vulnerability, "hazard_classification": zone.hazard_classification, "is_demo": bool(zone.is_demo), "geometry": geometry, "geometry_source": "DEMO/SIMULATION"}
        zone_items.append(zone_item)
        hazard_items.append({"id": f"hazard:{zone.id}", "zone_id": zone.id, "name": zone.hazard_classification or "vulnerability zone", "hazard_type": zone.hazard_classification or "general_vulnerability", "geometry": geometry, "population": zone.population, "is_demo": bool(zone.is_demo), "geometry_source": "DEMO/SIMULATION"})
        if risk:
            factors = _json_list(risk.contributing_factors)
            risk_items.append({"id": risk.prediction_id or str(risk.id), "zone_id": zone.id, "region_id": zone.region_id, "zone": zone.name, "disaster_type": risk.disaster_type, "risk_score": risk.risk_score or 0, "risk_level": risk.risk_level, "confidence": risk.confidence or 0, "timestamp": _iso(risk.valid_from), "data_freshness_seconds": risk.data_freshness_seconds, "stale": bool(risk.stale), "contributing_factors": factors, "geometry": geometry, "is_demo": str(risk.data_status).upper() in {"DEMO", "MIXED"}, "data_status": risk.data_status})

    sensors_query = db.query(SensorObservationDB)
    if zone_id:
        sensors_query = sensors_query.filter(SensorObservationDB.zone_id == zone_id)
    sensors = []
    seen_sensors: set[str] = set()
    for row in sensors_query.order_by(SensorObservationDB.received_at.desc()).limit(500).all():
        if row.sensor_id in seen_sensors:
            continue
        seen_sensors.add(row.sensor_id)
        trend = "STABLE"
        previous = db.query(SensorObservationDB).filter(SensorObservationDB.sensor_id == row.sensor_id, SensorObservationDB.id != row.id).order_by(SensorObservationDB.observed_at.desc()).first()
        if previous and row.value > previous.value:
            trend = "RISING"
        elif previous and row.value < previous.value:
            trend = "FALLING"
        status = "NORMAL"
        if row.sensor_type in {"river_level", "water_level", "soil_moisture", "ground_movement", "tilt"} and row.value >= 70:
            status = "CRITICAL"
        elif row.value >= 40:
            status = "ELEVATED"
        sensors.append({"id": row.sensor_id, "sensor_id": row.sensor_id, "type": row.sensor_type, "zone_id": row.zone_id, "region_id": row.region_id, "location": row.location, "latitude": row.latitude, "longitude": row.longitude, "value": row.value, "previous_value": previous.value if previous else None, "trend": trend, "status": status, "unit": row.unit, "last_update": _iso(row.received_at), "source": row.source, "is_demo": str(row.source).upper().startswith("DEMO")})
    if sensor_status:
        sensors = [row for row in sensors if row["status"].lower() == sensor_status.lower()]

    resources_query = db.query(CampusResourceDB)
    if resource_status:
        resources_query = resources_query.filter(CampusResourceDB.availability_status == resource_status.lower())
    resources = [_resource(row) for row in resources_query.limit(1000).all() if _finite_coordinate(row.latitude, row.longitude)]

    incidents_query = db.query(IncidentDB).filter(IncidentDB.status.notin_(["resolved", "closed"]))
    if zone_id:
        incidents_query = incidents_query.filter(IncidentDB.zone_id == zone_id)
    incidents = []
    for row in incidents_query.order_by(IncidentDB.created_at.desc()).limit(500).all():
        zone = zone_by_id.get(row.zone_id)
        lat, lng = (row.latitude, row.longitude) if _finite_coordinate(row.latitude, row.longitude) else ((zone.latitude, zone.longitude) if zone else (None, None))
        if _finite_coordinate(lat, lng):
            incidents.append({"id": row.incident_id, "incident_id": row.incident_id, "disaster_type": row.disaster_type or row.incident_type, "risk_level": row.severity, "priority": None, "people_affected": None, "location": row.location, "status": row.status, "created_at": _iso(row.created_at), "latitude": lat, "longitude": lng, "source": row.evidence_source, "is_demo": "DEMO" in str(row.evidence_source).upper()})

    requests_query = db.query(RescueRequestDB).filter(RescueRequestDB.status.notin_(["closed", "resolved"]))
    if zone_id:
        requests_query = requests_query.filter(RescueRequestDB.zone_id == zone_id)
    rescue_requests = [{"id": row.request_id, "request_id": row.request_id, "zone_id": row.zone_id, "location": row.location, "latitude": row.latitude, "longitude": row.longitude, "people_count": row.people_count, "injured_count": row.injured_count, "priority_score": row.priority_score, "priority_level": "CRITICAL" if (row.priority_score or 0) >= 80 else "HIGH" if (row.priority_score or 0) >= 60 else "MEDIUM", "status": row.status, "created_at": _iso(row.created_at)} for row in requests_query.order_by(RescueRequestDB.created_at.desc()).limit(500).all() if _finite_coordinate(row.latitude, row.longitude)]

    route_rows = db.query(RouteDB).order_by(RouteDB.updated_at.desc()).limit(200).all()
    routes = [{"id": row.id, "incident_id": row.incident_id, "resource_id": row.resource_id, "origin": row.origin, "destination": row.destination, "status": row.status, "distance_m": row.distance_m, "eta_seconds": row.eta_seconds, "route_version": row.route_version, "geometry_source": row.geometry_source, "geometry": {"type": "LineString", "coordinates": _route_coordinates(row)}} for row in route_rows if len(_route_coordinates(row)) >= 2]

    alerts_query = db.query(NotificationDB).filter(NotificationDB.audience.in_(["community", "rescue_teams", "admin"]))
    if zone_id:
        alerts_query = alerts_query.filter(NotificationDB.zone_id == zone_id)
    if alert_status:
        alerts_query = alerts_query.filter(NotificationDB.level == alert_status.lower())
    alerts = [{"id": row.id, "zone_id": row.zone_id, "region_id": row.region_id, "title": row.title, "message": row.message, "level": row.level, "alert_type": row.alert_type, "created_at": _iso(row.created_at), "geometry": _polygon((zone_by_id.get(row.zone_id).latitude if zone_by_id.get(row.zone_id) else None), (zone_by_id.get(row.zone_id).longitude if zone_by_id.get(row.zone_id) else None), 0.03), "is_demo": bool(row.is_demo)} for row in alerts_query.order_by(NotificationDB.created_at.desc()).limit(200).all()]

    return {"generated_at": datetime.now(timezone.utc).isoformat(), "data_status": "DEMO/SIMULATION" if any(item.get("is_demo") for item in zone_items + resources + sensors) else "LIVE", "risks": risk_items, "zones": zone_items, "hazards": hazard_items, "sensors": sensors, "incidents": incidents, "rescue_requests": rescue_requests, "resources": resources, "routes": routes, "alerts": alerts, "affected_population": sum(int(item.get("population") or 0) for item in zone_items if item["id"] in {risk["zone_id"] for risk in risk_items if risk["risk_level"] in {"high", "critical"}})}


def _json_list(value: Any) -> list[str]:
    try:
        parsed = value if isinstance(value, list) else json.loads(value or "[]")
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []

