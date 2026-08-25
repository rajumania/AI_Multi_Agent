"""Assignment-bound transport routes and live GPS state."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.database.models import (
    CampusResourceDB,
    DepartmentResponseDB,
    IncidentDB,
    RoadConditionDB,
    RouteDB,
    RouteReplanDB,
    TransportTelemetryDB,
)
from backend.services.departments import normalize_department
from backend.services.event_engine import event_engine
from backend.services.road_network import road_network


ACTIVE_ASSIGNMENT_STATES = {"EN_ROUTE", "ON_SCENE"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resource_ids(assignment: DepartmentResponseDB) -> list[str]:
    try:
        values = json.loads(assignment.assigned_resources or "[]")
    except (TypeError, ValueError):
        values = []
    return [str(value) for value in values] if isinstance(values, list) else []


def _assignment_context(db: Session, assignment_id: int):
    assignment = db.query(DepartmentResponseDB).filter(DepartmentResponseDB.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transport assignment not found.")
    incident = db.query(IncidentDB).filter(IncidentDB.incident_id == assignment.incident_id).first()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assigned incident not found.")
    return assignment, incident


def authorize_assignment_resource(
    db: Session,
    principal,
    *,
    assignment_id: Optional[int],
    resource_id: str,
    incident_id: Optional[str] = None,
    require_active: bool = True,
) -> DepartmentResponseDB:
    """Enforce principal -> department -> assignment -> resource ownership."""
    if assignment_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="assignment_id is required for transport telemetry.")
    if not principal.is_department or normalize_department(principal.department) != "TRANSPORT":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Transport department authorization is required.")
    assignment, incident = _assignment_context(db, assignment_id)
    if normalize_department(assignment.department) != "TRANSPORT":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Assignment is not a transport assignment.")
    if incident_id and incident.incident_id != incident_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incident does not belong to this assignment.")
    if resource_id not in _resource_ids(assignment):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Resource is not assigned to this transport team.")
    if require_active and assignment.status not in ACTIVE_ASSIGNMENT_STATES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transport GPS is available only after EN_ROUTE.")
    resource = db.query(CampusResourceDB).filter(CampusResourceDB.resource_id == resource_id).first()
    if not resource or normalize_department(resource.department) != "TRANSPORT":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Resource is not a transport resource.")
    return assignment


def _latest(db: Session, assignment_id: int, resource_id: str) -> Optional[TransportTelemetryDB]:
    return db.query(TransportTelemetryDB).filter(
        TransportTelemetryDB.assignment_id == assignment_id,
        TransportTelemetryDB.resource_id == resource_id,
    ).order_by(TransportTelemetryDB.timestamp.desc(), TransportTelemetryDB.id.desc()).first()


def _active_route(db: Session, assignment_id: int, resource_id: str) -> Optional[RouteDB]:
    return db.query(RouteDB).filter(
        RouteDB.assignment_id == assignment_id,
        RouteDB.resource_id == resource_id,
        RouteDB.status == "active",
    ).order_by(RouteDB.route_version.desc(), RouteDB.id.desc()).first()


def _route_dict(route: Optional[RouteDB]) -> Optional[Dict[str, Any]]:
    if not route:
        return None
    try:
        payload = json.loads(route.path or "{}")
    except (TypeError, ValueError):
        payload = {"coordinates": []}
    if isinstance(payload, list):
        payload = {"coordinates": payload}
    return {
        **payload,
        "route_version": route.route_version or 1,
        "distance_meters": route.distance_m,
        "eta_seconds": route.eta_seconds,
        "status": route.status,
        "geometry_source": route.geometry_source or "UNAVAILABLE",
        "updated_at": (route.updated_at or route.created_at).isoformat() if (route.updated_at or route.created_at) else None,
    }


def _origin_has_moved(route: RouteDB, latitude: float, longitude: float, threshold_meters: float = 2.0) -> bool:
    """Return whether the latest GPS point moved far enough to refresh geometry."""
    try:
        origin = json.loads(route.origin or "{}")
        origin_latitude = float(origin["latitude"])
        origin_longitude = float(origin["longitude"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return True
    return math.hypot(latitude - origin_latitude, longitude - origin_longitude) * 111000.0 >= threshold_meters


def _next_route_version(db: Session, assignment_id: int, resource_id: str) -> int:
    latest = db.query(RouteDB).filter(
        RouteDB.assignment_id == assignment_id,
        RouteDB.resource_id == resource_id,
    ).order_by(RouteDB.route_version.desc(), RouteDB.id.desc()).first()
    return int(latest.route_version or 0) + 1 if latest else 1


def ensure_active_route(
    db: Session,
    assignment_id: int,
    *,
    force: bool = False,
    reason: Optional[str] = None,
) -> Optional[RouteDB]:
    """Create/recalculate a route without changing assignment lifecycle."""
    assignment, incident = _assignment_context(db, assignment_id)
    resource_id = (_resource_ids(assignment) or [None])[0]
    if not resource_id or assignment.status not in ACTIVE_ASSIGNMENT_STATES:
        return None
    if incident.latitude is None or incident.longitude is None:
        return None
    latest = _latest(db, assignment_id, resource_id)
    if not latest:
        return None
    active = _active_route(db, assignment_id, resource_id)
    if active and not force and not _origin_has_moved(active, latest.latitude, latest.longitude):
        return active

    route = road_network.get_route_between_coordinates(
        latest.latitude,
        latest.longitude,
        incident.latitude,
        incident.longitude,
    )
    if not route:
        return None

    now = _now()
    version = _next_route_version(db, assignment_id, resource_id)
    route_path = json.dumps({"coordinates": route["coordinates"], "route": route.get("route", [])})
    route_origin = json.dumps({"latitude": latest.latitude, "longitude": latest.longitude})
    route_destination = json.dumps({"latitude": incident.latitude, "longitude": incident.longitude})

    # Ordinary GPS movement refreshes the active route in place. This keeps
    # the route anchored to the current vehicle position without creating an
    # unbounded route/replan row for every telemetry ping. Forced updates
    # (for example an authorized road blockage) still create a new version.
    if active and not force:
        active.origin = route_origin
        active.destination = route_destination
        active.path = route_path
        active.distance_m = float(route["distance_meters"])
        active.eta_seconds = float(route["eta_seconds"])
        active.geometry_source = route.get("source") or route.get("routing_engine")
        active.updated_at = now
        db.commit()
        db.refresh(active)
        new_route = active
        event_name = "transport_route_updated"
        version = int(active.route_version or 1)
    else:
        if active:
            active.status = "replaced"
            active.updated_at = now
        new_route = RouteDB(
            incident_id=incident.incident_id,
            assignment_id=assignment_id,
            resource_id=resource_id,
            origin=route_origin,
            destination=route_destination,
            path=route_path,
            distance_m=float(route["distance_meters"]),
            eta_seconds=float(route["eta_seconds"]),
            status="active",
            route_version=version,
            geometry_source=route.get("source") or route.get("routing_engine"),
            created_at=now,
            updated_at=now,
        )
        db.add(new_route)
        db.flush()
        if active:
            db.add(RouteReplanDB(
                incident_id=incident.incident_id,
                assignment_id=assignment_id,
                resource_id=resource_id,
                original_route=active.path,
                blocked_segment=reason or "route_update",
                new_route=new_route.path,
                reason=reason or "route_recalculated",
                route_version=version,
                timestamp=now,
            ))
        db.commit()
        db.refresh(new_route)
        event_name = "transport_route_updated" if active else "transport_route_created"
    payload = {
        "event_name": event_name,
        "event": event_name,
        "incident_id": incident.incident_id,
        "assignment_id": assignment_id,
        "department": "TRANSPORT",
        "resource_id": resource_id,
        "route_version": version,
        "coordinates": route["coordinates"],
        "distance_meters": route["distance_meters"],
        "eta_seconds": route["eta_seconds"],
        "geometry_source": route.get("source") or route.get("routing_engine"),
        "reason": reason,
        "timestamp": now.isoformat(),
    }
    event_engine.publish_event(event_name, incident.incident_id, payload)
    # Preserve the existing map consumer contract as an additive event.
    event_engine.publish_event("route_selected", incident.incident_id, {**payload, "event_name": "route_selected"})
    return new_route


def transport_tracking_snapshot(db: Session, assignment_id: int) -> Dict[str, Any]:
    assignment, incident = _assignment_context(db, assignment_id)
    resource_id = (_resource_ids(assignment) or [None])[0]
    latest = _latest(db, assignment_id, resource_id) if resource_id else None
    route = _route_dict(_active_route(db, assignment_id, resource_id)) if resource_id else None
    warning = None
    if assignment.status == "TEAM_ASSIGNED":
        warning = "Waiting for Transport Admin to set EN_ROUTE."
    elif assignment.status in ACTIVE_ASSIGNMENT_STATES and not latest:
        warning = "REAL GPS unavailable; enable GPS on the assigned transport device."
    elif assignment.status in ACTIVE_ASSIGNMENT_STATES and incident.latitude is None:
        warning = "Exact incident coordinates are unavailable; route cannot be calculated."
    return {
        "assignment_id": assignment.id,
        "incident_id": incident.incident_id,
        "department": assignment.department,
        "resource_id": resource_id,
        "team_identity": assignment.message or assignment.responder,
        "status": assignment.status,
        "incident_location": incident.location,
        "incident_latitude": incident.latitude,
        "incident_longitude": incident.longitude,
        "current_latitude": latest.latitude if latest else None,
        "current_longitude": latest.longitude if latest else None,
        "last_gps_update": latest.timestamp if latest else None,
        "gps_source": latest.source if latest else "UNAVAILABLE",
        "route": route,
        "eta_seconds": int(route["eta_seconds"]) if route and route.get("eta_seconds") is not None else None,
        "route_warning": warning,
    }


def recalculate_for_condition(db: Session, condition: RoadConditionDB) -> int:
    """Recalculate only active routes whose graph path contains the blocked edge."""
    if condition.status != "blocked":
        return 0
    rows = db.query(RouteDB).filter(RouteDB.status == "active").all()
    updated = 0
    for route in rows:
        try:
            route_data = json.loads(route.path or "{}")
            path = route_data.get("route", []) if isinstance(route_data, dict) else []
        except (TypeError, ValueError):
            path = []
        pairs = set(zip(path, path[1:])) | set(zip(path[1:], path))
        if (condition.node_a, condition.node_b) not in pairs:
            continue
        if route.assignment_id:
            if ensure_active_route(db, route.assignment_id, force=True, reason=condition.reason):
                updated += 1
    return updated
