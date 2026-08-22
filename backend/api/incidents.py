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
    IncidentCloseRequest,
    IncidentConfirmResponseRequest,
    SupervisorAnalysisResult,
    IncidentAnalysisResponse,
    MultiAgentOrchestrationResponse,
)

from backend.services.audit_service import audit_service
from backend.services.severity_engine import severity_engine
from backend.services.event_engine import event_engine
from backend.services.duplicate_service import duplicate_service

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

    event_engine.publish_event(
        event_name="incident_created",
        incident_id=db_incident.incident_id,
        payload={
            "event_name": "incident_created",
            "description": f"Incident reported at {db_incident.location}.",
            "incident_type": db_incident.incident_type,
            "severity": db_incident.severity,
            "location": db_incident.location,
        },
        db=db,
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

    # Deterministic Severity & Explainability Evaluation
    sev_eval = severity_engine.evaluate(
        incident_type=analysis_result.incident_type.value,
        description=db_incident.description,
        location=analysis_result.location or db_incident.location,
        injured_count=db_incident.injured_count if db_incident.injured_count is not None else analysis_result.injured_count,
        corroboration_count=1
    )

    # Update database record with AI findings
    now = datetime.now(timezone.utc)
    db_incident.incident_type = analysis_result.incident_type.value
    db_incident.severity = sev_eval.level  # Use auditable deterministic severity rating
    if analysis_result.location and analysis_result.location != "Campus Premises":
        db_incident.location = analysis_result.location
    if db_incident.injured_count is None:
        db_incident.injured_count = analysis_result.injured_count
    db_incident.summary = sev_eval.explanation
    db_incident.confidence = sev_eval.confidence
    db_incident.status = IncidentStatus.CLASSIFIED.value
    db_incident.current_step = f"Incident classified as {db_incident.incident_type.upper()} ({db_incident.severity.upper()} severity) at {db_incident.location}."
    db_incident.next_action = "Resource availability check and response plan preparation."
    db_incident.updated_at = now

    db.commit()
    db.refresh(db_incident)

    # Log AI Decision Trace
    event_engine.log_trace(
        incident_id=incident_id,
        agent_name="Supervisor Agent",
        action="evaluate_incident_intake",
        thought=f"Assessed description for {db_incident.location}: Classified as {db_incident.incident_type.upper()}.",
        confidence=sev_eval.confidence,
        why=sev_eval.explanation
    )

    # Audit Logging
    audit_service.log(
        action_type="ai_classification",
        description=f"Supervisor AI classified incident '{incident_id}' as {db_incident.incident_type.upper()} ({db_incident.severity.upper()}) at {db_incident.location}.",
        incident_id=db_incident.incident_id,
        actor="supervisor_ai",
        details={
            "summary": sev_eval.explanation,
            "score": sev_eval.score,
            "confidence": sev_eval.confidence,
            "breakdown": sev_eval.breakdown,
            "recommended_agents": analysis_result.recommended_agents,
        },
        db=db
    )

    event_engine.publish_event(
        event_name="incident_updated",
        incident_id=incident_id,
        payload={
            "event_name": "incident_updated",
            "description": f"AI classified incident as {db_incident.severity.upper()}.",
            "status": db_incident.status,
            "severity": db_incident.severity,
            "incident_type": db_incident.incident_type,
        },
        db=db,
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
    db_incident.current_step = "Available response resources verified and recommended action plan prepared."
    db_incident.next_action = "Review recommended response plan and authorize emergency deployment."
    db_incident.updated_at = now

    db.commit()
    db.refresh(db_incident)

    # Audit Logging (User-friendly action description)
    audit_service.log(
        action_type="resources_checked",
        description=f"Response resources verified for '{incident_id}'. Formulated {len(final_state.get('all_recommendations', []))} response action(s).",
        incident_id=db_incident.incident_id,
        actor="System",
        details={
            "delegated_agents": final_state.get("delegated_agents", []),
            "recommendation_count": len(final_state.get("all_recommendations", [])),
            "mcp_resources": [r["resource_id"] for r in final_state.get("mcp_resources", []) if "resource_id" in r]
        },
        db=db
    )

    event_engine.publish_event(
        event_name="response_plan_updated",
        incident_id=incident_id,
        payload={
            "event_name": "response_plan_updated",
            "description": "AI response planning and resource verification completed.",
            "status": db_incident.status,
        },
        db=db,
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


@router.post("/{incident_id}/confirm-response", response_model=IncidentRead)
def confirm_response(
    incident_id: str,
    payload: IncidentConfirmResponseRequest,
    db: Session = Depends(get_db)
):
    """
    Operator Action: Confirm that the response team has arrived on-scene and is actively handling the situation.
    Transitions status to 'monitoring'.
    """
    db_incident = db.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
    if not db_incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID '{incident_id}' not found."
        )

    now = datetime.now(timezone.utc)
    db_incident.status = IncidentStatus.MONITORING.value
    db_incident.current_step = "Response team confirmed on-scene. Active situation containment underway."
    db_incident.next_action = "Monitor on-scene responders until emergency is confirmed under control."
    db_incident.updated_at = now

    db.commit()
    db.refresh(db_incident)

    audit_service.log(
        action_type="response_confirmed",
        description=f"Response arrival confirmed at {db_incident.location} by {payload.confirmed_by}. {payload.notes or ''}".strip(),
        incident_id=db_incident.incident_id,
        actor=payload.confirmed_by or "Authorized Operator",
        details={"notes": payload.notes},
        db=db
    )

    return db_incident


@router.post("/{incident_id}/close", response_model=IncidentRead)
def close_incident(
    incident_id: str,
    payload: IncidentCloseRequest,
    db: Session = Depends(get_db)
):
    """
    Administrative Finalization: Officially close a resolved emergency incident and archive the record.
    """
    db_incident = db.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
    if not db_incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID '{incident_id}' not found."
        )

    now = datetime.now(timezone.utc)
    db_incident.status = IncidentStatus.CLOSED.value
    db_incident.closed_at = now
    db_incident.current_step = "Incident closed and administratively archived."
    db_incident.next_action = "None. Incident lifecycle successfully completed."
    db_incident.resolution_note = f"{db_incident.resolution_note or ''} [CLOSED by {payload.closed_by}: {payload.closing_notes}]".strip()
    db_incident.updated_at = now

    db.commit()
    db.refresh(db_incident)

    audit_service.log(
        action_type="incident_closed",
        description=f"Incident '{incident_id}' closed by {payload.closed_by}. {payload.closing_notes or ''}".strip(),
        incident_id=db_incident.incident_id,
        actor=payload.closed_by or "Authorized Operator",
        details={"closing_notes": payload.closing_notes, "closed_at": now.isoformat()},
        db=db
    )

    return db_incident





