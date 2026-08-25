from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


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

    model_config = ConfigDict(from_attributes=True)
