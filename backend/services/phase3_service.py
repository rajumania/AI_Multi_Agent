"""Phase 3 sensor/demo orchestration helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.database.models import SensorEventDB, ZoneDB
from backend.models.phase3 import SensorObservationCreate
from backend.services.disaster_intelligence_service import trigger_disaster_intelligence
from backend.services.sensor_monitoring import DemoSensorProvider, sensor_monitoring_service


def run_demo_scenario(db: Session, scenario: str) -> dict:
    key = scenario.lower().replace(" ", "_").replace("-", "_")
    zone_id, disaster, description = {
        "nepal_mountain": ("DEMO-N14", None, "DEMO/SIMULATION: extreme rainfall, rapidly rising river level, high soil moisture and detected ground movement in Nepal Mountain N-14."),
        "urban_flood": ("DEMO-ZONE-A", "urban_flood", "DEMO/SIMULATION: intense urban rainfall and waterlogging signals."),
        "cyclone": ("DEMO-ZONE-A", "cyclone", "DEMO/SIMULATION: severe coastal wind and rainfall conditions."),
        "heatwave": ("DEMO-ZONE-B", "heatwave", "DEMO/SIMULATION: sustained extreme heat and humidity."),
    }.get(key, (None, None, None))
    if zone_id is None:
        raise ValueError("Unknown demo scenario")
    zone = db.query(ZoneDB).filter(ZoneDB.id == zone_id).first()
    if zone is None:
        raise ValueError("Demo zone is not available")
    sensor_events = []
    for payload in DemoSensorProvider().read(zone, key):
        _, anomaly = sensor_monitoring_service.ingest(db, payload, zone)
        if anomaly:
            sensor_events.append(anomaly.event_id)
    hazards = [disaster] if disaster else ["flood", "landslide"]
    analyses = []
    event_id = None
    for hazard in hazards:
        result = trigger_disaster_intelligence(db, source="sensor", location=zone.name, description=description, zone_id=zone.id, disaster_type=hazard, event_id=event_id)
        event_id = result["event_id"]
        analyses.append(result)
    return {"status": "scenario_completed", "scenario": key, "data_status": "DEMO/SIMULATION", "event_id": event_id, "sensor_event_ids": sensor_events, "analyses": analyses}
