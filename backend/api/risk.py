"""Risk prediction, summaries and early-warning API routes."""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.api.deps import get_command_principal
from backend.database.models import NotificationDB, RiskPredictionDB, ZoneDB
from backend.models.domain import EarlyWarningRead, RiskPredictRequest, RiskPredictionResponse
from backend.services.risk_service import _response, predict, resolve_zone

router = APIRouter(prefix="/api/v1/risk", tags=["Risk & Early Warning"])


@router.post("/predict", response_model=RiskPredictionResponse, status_code=status.HTTP_201_CREATED)
def create_prediction(payload: RiskPredictRequest, db: Session = Depends(get_db), _principal=Depends(get_command_principal)):
    try:
        row, zone_name, _ = predict(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _response(row, zone_name)


@router.get("", response_model=list[RiskPredictionResponse])
def list_predictions(
    zone_id: Optional[str] = Query(None),
    disaster_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(RiskPredictionDB)
    if zone_id:
        query = query.filter(RiskPredictionDB.zone_id == zone_id)
    if disaster_type:
        query = query.filter(RiskPredictionDB.disaster_type == disaster_type.lower())
    rows = query.order_by(RiskPredictionDB.valid_from.desc()).limit(limit).all()
    zones = {z.id: z.name for z in db.query(ZoneDB).all()}
    return [_response(row, zones.get(row.zone_id, row.zone_id or "Unknown zone")) for row in rows]


@router.get("/zones", response_model=list[RiskPredictionResponse])
def zone_predictions(db: Session = Depends(get_db)):
    rows = db.query(RiskPredictionDB).order_by(RiskPredictionDB.valid_from.desc()).all()
    seen: set[str] = set()
    zones = {z.id: z.name for z in db.query(ZoneDB).all()}
    result = []
    for row in rows:
        if row.zone_id in seen:
            continue
        seen.add(row.zone_id)
        result.append(_response(row, zones.get(row.zone_id, row.zone_id or "Unknown zone")))
    return result


@router.get("/summary")
def risk_summary(zone_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(RiskPredictionDB)
    if zone_id:
        query = query.filter(RiskPredictionDB.zone_id == zone_id)
    rows = query.order_by(RiskPredictionDB.valid_from.desc()).limit(24).all()
    zones = {z.id: z.name for z in db.query(ZoneDB).all()}
    latest = _response(rows[0], zones.get(rows[0].zone_id, rows[0].zone_id or "Unknown zone")) if rows else None
    trend = [_response(row, zones.get(row.zone_id, row.zone_id or "Unknown zone")) for row in reversed(rows)]
    warning_status = "CRITICAL" if latest and latest.risk_level == "critical" else "WARNING" if latest and latest.risk_level == "high" else "MONITORING" if latest and latest.risk_level == "medium" else "NORMAL"
    return {"latest": latest, "trend": trend, "warning_status": warning_status, "updated_at": latest.created_at if latest else None}


@router.get("/early-warnings", response_model=list[EarlyWarningRead])
def early_warnings(db: Session = Depends(get_db)):
    rows = db.query(RiskPredictionDB).filter(RiskPredictionDB.risk_level.in_(["high", "critical"])).order_by(RiskPredictionDB.valid_from.desc()).limit(50).all()
    alerts = {row.incident_id: row.id for row in db.query(NotificationDB).filter(NotificationDB.alert_type == "early_warning").all()}
    zones = {z.id: z.name for z in db.query(ZoneDB).all()}
    return [EarlyWarningRead(alert_id=alerts.get(f"risk:{row.prediction_id}"), prediction_id=row.prediction_id, disaster_type=row.disaster_type, zone=zones.get(row.zone_id, row.zone_id or "Unknown zone"), risk_score=row.risk_score or 0, risk_level=row.risk_level, confidence=row.confidence or 0, contributing_factors=_list(row.contributing_factors), recommendations=_list(row.recommendations), created_at=row.valid_from) for row in rows]


@router.get("/{prediction_id}", response_model=RiskPredictionResponse)
def get_prediction(prediction_id: str, db: Session = Depends(get_db)):
    row = db.query(RiskPredictionDB).filter(RiskPredictionDB.prediction_id == prediction_id).first()
    if row is None and prediction_id.isdigit():
        row = db.query(RiskPredictionDB).filter(RiskPredictionDB.id == int(prediction_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Risk prediction not found")
    zone = db.query(ZoneDB).filter(ZoneDB.id == row.zone_id).first()
    return _response(row, zone.name if zone else row.zone_id or "Unknown zone")


demo_router = APIRouter(prefix="/api/v1/demo", tags=["Demo Scenarios"])


@demo_router.post("/scenarios/flood-critical", response_model=RiskPredictionResponse, status_code=status.HTTP_201_CREATED)
def demo_flood_critical(db: Session = Depends(get_db), _principal=Depends(get_command_principal)):
    """Run the deterministic critical-flood demonstration through live APIs."""
    payload = RiskPredictRequest(
        disaster_type="flood", zone_id="DEMO-ZONE-A", use_latest_data=False,
        weather={"location": "Zone A (DEMO)", "condition": "extreme rainfall", "temperature_c": 29, "humidity": 88, "rainfall_mm": 142, "rainfall_intensity": 48, "wind_speed_kph": 24, "pressure": 1002, "precipitation_probability": 95, "source": "DEMO_SCENARIO"},
        environmental=[
            {"zone_id": "DEMO-ZONE-A", "indicator": "water_level_score", "value": 95, "unit": "score", "source": "DEMO_SCENARIO"},
            {"zone_id": "DEMO-ZONE-A", "indicator": "soil_moisture", "value": 82, "unit": "%", "source": "DEMO_SCENARIO"},
            {"zone_id": "DEMO-ZONE-A", "indicator": "drainage_vulnerability", "value": 90, "unit": "score", "source": "DEMO_SCENARIO"},
            {"zone_id": "DEMO-ZONE-A", "indicator": "community_flood_reports", "value": 17, "unit": "reports", "source": "DEMO_SCENARIO"},
        ],
    )
    row, zone_name, _ = predict(db, payload)
    return _response(row, zone_name)


def _list(value):
    try:
        parsed = value if isinstance(value, list) else json.loads(value or "[]")
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []
