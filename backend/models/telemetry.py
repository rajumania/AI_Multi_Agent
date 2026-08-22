from pydantic import BaseModel, Field
from typing import Optional


class TelemetryIngestRequest(BaseModel):
    vehicle_id: str = Field(..., example="AMB-001")
    latitude: float = Field(..., example=16.2334)
    longitude: float = Field(..., example=80.5513)
    speed: float = Field(0.0, example=31.5)
    heading: float = Field(0.0, example=72.0)
    accuracy: float = Field(5.0, example=8.2)
    timestamp: Optional[str] = None


class TelemetryIngestResponse(BaseModel):
    status: str
    vehicle_id: str
    latitude: float
    longitude: float
    gps_mode: str
    timestamp: str
