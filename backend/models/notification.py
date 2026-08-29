from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class NotificationRead(BaseModel):
    id: int
    recipient_type: str
    department: Optional[str] = None
    incident_id: Optional[str] = None
    title: str
    message: str
    level: str
    read: int
    created_at: datetime
    alert_type: Optional[str] = None
    audience: Optional[str] = None
    region_id: Optional[str] = None
    zone_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    is_demo: int = 0
    priority: str = "medium"
    lifecycle_status: str = "CREATED"
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)
