from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ResponsePlanBase(BaseModel):
    incident_id: str = Field(..., description="Target incident ID")
    title: str = Field(..., description="Short response plan title")
    severity: str = Field(..., description="Incident severity level")
    location: str = Field(..., description="Campus incident location")
    recommended_actions: List[str] = Field(default_factory=list, description="Ordered recommended response steps")
    allocated_resources: List[str] = Field(default_factory=list, description="List of physical campus resource IDs")
    requires_approval: bool = Field(default=True, description="Whether high-impact actions mandate human operator approval")
    approval_status: ApprovalStatus = Field(default=ApprovalStatus.PENDING, description="Current approval state")
    approved_by: Optional[str] = Field(default=None, description="Operator or commander identifier")
    approval_notes: Optional[str] = Field(default=None, description="Operator approval justification notes")


class ResponsePlanCreate(ResponsePlanBase):
    pass


class ResponsePlanRead(ResponsePlanBase):
    plan_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalDecisionPayload(BaseModel):
    decision: str = Field(..., min_length=6, max_length=10, description="'approve' or 'reject'")
    operator_name: str = Field(default="Campus Safety Commander", min_length=1, max_length=100, description="Name/Role of authorizing person")
    notes: Optional[str] = Field(default=None, max_length=2000, description="Optional justification notes")
