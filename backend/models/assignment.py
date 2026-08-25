from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import List, Optional
import json

class DepartmentAssignmentRead(BaseModel):
    id: int
    incident_id: str
    department: str
    status: str
    accepted: int
    message: Optional[str] = None
    responder: Optional[str] = None
    assigned_resources: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator("assigned_resources", mode="before")
    @classmethod
    def parse_assigned_resources(cls, value):
        # SQLite stores this field as JSON text; API consumers receive a list.
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except (TypeError, ValueError):
                return []
        return value or []

class AssignmentDecisionPayload(BaseModel):
    accepted: bool
    message: Optional[str] = None

class AssignmentTeamPayload(BaseModel):
    resource_ids: List[str]
    team_name: Optional[str] = None

class AssignmentStatusPayload(BaseModel):
    status: str
    message: Optional[str] = None
