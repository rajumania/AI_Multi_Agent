from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ResourceType(str, Enum):
    AMBULANCE = "ambulance"
    SECURITY = "security"
    FIRST_AID = "first_aid"
    SHELTER = "shelter"
    VEHICLE = "vehicle"
    MEDICAL_CENTER = "medical_center"
    FACILITY = "facility"
    FIRE_RESPONSE = "fire_response"
    OTHER = "other"


class AvailabilityStatus(str, Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    UNAVAILABLE = "unavailable"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class CampusResourceBase(BaseModel):
    resource_id: str = Field(..., description="Unique identifier (e.g., AMB-001)")
    name: str = Field(..., description="Display name of the resource")
    resource_type: ResourceType = Field(..., description="Category of resource")
    location: str = Field(..., description="Campus station or location name")
    latitude: Optional[float] = Field(default=None, description="Campus map latitude coordinate")
    longitude: Optional[float] = Field(default=None, description="Campus map longitude coordinate")
    availability_status: AvailabilityStatus = Field(
        default=AvailabilityStatus.AVAILABLE,
        description="Current readiness status"
    )
    capacity: Optional[int] = Field(default=None, description="Maximum occupant or handling capacity")
    quantity: Optional[int] = Field(default=1, description="Quantity of items/units available")
    contact: Optional[str] = Field(default=None, description="Direct radio or contact extension")


class CampusResourceCreate(CampusResourceBase):
    pass


class CampusResourceRead(CampusResourceBase):
    id: Optional[int] = None
    last_updated: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

