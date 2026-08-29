"""Pydantic contracts for the additive disaster-response domain foundation."""

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.config import settings
from backend.models.incident import DisasterType, IncidentStatus, SeverityLevel


class RegionRead(BaseModel):
    id: str
    name: str
    risk_status: str = "demo"
    population: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_demo: bool = False
    model_config = ConfigDict(from_attributes=True)


class ZoneRead(RegionRead):
    region_id: str
    elevation_m: Optional[float] = None
    slope_deg: Optional[float] = None
    vulnerability_score: Optional[float] = None
    historical_disaster_frequency: Optional[float] = None
    river_proximity_km: Optional[float] = None
    drainage_vulnerability: Optional[float] = None
    hazard_classification: Optional[str] = None
    coastal_vulnerability: Optional[float] = None


class CommunityRead(BaseModel):
    id: str
    name: str
    zone_id: Optional[str] = None
    population: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_demo: bool = False
    model_config = ConfigDict(from_attributes=True)


class RescueRequestCreate(BaseModel):
    location: str = Field(..., min_length=2)
    people_count: int = Field(default=1, ge=1)
    injured_count: int = Field(default=0, ge=0)
    children_count: int = Field(default=0, ge=0)
    elderly_count: int = Field(default=0, ge=0)
    medical_emergency: bool = False
    hazard_level: SeverityLevel = SeverityLevel.UNKNOWN
    description: str = Field(..., min_length=3)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    region_id: Optional[str] = None
    zone_id: Optional[str] = None


class RescueRequestRead(RescueRequestCreate):
    request_id: str
    status: str
    priority_score: Optional[float] = None
    user_id: Optional[str] = None
    incident_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WeatherObservationRead(BaseModel):
    id: int
    region_id: Optional[str] = None
    zone_id: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    observed_at: datetime
    received_at: datetime
    condition: str
    rainfall_mm: Optional[float] = None
    rainfall_intensity: Optional[float] = None
    humidity: Optional[float] = None
    wind_speed_kph: Optional[float] = None
    temperature_c: Optional[float] = Field(default=None, ge=-100, le=70)
    wind_direction: Optional[float] = None
    pressure: Optional[float] = None
    precipitation_probability: Optional[float] = None
    source: str = "demo"
    status: str = "UNKNOWN"
    freshness_seconds: Optional[float] = None

    @model_validator(mode="after")
    def derive_provider_state(self):
        observed = self.observed_at if self.observed_at.tzinfo else self.observed_at.replace(tzinfo=timezone.utc)
        received = self.received_at if self.received_at.tzinfo else self.received_at.replace(tzinfo=timezone.utc)
        self.freshness_seconds = max(0.0, (received - observed).total_seconds())
        source = self.source.upper()
        if "OFFLINE" in source:
            self.status = "OFFLINE"
        elif "DEMO" in source or "SIMULATION" in source:
            self.status = "FALLBACK"
            self.freshness_seconds = None
        elif self.freshness_seconds > max(1, settings.WEATHER_STALE_AFTER_MINUTES) * 60:
            self.status = "STALE"
        else:
            self.status = "LIVE"
        return self
    model_config = ConfigDict(from_attributes=True)


class EnvironmentalObservationRead(BaseModel):
    id: int
    region_id: Optional[str] = None
    zone_id: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    observed_at: datetime
    received_at: datetime
    indicator: str
    value: float = Field(..., ge=-10000, le=1000000)
    unit: Optional[str] = None
    source: str = "demo"
    status: str = "UNKNOWN"
    freshness_seconds: Optional[float] = None

    @model_validator(mode="after")
    def derive_provider_state(self):
        observed = self.observed_at if self.observed_at.tzinfo else self.observed_at.replace(tzinfo=timezone.utc)
        received = self.received_at if self.received_at.tzinfo else self.received_at.replace(tzinfo=timezone.utc)
        self.freshness_seconds = max(0.0, (received - observed).total_seconds())
        source = self.source.upper()
        if "OFFLINE" in source:
            self.status = "OFFLINE"
        elif "DEMO" in source or "SIMULATION" in source:
            self.status = "FALLBACK"
            self.freshness_seconds = None
        elif self.freshness_seconds > max(1, settings.WEATHER_STALE_AFTER_MINUTES) * 60:
            self.status = "STALE"
        else:
            self.status = "LIVE"
        return self
    model_config = ConfigDict(from_attributes=True)


class RiskPredictionRead(BaseModel):
    id: int
    prediction_id: Optional[str] = None
    region_id: Optional[str] = None
    zone_id: Optional[str] = None
    disaster_type: DisasterType
    risk_level: SeverityLevel
    probability: Optional[float] = None
    risk_score: Optional[float] = None
    confidence: Optional[float] = None
    features: Any = None
    contributing_factors: Any = None
    recommendations: Any = None
    explanation: Optional[str] = None
    data_status: str = "demo"
    data_freshness_seconds: Optional[float] = None
    stale: bool = False
    rationale: Optional[str] = None
    valid_from: datetime
    valid_until: Optional[datetime] = None
    status: str = "foundation"
    model_config = ConfigDict(from_attributes=True)


class WeatherObservationCreate(BaseModel):
    zone_id: Optional[str] = None
    region_id: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    observed_at: Optional[datetime] = None
    condition: str = "unknown"
    temperature_c: Optional[float] = Field(default=None, ge=-100, le=70)
    humidity: Optional[float] = Field(default=None, ge=0, le=100)
    rainfall_mm: Optional[float] = Field(default=None, ge=0)
    rainfall_intensity: Optional[float] = Field(default=None, ge=0)
    wind_speed_kph: Optional[float] = Field(default=None, ge=0)
    wind_direction: Optional[float] = Field(default=None, ge=0, le=360)
    pressure: Optional[float] = Field(default=None, ge=800, le=1200)
    precipitation_probability: Optional[float] = Field(default=None, ge=0, le=100)
    source: str = "manual"

    @field_validator("temperature_c", "rainfall_mm", "rainfall_intensity", "wind_speed_kph", "pressure")
    @classmethod
    def finite_measurement(cls, value):
        if value is not None and (value != value or value in (float("inf"), float("-inf"))):
            raise ValueError("Measurements must be finite numbers")
        return value

    @model_validator(mode="after")
    def coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        return self


class EnvironmentalObservationCreate(BaseModel):
    zone_id: Optional[str] = None
    region_id: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    observed_at: Optional[datetime] = None
    indicator: str = Field(..., min_length=2)
    value: float = Field(..., ge=-10000, le=1000000)
    unit: Optional[str] = None
    source: str = "manual"

    @field_validator("value")
    @classmethod
    def finite_value(cls, value):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("Environmental values must be finite numbers")
        return value

    @model_validator(mode="after")
    def coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        return self


class RiskPredictRequest(BaseModel):
    disaster_type: DisasterType
    zone_id: Optional[str] = None
    location: Optional[str] = None
    region_id: Optional[str] = None
    use_latest_data: bool = True
    weather: Optional[WeatherObservationCreate] = None
    environmental: list[EnvironmentalObservationCreate] = Field(default_factory=list)


class RiskPredictionResponse(BaseModel):
    prediction_id: str
    disaster_type: DisasterType
    zone_id: Optional[str] = None
    zone: str
    region_id: Optional[str] = None
    risk_score: float
    risk_level: SeverityLevel
    confidence: float
    contributing_factors: list[str]
    recommendations: list[str]
    explanation: str
    features: dict[str, float]
    data_status: str
    data_freshness_seconds: Optional[float] = None
    stale: bool = False
    created_at: datetime


class EarlyWarningRead(BaseModel):
    alert_id: Optional[int] = None
    prediction_id: str
    disaster_type: DisasterType
    zone: str
    risk_score: float
    risk_level: SeverityLevel
    confidence: float
    contributing_factors: list[str]
    recommendations: list[str]
    created_at: datetime
