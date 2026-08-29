"""API contracts for location-driven external disaster intelligence."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from backend.models.incident import DisasterType


class IntelligencePreviewRequest(BaseModel):
    description: str = Field(..., min_length=3)
    location: str = Field(default="Selected coordinates", min_length=2)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    disaster_type: DisasterType = DisasterType.OTHER
    injured_count: int | None = Field(default=None, ge=0)
    image_url: str | None = Field(default=None, max_length=500)
    origin_latitude: float | None = Field(default=None, ge=-90, le=90)
    origin_longitude: float | None = Field(default=None, ge=-180, le=180)
    earthquake_radius_km: float | None = Field(default=None, gt=0, le=2000)
    earthquake_lookback_hours: int | None = Field(default=None, gt=0, le=720)
    earthquake_min_magnitude: float | None = Field(default=None, ge=-2, le=12)

    @model_validator(mode="after")
    def coordinate_pairs(self):
        if (self.origin_latitude is None) != (self.origin_longitude is None):
            raise ValueError("origin latitude and longitude must be supplied together")
        return self


class IntelligencePreviewResponse(BaseModel):
    location: str
    latitude: float
    longitude: float
    reverse_geocode: dict[str, Any] | None = None
    weather: dict[str, Any]
    environmental: list[dict[str, Any]]
    earthquakes: list[dict[str, Any]]
    earthquake_status: str
    severe_weather: list[dict[str, Any]]
    severe_weather_status: str
    geographic: dict[str, Any]
    routes: list[dict[str, Any]]
    evidence: dict[str, Any]
    risk: dict[str, Any]
    departments: list[dict[str, Any]]
    image_analysis: dict[str, Any]
    provider_status: list[dict[str, Any]]
    analyzed_at: str
    data_status: str = "UNKNOWN"
    weather_error: str | None = None
