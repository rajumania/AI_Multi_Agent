"""Consolidated GeoJSON-backed disaster map endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.api.deps import get_command_principal
from backend.services.map_overview import build_map_overview

router = APIRouter(prefix="/api/v1/map", tags=["Disaster Risk Map"])


def _overview(db: Session, **filters):
    return build_map_overview(db, **{key: value for key, value in filters.items() if value is not None})


@router.get("/overview")
def map_overview(
    zone_id: Optional[str] = Query(None),
    region_id: Optional[str] = Query(None),
    disaster_type: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    resource_status: Optional[str] = Query(None),
    sensor_status: Optional[str] = Query(None),
    alert_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _principal=Depends(get_command_principal),
):
    return _overview(db, zone_id=zone_id, region_id=region_id, disaster_type=disaster_type, risk_level=risk_level, resource_status=resource_status, sensor_status=sensor_status, alert_status=alert_status)


@router.get("/{layer}")
def map_layer(layer: str, db: Session = Depends(get_db), _principal=Depends(get_command_principal)):
    overview = build_map_overview(db)
    if layer not in {"risks", "zones", "hazards", "sensors", "incidents", "rescue_requests", "resources", "routes", "alerts"}:
        return {"items": []}
    return {"items": overview[layer], "generated_at": overview["generated_at"], "data_status": overview["data_status"]}
