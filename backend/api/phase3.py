"""Phase 3 trigger, sensor, department, agent-trace and travel APIs."""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.deps import get_command_principal, get_optional_principal
from backend.database.database import get_db
from backend.database.models import AgentRunDB, IncidentDB, NotificationDB, SensorEventDB, SensorObservationDB, ZoneDB
from backend.models.phase3 import AgentRunRead, DepartmentRead, DisasterEventTrigger, SensorEventRead, SensorObservationCreate, SensorObservationRead, SensorSimulationRequest, TravelSafetyRequest, TravelSafetyResponse
from backend.services.disaster_intelligence_service import trigger_disaster_intelligence
from backend.services.phase3_service import run_demo_scenario
from backend.services.sensor_monitoring import THRESHOLDS, sensor_monitoring_service
from backend.services.travel_safety import check_travel_safety
from backend.services.risk_service import resolve_zone
from backend.services.event_engine import event_engine
from backend.services.monitoring_service import replan_event

router = APIRouter(prefix="/api/v1", tags=["Disaster Intelligence"])

DEPARTMENTS = [
    ("SEARCH_AND_RESCUE", "Search & Rescue", ["rescue assessment", "priority", "resources", "route"]),
    ("MEDICAL_EMS", "Medical EMS", ["triage", "hospitals", "ambulances"]),
    ("FIRE_HAZMAT", "Fire & Hazmat", ["fire response", "hazard controls"]),
    ("POLICE_PUBLIC_SAFETY", "Police & Public Safety", ["access controls", "public safety"]),
    ("TRANSPORT", "Transport", ["vehicles", "safe routes"]),
    ("LOGISTICS", "Logistics", ["food", "water", "equipment"]),
    ("SHELTER_RELIEF", "Shelter & Relief", ["shelters", "capacity"]),
    ("INFRASTRUCTURE_UTILITIES", "Infrastructure & Utilities", ["infrastructure", "route status"]),
    ("GIS_GEOSPATIAL", "GIS & Geospatial", ["zones", "geographic vulnerability"]),
    ("WEATHER_ENVIRONMENT", "Weather & Environment", ["weather", "sensors", "risk"]),
    ("PUBLIC_INFORMATION", "Public Information", ["approved warnings", "community communication"]),
    ("COMMUNITY_VOLUNTEER", "Community Volunteer", ["community reports", "local assistance"]),
]


@router.post("/events", status_code=status.HTTP_201_CREATED)
def create_disaster_event(payload: DisasterEventTrigger, db: Session = Depends(get_db), principal=Depends(get_optional_principal)):
    try:
        return trigger_disaster_intelligence(db, source=payload.event_source.lower(), location=payload.location, description=payload.description, zone_id=payload.zone_id, region_id=payload.region_id, latitude=payload.latitude, longitude=payload.longitude, disaster_type=payload.disaster_type, user_id=str(principal.id) if principal and principal.is_user else None, people_count=payload.people_count, community_reports=payload.community_reports, image_url=payload.image_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sensor-events", response_model=dict, status_code=status.HTTP_201_CREATED)
def ingest_sensor_event(payload: SensorObservationCreate, db: Session = Depends(get_db), _principal=Depends(get_command_principal)):
    try:
        zone = resolve_zone(db, payload.zone_id, payload.location, payload.region_id)
        observation, anomaly = sensor_monitoring_service.ingest(db, payload, zone)
        analysis = None
        if anomaly:
            active_statuses = {"reported", "analyzing", "assessing", "classified", "planning", "response_planning", "awaiting_approval", "approved", "in_progress", "monitoring"}
            active_event = db.query(IncidentDB).filter(IncidentDB.zone_id == zone.id, IncidentDB.status.in_(active_statuses)).order_by(IncidentDB.updated_at.desc()).first()
            analysis = trigger_disaster_intelligence(db, source="sensor", location=zone.name, description=anomaly.description, zone_id=zone.id, disaster_type=None, event_id=active_event.incident_id if active_event else None, replan=active_event is not None)
            event_engine.publish_event("sensor_correlated", analysis["event_id"], {"event_name": "sensor_correlated", "event": "SENSOR_CORRELATED", "sensor_event_id": anomaly.event_id, "sensor_id": anomaly.sensor_id, "zone_id": zone.id, "replan": active_event is not None, "description": "Sensor anomaly fused with the active disaster event."}, db=db)
            anomaly.status = "processed"
            db.commit()
        return {"observation": _observation(observation), "anomaly": _sensor_event(anomaly) if anomaly else None, "analysis": analysis}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sensors", response_model=list[SensorObservationRead])
def list_sensors(zone_id: Optional[str] = Query(None), limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    query = db.query(SensorObservationDB)
    if zone_id:
        query = query.filter(SensorObservationDB.zone_id == zone_id)
    return [_observation(row) for row in query.order_by(SensorObservationDB.received_at.desc()).limit(limit).all()]


@router.get("/sensors/status")
def sensor_status(db: Session = Depends(get_db)):
    rows = db.query(SensorObservationDB).order_by(SensorObservationDB.received_at.desc()).limit(200).all()
    latest = {}
    for row in rows:
        latest.setdefault(row.sensor_id, row)
    now = datetime.now(timezone.utc)
    result = []
    for row in latest.values():
        low, critical = THRESHOLDS.get(row.sensor_type, (None, None))
        age_seconds = max(0.0, (now - row.received_at.replace(tzinfo=timezone.utc) if row.received_at.tzinfo is None else now - row.received_at).total_seconds())
        if age_seconds > 30 * 60:
            condition = "OFFLINE"
        elif critical is not None and row.value >= critical:
            condition = "CRITICAL"
        elif low is not None and row.value >= low:
            condition = "WARNING"
        else:
            condition = "NORMAL"
        result.append({"sensor_id": row.sensor_id, "sensor_type": row.sensor_type, "zone_id": row.zone_id, "value": row.value, "previous_value": next((item.value for item in rows if item.sensor_id == row.sensor_id and item.id != row.id), None), "threshold": critical, "warning_threshold": low, "status": condition, "source": row.source, "unit": row.unit, "location": row.location, "observed_at": row.observed_at, "received_at": row.received_at, "age_seconds": age_seconds})
    return result


@router.get("/sensor-events", response_model=list[SensorEventRead])
def list_sensor_events(zone_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(SensorEventDB)
    if zone_id:
        query = query.filter(SensorEventDB.zone_id == zone_id)
    return query.order_by(SensorEventDB.created_at.desc()).limit(100).all()


@router.post("/sensor-simulations")
def sensor_simulation(payload: SensorSimulationRequest, db: Session = Depends(get_db), _principal=Depends(get_command_principal)):
    try:
        return run_demo_scenario(db, payload.scenario)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/monitoring/replan/{event_id}")
def monitoring_replan(event_id: str, db: Session = Depends(get_db), _principal=Depends(get_command_principal)):
    try:
        return replan_event(db, event_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/departments", response_model=list[DepartmentRead])
def departments():
    return [{"id": item[0], "name": item[1], "consumes": item[2]} for item in DEPARTMENTS]


@router.get("/departments/{department_id}", response_model=DepartmentRead)
def department(department_id: str):
    for item in DEPARTMENTS:
        if item[0] == department_id.upper():
            return {"id": item[0], "name": item[1], "consumes": item[2]}
    raise HTTPException(status_code=404, detail="Department not found")


@router.get("/agent-runs/{run_id}", response_model=AgentRunRead)
def agent_run(run_id: str, db: Session = Depends(get_db)):
    row = db.query(AgentRunDB).filter(AgentRunDB.run_id == run_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return _agent_run(row)


@router.get("/agent-runs", response_model=list[AgentRunRead])
def list_agent_runs(event_id: Optional[str] = Query(None), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    """Return persisted orchestration executions for command-center reconciliation."""
    query = db.query(AgentRunDB)
    if event_id:
        query = query.filter(AgentRunDB.event_id == event_id)
    rows = query.order_by(AgentRunDB.created_at.desc()).limit(limit).all()
    return [_agent_run(row) for row in rows]


@router.get("/agent-runs/{run_id}/trace")
def agent_trace(run_id: str, db: Session = Depends(get_db)):
    row = db.query(AgentRunDB).filter(AgentRunDB.run_id == run_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return {"run_id": run_id, "event_id": row.event_id, "trace": event_engine.get_decision_trace(row.event_id)}


@router.get("/alerts/nearby")
def nearby_alerts(zone_id: Optional[str] = Query(None), location: Optional[str] = Query(None), db: Session = Depends(get_db)):
    if not zone_id and location:
        try:
            zone_id = resolve_zone(db, location=location).id
        except ValueError:
            return []
    query = db.query(NotificationDB).filter(NotificationDB.audience.in_(["community", "rescue_teams"]))
    if zone_id:
        query = query.filter(NotificationDB.zone_id == zone_id)
    return query.order_by(NotificationDB.created_at.desc()).limit(100).all()


@router.post("/travel/safety-check", response_model=TravelSafetyResponse)
def travel_safety(payload: TravelSafetyRequest, db: Session = Depends(get_db), _principal=Depends(get_optional_principal)):
    try:
        return check_travel_safety(db, payload.destination, payload.current_location, payload.latitude, payload.longitude)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/travel/safety-check", response_model=TravelSafetyResponse)
def travel_safety_get(destination: str, current_location: Optional[str] = None, latitude: Optional[float] = Query(None, ge=-90, le=90), longitude: Optional[float] = Query(None, ge=-180, le=180), db: Session = Depends(get_db)):
    try:
        if (latitude is None) != (longitude is None):
            raise HTTPException(status_code=400, detail="latitude and longitude must be supplied together")
        return check_travel_safety(db, destination, current_location, latitude, longitude)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _observation(row):
    return {"id": row.id, "sensor_id": row.sensor_id, "sensor_type": row.sensor_type, "zone_id": row.zone_id, "region_id": row.region_id, "location": row.location, "latitude": row.latitude, "longitude": row.longitude, "value": row.value, "unit": row.unit, "observed_at": row.observed_at, "received_at": row.received_at, "source": row.source, "metadata": json.loads(row.metadata_json or "{}")}


def _sensor_event(row):
    return {"id": row.id, "event_id": row.event_id, "sensor_id": row.sensor_id, "sensor_type": row.sensor_type, "region_id": row.region_id, "zone_id": row.zone_id, "previous_value": row.previous_value, "current_value": row.current_value, "change_value": row.change_value, "anomaly_level": row.anomaly_level, "description": row.description, "source": row.source, "status": row.status, "created_at": row.created_at}


def _agent_run(row):
    return {"run_id": row.run_id, "event_id": row.event_id, "status": row.status, "required_agents": json.loads(row.required_agents or "[]"), "agent_results": json.loads(row.agent_results or "{}"), "agent_errors": json.loads(row.agent_errors or "[]"), "created_at": row.created_at, "completed_at": row.completed_at}
