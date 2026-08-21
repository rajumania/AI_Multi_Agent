from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class BroadcastNotification(BaseModel):
    channel: str = Field(..., description="Communication channel (e.g. Campus SMS, PA Audio, Mobile App)")
    recipient_group: str = Field(..., description="Target audience (e.g. All Students, Building Wardens, Emergency Responders)")
    headline: str = Field(..., description="Short broadcast title")
    message: str = Field(..., description="Full broadcast message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="sent", description="Delivery status (e.g. sent, delivered)")


class DispatchExecutionResult(BaseModel):
    plan_id: str
    incident_id: str
    execution_status: str = Field(default="dispatched")
    dispatched_resources: List[str] = Field(default_factory=list, description="Resource IDs set to busy/dispatched")
    broadcast_alerts: List[BroadcastNotification] = Field(default_factory=list)
    executed_at: datetime
    execution_notes: str


class IncidentResolutionRequest(BaseModel):
    resolution_notes: str = Field(..., description="Summary of actions taken and incident conclusion")
    resolved_by: str = Field(default="Campus Safety Commander", description="Name/role of commander closing incident")
