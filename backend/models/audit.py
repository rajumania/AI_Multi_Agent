from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class AuditLogBase(BaseModel):
    incident_id: Optional[str] = Field(default=None, description="Related incident ID")
    plan_id: Optional[str] = Field(default=None, description="Related response plan ID")
    action_type: str = Field(..., description="Categorical action key (e.g., incident_created, approval_decision)")
    actor: str = Field(default="system", description="Entity that initiated the action")
    description: str = Field(..., description="Human-readable audit message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Structured payload metadata")


class AuditLogCreate(AuditLogBase):
    pass


class AuditLogRead(AuditLogBase):
    id: int
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
