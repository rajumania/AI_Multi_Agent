"""Additive disaster-domain APIs backed by the existing database architecture."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.orm import Session

from backend.api.deps import get_optional_principal
from backend.api.incidents import create_incident
from backend.database.database import get_db
from backend.database.models import (
    CampusResourceDB,
    CommunityDB,
    IncidentDB,
    RegionDB,
    RescueRequestDB,
    RiskPredictionDB,
    WeatherObservationDB,
    ZoneDB,
)
from backend.models.domain import (
    CommunityRead,
    RegionRead,
    RescueRequestCreate,
    RescueRequestRead,
    RiskPredictionRead,
    WeatherObservationRead,
    ZoneRead,
)
from backend.models.incident import DisasterType, IncidentCreate, IncidentRead
from backend.models.resources import CampusResourceRead, ResourceType


router = APIRouter(prefix="/api/v1", tags=["Disaster Domain"])


@router.get("/regions", response_model=List[RegionRead])
def list_regions(db: Session = Depends(get_db)):
    return db.query(RegionDB).order_by(RegionDB.name.asc()).all()


@router.get("/zones", response_model=List[ZoneRead])
def list_zones(region_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(ZoneDB)
    if region_id:
        query = query.filter(ZoneDB.region_id == region_id)
    return query.order_by(ZoneDB.name.asc()).all()


@router.get("/communities", response_model=List[CommunityRead])
def list_communities(zone_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(CommunityDB)
    if zone_id:
        query = query.filter(CommunityDB.zone_id == zone_id)
    return query.order_by(CommunityDB.name.asc()).all()


@router.get("/disasters", response_model=List[IncidentRead])
def list_disasters(
    disaster_type: Optional[DisasterType] = Query(None),
    db: Session = Depends(get_db),
    principal=Depends(get_optional_principal),
):
    query = db.query(IncidentDB).filter(IncidentDB.disaster_type.isnot(None))
    if disaster_type:
        query = query.filter(IncidentDB.disaster_type == disaster_type.value)
    rows = query.order_by(IncidentDB.created_at.desc()).all()
    # The legacy incident visibility policy is intentionally not bypassed by
    # the alias; domain clients should observe the same authorization boundary.
    from backend.api.incidents import _principal_can_view_incident
    return [row for row in rows if _principal_can_view_incident(row, principal)]


@router.post("/disasters", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
def create_disaster(
    payload: IncidentCreate,
    background_tasks: BackgroundTasks,
    region_id: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    principal=Depends(get_optional_principal),
):
    """Create a disaster event through the existing incident intake pipeline."""
    incident = create_incident(payload, background_tasks, db, principal)
    incident.disaster_type = payload.disaster_type.value if payload.disaster_type else "other"
    incident.region_id = region_id
    incident.zone_id = zone_id
    db.commit()
    db.refresh(incident)
    return incident


def _resource_list(resource_types: set[str], db: Session):
    return db.query(CampusResourceDB).filter(CampusResourceDB.resource_type.in_(resource_types)).order_by(CampusResourceDB.name.asc()).all()


@router.get("/shelters", response_model=List[CampusResourceRead])
def list_shelters(db: Session = Depends(get_db)):
    return _resource_list({ResourceType.SHELTER.value}, db)


@router.get("/hospitals", response_model=List[CampusResourceRead])
def list_hospitals(db: Session = Depends(get_db)):
    return _resource_list({ResourceType.HOSPITAL.value, ResourceType.CLINIC.value, ResourceType.MEDICAL_CENTER.value}, db)


@router.get("/emergency-services", response_model=List[CampusResourceRead])
def list_emergency_services(db: Session = Depends(get_db)):
    return _resource_list({"ambulance", "rescue_team", "fire_service", "police", "emergency_service", "security", "fire_response"}, db)


@router.get("/risk-predictions", response_model=List[RiskPredictionRead])
def list_risk_predictions(
    region_id: Optional[str] = Query(None),
    zone_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(RiskPredictionDB)
    if region_id:
        query = query.filter(RiskPredictionDB.region_id == region_id)
    if zone_id:
        query = query.filter(RiskPredictionDB.zone_id == zone_id)
    return query.order_by(RiskPredictionDB.valid_from.desc()).all()


@router.get("/weather-observations", response_model=List[WeatherObservationRead])
def list_weather_observations(db: Session = Depends(get_db)):
    return db.query(WeatherObservationDB).order_by(WeatherObservationDB.observed_at.desc()).limit(100).all()


@router.get("/rescue-requests", response_model=List[RescueRequestRead])
def list_rescue_requests(db: Session = Depends(get_db), principal=Depends(get_optional_principal)):
    rows = db.query(RescueRequestDB).order_by(RescueRequestDB.created_at.desc()).all()
    if principal is not None and principal.is_user and not principal.is_privileged:
        return [row for row in rows if row.user_id == str(principal.id)]
    return rows


@router.post("/rescue-requests", response_model=RescueRequestRead, status_code=status.HTTP_201_CREATED)
def create_rescue_request(payload: RescueRequestCreate, db: Session = Depends(get_db), principal=Depends(get_optional_principal)):
    now = datetime.now(timezone.utc)
    user_id = str(principal.id) if principal is not None and principal.is_user else None
    row = RescueRequestDB(
        request_id=f"RES-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}",
        location=payload.location.strip(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        people_count=payload.people_count,
        injured_count=payload.injured_count,
        children_count=payload.children_count,
        elderly_count=payload.elderly_count,
        medical_emergency=1 if payload.medical_emergency else 0,
        hazard_level=payload.hazard_level.value,
        description=payload.description.strip(),
        region_id=payload.region_id,
        zone_id=payload.zone_id,
        user_id=user_id,
        status="reported",
        priority_score=None,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
