import json
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from backend.database.database import get_db
from backend.database.models import DepartmentResponseDB
from backend.api.deps import get_current_principal
from backend.models.telemetry import TelemetryIngestRequest, TelemetryIngestResponse
from backend.services.telemetry_service import telemetry_service
from backend.services.transport_tracking_service import authorize_assignment_resource

router = APIRouter(prefix="/api/v1/telemetry", tags=["Live Telemetry & GPS"])


@router.post("/location", response_model=TelemetryIngestResponse)
def post_vehicle_telemetry(
    payload: TelemetryIngestRequest,
    x_gps_device_token: Optional[str] = Header(None, alias="X-GPS-Device-Token"),
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
):
    """
    Real GPS Telemetry Ingestion Endpoint.
    Validates device authentication, coordinate sanity, updates SQLite state, and broadcasts live WebSocket event.
    """
    assignment = authorize_assignment_resource(
        db,
        principal,
        assignment_id=payload.assignment_id,
        resource_id=payload.vehicle_id,
        incident_id=payload.incident_id,
    )
    res = telemetry_service.process_telemetry(
        vehicle_id=payload.vehicle_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        speed=payload.speed,
        heading=payload.heading,
        accuracy=payload.accuracy,
        timestamp_str=payload.timestamp or "",
        auth_secret=x_gps_device_token,
        db=db,
        assignment_id=assignment.id,
        incident_id=assignment.incident_id,
    )
    return TelemetryIngestResponse(**res)


@router.get("/status/{vehicle_id}")
def get_vehicle_gps_status(vehicle_id: str, db: Session = Depends(get_db), principal=Depends(get_current_principal)):
    """
    Returns strict live GPS status (LIVE, STALE, LOST, OFFLINE) and telemetry freshness for vehicle.
    """
    if not principal.is_privileged:
        if not principal.is_department or str(principal.department).upper() != "TRANSPORT":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Transport department access required.")
        assignments = db.query(DepartmentResponseDB).filter(DepartmentResponseDB.department == "TRANSPORT").all()
        if not any(vehicle_id in _assigned_resource_ids(row) for row in assignments):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vehicle is not assigned to this transport department.")
    return telemetry_service.get_gps_status(vehicle_id, db=db)


def _assigned_resource_ids(row: DepartmentResponseDB) -> list[str]:
    try:
        values = json.loads(row.assigned_resources or "[]")
    except (TypeError, ValueError):
        values = []
    return [str(value) for value in values] if isinstance(values, list) else []
