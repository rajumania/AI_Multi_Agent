from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TelemetryIngestRequest(BaseModel):
    vehicle_id: str = Field(..., min_length=1, max_length=50)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    speed: float = Field(0.0, ge=0.0)
    heading: float = Field(0.0, ge=0.0, le=360.0)
    accuracy: float = Field(5.0, ge=0.0)
    timestamp: Optional[str] = None
    assignment_id: Optional[int] = None
    incident_id: Optional[str] = None


class TelemetryIngestResponse(BaseModel):
    status: str
    vehicle_id: str
    latitude: float
    longitude: float
    gps_mode: str
    timestamp: str
    assignment_id: Optional[int] = None
    incident_id: Optional[str] = None
    route_version: Optional[int] = None


class RoadConditionCreate(BaseModel):
    node_a: str = Field(..., min_length=1, max_length=80)
    node_b: str = Field(..., min_length=1, max_length=80)
    status: str = Field(..., pattern="^(blocked|cleared)$")
    reason: str = Field(..., min_length=3, max_length=200)
    incident_id: Optional[str] = Field(default=None, max_length=50)


class TransportTrackingRead(BaseModel):
    assignment_id: int
    incident_id: str
    department: str
    resource_id: Optional[str] = None
    team_identity: Optional[str] = None
    status: str
    incident_location: str
    incident_latitude: Optional[float] = None
    incident_longitude: Optional[float] = None
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    last_gps_update: Optional[datetime] = None
    gps_source: str = "UNAVAILABLE"
    route: Optional[dict] = None
    eta_seconds: Optional[int] = None
    route_warning: Optional[str] = None
