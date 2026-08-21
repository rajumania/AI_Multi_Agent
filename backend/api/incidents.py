import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database.database import get_db
from backend.database.models import IncidentDB
from backend.agents.supervisor import supervisor_agent
from backend.graph.workflow import run_emergency_workflow
from backend.models.incident import (
    IncidentCreate,
    IncidentRead,
    IncidentStatus,
    IncidentType,
    SeverityLevel,
    SupervisorAnalysisResult,
    IncidentAnalysisResponse,
    MultiAgentOrchestrationResponse,
)

from backend.services.audit_service import audit_service

router = APIRouter(prefix="/api/v1/incidents", tags=["Incidents"])


def generate_incident_id() -> str:
    """Generate a readable, unique incident identifier (e.g., INC-20260821-4A8F)."""
    now = datetime.now(timezone.utc)
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"INC-{now.strftime('%Y%m%d')}-{short_uuid}"


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
def create_incident(incident_in: IncidentCreate, db: Session = Depends(get_db)):
    """
    Intake a new emergency incident report.
    Validates payload and preserves null for unknown injured_count (never defaulting to 0).
    """
    now = datetime.now(timezone.utc)
    incident_id = generate_incident_id()

    db_incident = IncidentDB(
        incident_id=incident_id,
        description=incident_in.description.strip(),
        incident_type=incident_in.incident_type.value,
        location=incident_in.location.strip(),
        severity=incident_in.severity.value,
        injured_count=incident_in.injured_count,  # Strictly None if unknown
        evidence_source=incident_in.evidence_source,
        reported_by=incident_in.reported_by,
        status=IncidentStatus.REPORTED.value,
        created_at=now,
        updated_at=now,
    )

    db.add(db_incident)
    db.commit()
    db.refresh(db_incident)

    # Audit Logging
    audit_service.log(
        action_type="incident_created",
        description=f"Incident '{incident_id}' lodged by '{db_incident.reported_by}' at '{db_incident.location}'.",
        incident_id=db_incident.incident_id,
        actor=db_incident.reported_by or "reporter",
        details={
            "description": db_incident.description,
            "incident_type": db_incident.incident_type,
            "severity": db_incident.severity,
            "injured_count": db_incident.injured_count,
        },
        db=db
    )

    return db_incident



@router.get("", response_model=List[IncidentRead])
def list_incidents(
    status_filter: Optional[IncidentStatus] = Query(None, alias="status"),
    severity_filter: Optional[SeverityLevel] = Query(None, alias="severity"),
    incident_type_filter: Optional[IncidentType] = Query(None, alias="type"),
    db: Session = Depends(get_db),
):
    """
    Retrieve all reported incidents, ordered by most recent first.
    """
    query = db.query(IncidentDB)

    if status_filter:
        query = query.filter(IncidentDB.status == status_filter.value)
    if severity_filter:
        query = query.filter(IncidentDB.severity == severity_filter.value)
    if incident_type_filter:
        query = query.filter(IncidentDB.incident_type == incident_type_filter.value)

    incidents = query.order_by(desc(IncidentDB.created_at)).all()
    return incidents


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    """
    Retrieve a specific incident by its ID.
    """
    incident = db.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID '{incident_id}' not found."
        )
    return incident


@router.post("/{incident_id}/analyze", response_model=IncidentAnalysisResponse)
def analyze_incident_by_id(incident_id: str, db: Session = Depends(get_db)):
    """
    Step 3 Supervisor AI Agent:
    - Analyzes incident description using centralized LLM (Gemini / OpenAI / safety fallback)
    - Classifies category and assesses severity
    - Extracts location and strictly preserves unknown injured count as null
    - Updates SQLite record with summary, confidence, and classified status
    """
    db_incident = db.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
    if not db_incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID '{incident_id}' not found."
        )

    # Perform Supervisor AI Agent Analysis
    analysis_result = supervisor_agent.analyze_incident(
        description=db_incident.description,
        reported_location=db_incident.location,
        reported_by=db_incident.reported_by,
    )

    # Update database record with AI findings
    now = datetime.now(timezone.utc)
    db_incident.incident_type = analysis_result.incident_type.value
    db_incident.severity = analysis_result.severity.value
    if analysis_result.location and analysis_result.location != "Campus Premises":
        db_incident.location = analysis_result.location
    if db_incident.injured_count is None:
        db_incident.injured_count = analysis_result.injured_count
    db_incident.summary = analysis_result.summary
    db_incident.confidence = analysis_result.confidence
    db_incident.status = IncidentStatus.CLASSIFIED.value
    db_incident.updated_at = now

    db.commit()
    db.refresh(db_incident)

    # Audit Logging
    audit_service.log(
        action_type="ai_classification",
        description=f"Supervisor AI classified incident '{incident_id}' as {db_incident.incident_type.upper()} ({db_incident.severity.upper()}) at {db_incident.location}.",
        incident_id=db_incident.incident_id,
        actor="supervisor_ai",
        details={
            "summary": analysis_result.summary,
            "confidence": analysis_result.confidence,
            "recommended_agents": analysis_result.recommended_agents,
        },
        db=db
    )


    return IncidentAnalysisResponse(
        incident=IncidentRead.model_validate(db_incident),
        analysis=analysis_result
    )


