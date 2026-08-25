import math
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.config import settings
from backend.database.models import CampusResourceDB, TransportTelemetryDB
from backend.services.event_engine import event_engine
from backend.services.audit_service import audit_service


class TelemetryService:
    """
    Real GPS Telemetry Service.
    Ingests live position updates from authorized mobile/hardware trackers,
    validates spatial sanity, maintains GPS connection states, and broadcasts live WebSocket events.
    """

    def __init__(self):
        # In-memory store of last telemetry ping per vehicle_id
        # vehicle_id -> {latitude, longitude, speed, heading, accuracy, timestamp, raw_time}
        self._latest_telemetry: Dict[str, Dict[str, Any]] = {}

    def get_gps_status(self, vehicle_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Calculates strict GPS status for vehicle:
        - LIVE: telemetry received within 15 seconds
        - LIVE - STALE: telemetry received between 15s and 60s ago
        - GPS CONNECTION LOST: telemetry stopped >60s ago
        - GPS OFFLINE: no telemetry recorded
        """
        record = self._latest_telemetry.get(vehicle_id)
        if not record and db is not None:
            persisted = db.query(TransportTelemetryDB).filter(
                TransportTelemetryDB.resource_id == vehicle_id,
            ).order_by(TransportTelemetryDB.timestamp.desc(), TransportTelemetryDB.id.desc()).first()
            if persisted:
                raw_time = persisted.timestamp
                record = {
                    "latitude": persisted.latitude,
                    "longitude": persisted.longitude,
                    "speed": persisted.speed or 0.0,
                    "heading": persisted.heading or 0.0,
                    "accuracy": persisted.accuracy or 0.0,
                    "timestamp": raw_time.isoformat(),
                    "raw_time": raw_time,
                }
        if not record:
            return {
                "gps_mode": "GPS OFFLINE",
                "status_code": "OFFLINE",
                "last_update": None,
                "last_location": None,
                "heading": 0.0,
                "speed": 0.0
            }

        now = datetime.now(timezone.utc)
        diff_sec = (now - record["raw_time"]).total_seconds()

        if diff_sec <= 15:
            code = "LIVE"
            mode = "LIVE GPS"
        elif diff_sec <= 60:
            code = "STALE"
            mode = "LIVE GPS - STALE"
        else:
            code = "LOST"
            mode = "GPS CONNECTION LOST"

        return {
            "gps_mode": mode,
            "status_code": code,
            "last_update": record["timestamp"],
            "last_location": [record["latitude"], record["longitude"]],
            "heading": record.get("heading", 0.0),
            "speed": record.get("speed", 0.0),
            "accuracy": record.get("accuracy", 0.0),
            "source": "LIVE VEHICLE TELEMETRY"
        }

    def process_telemetry(
        self,
        vehicle_id: str,
        latitude: float,
        longitude: float,
        speed: float,
        heading: float,
        accuracy: float,
        timestamp_str: str,
        auth_secret: Optional[str],
        db: Session,
        assignment_id: Optional[int] = None,
        incident_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        # 1. Secret / Device Authentication
        if not auth_secret or auth_secret != settings.GPS_TELEMETRY_SECRET:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid GPS telemetry device token."
            )

        # 2. Coordinate boundary sanity
        if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Coordinates out of physical range."
            )

        now = datetime.now(timezone.utc)
        received_timestamp = now
        if timestamp_str:
            try:
                received_timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                if received_timestamp.tzinfo is None:
                    received_timestamp = received_timestamp.replace(tzinfo=timezone.utc)
            except ValueError:
                received_timestamp = now

        # 3. Store telemetry ping
        self._latest_telemetry[vehicle_id] = {
            "latitude": latitude,
            "longitude": longitude,
            "speed": max(0.0, speed),
            "heading": heading % 360.0,
            "accuracy": accuracy,
            "timestamp": timestamp_str or now.isoformat(),
            "raw_time": now
        }

        # 4. Update Database position
        resource = db.query(CampusResourceDB).filter(CampusResourceDB.resource_id == vehicle_id).first()
        if resource:
            resource.latitude = latitude
            resource.longitude = longitude
            resource.last_updated = now
            if resource.availability_status == "available":
                resource.availability_status = "en_route"
            db.commit()

        if assignment_id is not None and incident_id:
            db.add(TransportTelemetryDB(
                resource_id=vehicle_id,
                assignment_id=assignment_id,
                incident_id=incident_id,
                latitude=latitude,
                longitude=longitude,
                timestamp=received_timestamp,
                speed=max(0.0, speed),
                heading=heading % 360.0,
                accuracy=accuracy,
                source="REAL",
            ))
            db.commit()

        route_version = None
        if assignment_id is not None:
            # A route is created only after the human-controlled EN_ROUTE state
            # has been reached and a real GPS point is available.
            from backend.services.transport_tracking_service import ensure_active_route
            route = ensure_active_route(db, assignment_id)
            route_version = route.route_version if route else None

        # 5. Broadcast real-time WebSocket event
        location_payload = {
            "event": "transport_location_updated",
            "resource_id": vehicle_id,
            "assignment_id": assignment_id,
            "department": "TRANSPORT" if assignment_id is not None else None,
            "incident_id": incident_id or "live_telemetry",
            "latitude": latitude,
            "longitude": longitude,
            "speed": speed,
            "heading": heading,
            "accuracy": accuracy,
            "gps_mode": "LIVE",
            "source": "REAL",
            "route_version": route_version,
            "timestamp": now.isoformat(),
        }
        event_engine.publish_event(
            event_name="transport_location_updated" if assignment_id is not None else "vehicle_location_updated",
            incident_id=incident_id or "live_telemetry",
            payload={**location_payload, "event_name": "transport_location_updated" if assignment_id is not None else "vehicle_location_updated"},
        )
        if assignment_id is not None and route_version is not None and route is not None:
            event_engine.publish_event(
                event_name="transport_eta_updated",
                incident_id=incident_id or "live_telemetry",
                payload={
                    "event_name": "transport_eta_updated",
                    "event": "transport_eta_updated",
                    "incident_id": incident_id,
                    "assignment_id": assignment_id,
                    "department": "TRANSPORT",
                    "resource_id": vehicle_id,
                    "route_version": route_version,
                    "eta_seconds": route.eta_seconds,
                    "distance_meters": route.distance_m,
                    "timestamp": now.isoformat(),
                },
            )

        return {
            "status": "accepted",
            "vehicle_id": vehicle_id,
            "latitude": latitude,
            "longitude": longitude,
            "gps_mode": "LIVE",
            "timestamp": now.isoformat(),
            "assignment_id": assignment_id,
            "incident_id": incident_id,
            "route_version": route_version,
        }


telemetry_service = TelemetryService()
