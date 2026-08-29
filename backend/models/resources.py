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
    HOSPITAL = "hospital"
    CLINIC = "clinic"
    RESCUE_TEAM = "rescue_team"
    FIRE_SERVICE = "fire_service"
    POLICE = "police"
    EMERGENCY_SERVICE = "emergency_service"
    BOAT = "boat"
    FOOD = "food"
    WATER = "water"
    EMERGENCY_KIT = "emergency_kit"
    OTHER = "other"


class AvailabilityStatus(str, Enum):
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    BUSY = "busy"
    UNAVAILABLE = "unavailable"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"
    # Legacy dispatch states remain accepted for backwards compatibility.
    RESERVED = "reserved"
    EN_ROUTE = "en_route"


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
    current_assignment: Optional[str] = Field(default=None, description="Incident, plan, or team currently using this resource")
    department: Optional[str] = Field(default=None, description="Owning emergency service or response department")
    emergency_beds: Optional[int] = Field(default=None, ge=0, description="Emergency beds for hospital resources")
    is_demo: bool = Field(default=False, description="Clearly marked development/demo data")


class CampusResourceCreate(CampusResourceBase):
    pass


class CampusResourceRead(CampusResourceBase):
    id: Optional[int] = None
    last_updated: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

