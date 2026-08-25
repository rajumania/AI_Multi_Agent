from datetime import datetime, timezone
from enum import Enum
import json
import math
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict, model_validator


class IncidentType(str, Enum):
    FIRE = "fire"
    CHEMICAL = "chemical"
    MEDICAL = "medical"
    SECURITY = "security"
    ACCIDENT = "accident"
    WEATHER = "weather"
    CROWD = "crowd"
    FACILITY = "facility"
    OTHER = "other"
    UNKNOWN = "unknown"


class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class IncidentStatus(str, Enum):
    REPORTED = "reported"
    ANALYZING = "analyzing"
    ASSESSING = "assessing"
    CLASSIFIED = "classified"
    PLANNING = "planning"
    RESPONSE_PLANNING = "response_planning"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    AUTHORIZED = "authorized"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    RESPONSE_IN_PROGRESS = "response_in_progress"
    DISPATCHED = "dispatched"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    ACTION_FAILED = "action_failed"



class IncidentBase(BaseModel):
    description: str = Field(..., min_length=3, description="Detailed description of the incident")
    incident_type: IncidentType = Field(default=IncidentType.UNKNOWN, description="Conceptual category of incident")
    location: str = Field(..., min_length=2, description="Campus location or building name")
    severity: SeverityLevel = Field(default=SeverityLevel.UNKNOWN, description="Assessed severity level")
    injured_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of confirmed injured individuals. Must be null if unknown."
    )
    evidence_source: Optional[str] = Field(default="direct_report", description="Origin/source of evidence")
    reported_by: Optional[str] = Field(default="Campus Operator", description="Reporter identifier or role")
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Exact incident latitude when selected")
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Exact incident longitude when selected")

    @field_validator("latitude", "longitude")
    @classmethod
    def validate_finite_coordinate(cls, value):
        if value is not None and not math.isfinite(value):
            raise ValueError("Coordinates must be finite numbers.")
        return value

    @model_validator(mode="after")
    def validate_coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must be supplied together.")
        return self

    @field_validator("injured_count", mode="before")
    @classmethod
    def validate_injured_count(cls, v):
        # Prevent string 'unknown' or empty strings from breaking parsing; keep as None
        if v is None or v == "" or str(v).lower() in ("unknown", "null", "none"):
            return None
        if isinstance(v, int):
            return v
        try:
            return int(v)
        except (ValueError, TypeError):
            return None


class IncidentCreate(IncidentBase):
    pass


class IncidentCloseRequest(BaseModel):
    closed_by: str = Field(default="Authorized Campus Operator")
    closing_notes: Optional[str] = Field(default="Incident record administratively finalized and archived.")


class IncidentConfirmResponseRequest(BaseModel):
    confirmed_by: str = Field(default="Authorized Campus Operator")
    notes: Optional[str] = Field(default="First responders confirmed arrival on-scene and active management underway.")


class IncidentRead(IncidentBase):
    incident_id: str
    status: IncidentStatus = IncidentStatus.REPORTED
    ai_provider_status: Optional[str] = None
    current_step: Optional[str] = None
    next_action: Optional[str] = None
    summary: Optional[str] = None
    confidence: Optional[float] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    resolution_note: Optional[str] = None
    required_departments: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("required_departments", mode="before")
    @classmethod
    def parse_required_departments(cls, value):
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except (TypeError, ValueError):
                return []
        return value or []


class SupervisorAnalysisResult(BaseModel):
    incident_type: IncidentType = Field(..., description="Classified incident category")
    severity: SeverityLevel = Field(..., description="Assessed severity level")
    location: str = Field(..., description="Extracted campus location")
    injured_count: Optional[int] = Field(
        default=None,
        description="Preserved casualty count (strictly null if unknown, never defaulted to 0)"
    )
    summary: str = Field(..., description="Concise emergency briefing summary")
    confidence: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
        description="Confidence score for the classification and extraction"
    )
    recommended_agents: list[str] = Field(
        default_factory=list,
        description="Sub-agents relevant to the incident (e.g. security, medical, transport, communication)"
    )
    key_observations: list[str] = Field(
        default_factory=list,
        description="Safety-aligned observations explaining the assessment"
    )


class IncidentAnalysisResponse(BaseModel):
    incident: IncidentRead
    analysis: SupervisorAnalysisResult


class MultiAgentOrchestrationResponse(BaseModel):
    incident: IncidentRead
    delegated_agents: list[str] = Field(default_factory=list)
    security_result: Optional[dict] = None
    medical_result: Optional[dict] = None
    transport_result: Optional[dict] = None
    communication_result: Optional[dict] = None
    fire_result: Optional[dict] = None
    facilities_result: Optional[dict] = None
    mcp_resources: list[dict] = Field(default_factory=list, description="Real physical campus resources discovered via MCP")
    all_recommendations: list[str] = Field(default_factory=list)
    required_approvals: list[str] = Field(default_factory=list)
    audit_trail: list[str] = Field(default_factory=list)
    execution_status: str = "orchestrated"



