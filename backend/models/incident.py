from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class IncidentType(str, Enum):
    FIRE = "fire"
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
    CLASSIFIED = "classified"
    RESPONSE_PLANNING = "response_planning"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    DISPATCHED = "dispatched"
    RESOLVED = "resolved"



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


class IncidentRead(IncidentBase):
    incident_id: str
    status: IncidentStatus = IncidentStatus.REPORTED
    summary: Optional[str] = None
    confidence: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
    mcp_resources: list[dict] = Field(default_factory=list, description="Real physical campus resources discovered via MCP")
    all_recommendations: list[str] = Field(default_factory=list)
    required_approvals: list[str] = Field(default_factory=list)
    audit_trail: list[str] = Field(default_factory=list)
    execution_status: str = "orchestrated"