@router.post("/analyze-raw", response_model=SupervisorAnalysisResult)
def analyze_raw_text(
    payload: IncidentCreate,
):
    """
    Step 3 Standalone / Testing Endpoint:
    Directly run Supervisor AI Agent on raw text input without modifying SQLite database.
    """
    return supervisor_agent.analyze_incident(
        description=payload.description,
        reported_location=payload.location,
        reported_by=payload.reported_by,
    )


@router.post("/{incident_id}/orchestrate", response_model=MultiAgentOrchestrationResponse)
def orchestrate_incident(incident_id: str, db: Session = Depends(get_db)):
    """
    Step 4 LangGraph Multi-Agent Orchestration Endpoint:
    Executes LangGraph state graph across Supervisor, Security, Medical, Transport, and Communication Agents.
    Consolidates specialized recommendations and sets status to 'response_planning'.
    """
    db_incident = db.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
    if not db_incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID '{incident_id}' not found."
        )

    # Initialize Graph State from DB record
    initial_state = {
        "incident_id": db_incident.incident_id,
        "description": db_incident.description,
        "location": db_incident.location,
        "incident_type": db_incident.incident_type,
        "severity": db_incident.severity,
        "injured_count": db_incident.injured_count,
        "evidence_source": db_incident.evidence_source,
        "reported_by": db_incident.reported_by,
        "summary": db_incident.summary or "",
        "audit_trail": []
    }

    # Execute LangGraph Multi-Agent Workflow
    final_state = run_emergency_workflow(initial_state)

    # Update database record
    now = datetime.now(timezone.utc)
    if final_state.get("incident_type"):
        db_incident.incident_type = final_state["incident_type"]
    if final_state.get("severity"):
        db_incident.severity = final_state["severity"]
    if final_state.get("location") and final_state["location"] != "Campus Premises":
        db_incident.location = final_state["location"]
    if final_state.get("summary"):
        db_incident.summary = final_state["summary"]
    if final_state.get("confidence"):
        db_incident.confidence = final_state["confidence"]
    if db_incident.injured_count is None:
        db_incident.injured_count = final_state.get("injured_count")

    db_incident.status = IncidentStatus.RESPONSE_PLANNING.value
    db_incident.updated_at = now

    db.commit()
    db.refresh(db_incident)

    # Audit Logging
    audit_service.log(
        action_type="agent_execution",
        description=f"LangGraph executed {len(final_state.get('delegated_agents', []))} agents for incident '{incident_id}'.",
        incident_id=db_incident.incident_id,
        actor="langgraph_orchestrator",
        details={
            "delegated_agents": final_state.get("delegated_agents", []),
            "recommendation_count": len(final_state.get("all_recommendations", [])),
            "mcp_resources": [r["resource_id"] for r in final_state.get("mcp_resources", []) if "resource_id" in r]
        },
        db=db
    )

    return MultiAgentOrchestrationResponse(
        incident=IncidentRead.model_validate(db_incident),
        delegated_agents=final_state.get("delegated_agents", []),
        security_result=final_state.get("security_result"),
        medical_result=final_state.get("medical_result"),
        transport_result=final_state.get("transport_result"),
        communication_result=final_state.get("communication_result"),
        mcp_resources=final_state.get("mcp_resources", []),
        all_recommendations=final_state.get("all_recommendations", []),
        required_approvals=final_state.get("required_approvals", []),
        audit_trail=final_state.get("audit_trail", []),
        execution_status=final_state.get("execution_status", "orchestrated")
    )




