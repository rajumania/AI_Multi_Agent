"""Typed contracts for Phase 3 sensors, triggers, travel and agent runs."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SensorObservationCreate(BaseModel):
    sensor_id: str = Field(..., min_length=2, max_length=80)
    sensor_type: str = Field(..., min_length=2, max_length=50)
    zone_id: Optional[str] = None
    region_id: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    value: float = Field(..., ge=-1000000, le=1000000)
    unit: Optional[str] = None
    observed_at: Optional[datetime] = None
    source: str = "DEMO_SIMULATION"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("value")
    @classmethod
    def finite_value(cls, value: float) -> float:
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("Sensor values must be finite")
        return value

    @model_validator(mode="after")
    def coordinates_match(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        return self


class SensorObservationRead(SensorObservationCreate):
    id: int
    received_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SensorEventRead(BaseModel):
    id: int
    event_id: str
    sensor_id: str
    sensor_type: str
    region_id: Optional[str] = None
    zone_id: Optional[str] = None
    previous_value: Optional[float] = None
    current_value: float
    change_value: Optional[float] = None
    anomaly_level: str
    description: str
    source: str
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DisasterEventTrigger(BaseModel):
    event_source: str = Field(default="community", min_length=2)
    disaster_type: Optional[str] = None
    location: str = Field(..., min_length=2)
    zone_id: Optional[str] = None
    region_id: Optional[str] = None
    description: str = Field(..., min_length=3)
    image_url: Optional[str] = None
    people_count: int = Field(default=1, ge=1)
    community_reports: int = Field(default=0, ge=0, le=100000)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        return self


class SensorSimulationRequest(BaseModel):
    scenario: str = Field(default="nepal_mountain", min_length=2)


class TravelSafetyRequest(BaseModel):
    destination: str = Field(..., min_length=2)
    travel_at: Optional[datetime] = None
    current_location: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        return self


class TravelSafetyResponse(BaseModel):
    destination: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    risk_score: float
    risk_level: str
    hazards: list[str]
    weather_summary: str
    active_alerts: list[str]
    route_status: str
    recommendation: str
    reasons: list[str]
    safer_alternatives: list[str] = Field(default_factory=list)
    last_updated: datetime
    data_status: str = "UNKNOWN"
    data_sources: list[str] = Field(default_factory=list)
    freshness_seconds: Optional[float] = None
    provider_status: dict[str, str] = Field(default_factory=dict)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    earthquakes: list[dict[str, Any]] = Field(default_factory=list)


class DepartmentRead(BaseModel):
    id: str
    name: str
    consumes: list[str]


class AgentRunRead(BaseModel):
    run_id: str
    event_id: str
    status: str
    required_agents: list[str]
    agent_results: dict[str, Any]
    agent_errors: list[str]
    created_at: datetime
    completed_at: Optional[datetime] = None
