import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database.database import get_db, SessionLocal
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
from backend.services.departments import departments_for_incident, normalize_department
from backend.api.deps import get_command_principal, get_optional_principal
from backend.services.auth_service import Principal
from backend.services.performance import perf_complete, perf_start, perf_stage
from backend.services.workflow_cache import workflow_cache
from backend.services.response_service import response_service
from backend.services.llm_service import llm_service
from backend.config import settings

router = APIRouter(prefix="/api/v1/incidents", tags=["Incidents"])


def generate_incident_id() -> str:
    """Generate a readable, unique incident identifier (e.g., INC-20260821-4A8F)."""
    now = datetime.now(timezone.utc)
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"INC-{now.strftime('%Y%m%d')}-{short_uuid}"


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
def create_incident(
    incident_in: IncidentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    principal: Optional[Principal] = Depends(get_optional_principal),
):
    """
    Intake a new emergency incident report.
    Validates payload and preserves null for unknown injured_count (never defaulting to 0).

    Open to anonymous reporters (kiosk/legacy). When a citizen is authenticated,
    the incident is stamped with their ``user_id`` so the user portal can scope
    live updates to incidents they themselves reported. Category and the routed
    departments are recorded so department dashboards and the WebSocket layer can
    resolve the incident's audience.
    """
    now = datetime.now(timezone.utc)
    incident_id = generate_incident_id()
    intake_started = perf_start("intake", incident_id=incident_id)

    # Stamp ownership only for citizen (user) principals. Operators/department
    # staff filing on someone's behalf do not "own" the incident as a citizen.
    owner_user_id = None
    if principal is not None and getattr(principal, "is_user", False):
        owner_user_id = str(principal.id)

    # Record the routed departments up front so department dashboards and the
    # real-time layer can resolve who should see this incident.
    required_departments = departments_for_incident(
        incident_in.incident_type.value,
        incident_in.severity.value,
    )

    db_incident = IncidentDB(
        incident_id=incident_id,
        description=incident_in.description.strip(),
        incident_type=incident_in.incident_type.value,
        category=incident_in.incident_type.value,
        location=incident_in.location.strip(),
        severity=incident_in.severity.value,
        injured_count=incident_in.injured_count,  # Strictly None if unknown
        evidence_source=incident_in.evidence_source,
        reported_by=incident_in.reported_by,
        user_id=owner_user_id,
        latitude=incident_in.latitude,
        longitude=incident_in.longitude,
        required_departments=json.dumps(required_departments),
        status=IncidentStatus.REPORTED.value,
        ai_provider_status="PENDING",
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
            "incident_description": db_incident.description,
            "incident_type": db_incident.incident_type,
            "severity": db_incident.severity,
            "location": db_incident.location,
            "injured_count": db_incident.injured_count,
            "status": db_incident.status,
            "created_at": db_incident.created_at.isoformat(),
            "updated_at": db_incident.updated_at.isoformat(),
        },
        db=db,
    )

    perf_complete("intake", intake_started, incident_id=incident_id)
    if settings.AUTOMATIC_AI_WORKFLOW:
        background_tasks.add_task(run_automatic_incident_pipeline, incident_id)
    return db_incident


def run_automatic_incident_pipeline(incident_id: str) -> None:
    """Run the existing AI workflow after the intake response has returned.

    This is intentionally an in-process FastAPI background task: it reuses the
    existing supervisor, LangGraph, response planner, audit trail, and event
    engine. It never approves a plan or dispatches physical resources.
    """
    db = SessionLocal()
    workflow_started = perf_start("automatic_workflow", incident_id=incident_id)
    try:
        incident = db.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
        if incident is None:
            return

        incident.status = IncidentStatus.ANALYZING.value
        incident.ai_provider_status = llm_service.assessment_start_status()
        incident.current_step = "AI incident assessment is in progress."
        incident.next_action = "Supervisor Agent is assessing the report before response planning."
        incident.updated_at = datetime.now(timezone.utc)
        with perf_stage("assessment_persistence", incident_id=incident_id):
            db.commit()
            db.refresh(incident)

        event_engine.publish_event(
            event_name="assessment_started",
            incident_id=incident_id,
            payload={
                "event_name": "assessment_started",
                "status": incident.status,
                "ai_provider_status": incident.ai_provider_status,
                "description": "AI incident assessment started.",
            },
            db=db,
        )

        # Reuse the existing endpoint implementations internally so the
        # background path and the explicit legacy endpoints have one source of
        # truth for classification, orchestration, persistence, and events.
        analyze_incident_by_id(incident_id=incident_id, db=db, principal=None)
        orchestrate_incident(incident_id=incident_id, db=db, principal=None)
        response_service.generate_plan(incident_id=incident_id, db=db)
    except Exception as exc:
        db.rollback()
        failed = db.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
        if failed is not None:
            failed.status = IncidentStatus.ACTION_FAILED.value
            failed.ai_provider_status = "FAILED"
            failed.current_step = "Automatic AI assessment failed and requires operator attention."
            failed.next_action = "Review the assessment failure and retry or intervene manually."
            failed.updated_at = datetime.now(timezone.utc)
            db.commit()
            audit_service.log(
                action_type="assessment_failed",
                description=f"Automatic AI assessment failed for incident '{incident_id}'.",
                incident_id=incident_id,
                actor="System",
                details={"error": str(exc)[:500]},
                db=db,
            )
            event_engine.publish_event(
                event_name="assessment_failed",
                incident_id=incident_id,
                payload={
                    "event_name": "assessment_failed",
                    "status": failed.status,
                    "ai_provider_status": failed.ai_provider_status,
                    "description": "Automatic AI assessment failed; operator attention required.",
                },
                db=None,
            )
        print(f"[automatic-workflow] incident={incident_id} failed: {exc}", flush=True)
    finally:
        perf_complete("automatic_workflow", workflow_started, incident_id=incident_id)
        db.close()



def _incident_departments(incident: IncidentDB) -> set:
    """The set of departments an incident is routed to (canonical UPPER codes).

    Prefers the ``required_departments`` JSON stamped at intake; falls back to
    deriving from the incident category for older rows that predate that column.
    """
    depts: set = set()
    raw = getattr(incident, "required_departments", None)
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                for d in data:
                    nd = normalize_department(d)
                    if nd:
                        depts.add(nd)
        except (ValueError, TypeError):
            pass
    if not depts:
        for d in departments_for_incident(incident.incident_type, incident.severity):
            nd = normalize_department(d)
            if nd:
                depts.add(nd)
    return depts


def _principal_can_view_incident(incident: IncidentDB, principal: Optional[Principal]) -> bool:
    """Server-side visibility rule for a single incident (Increment 2).

    Never trusts the frontend — the role/department come from the verified token.
      * Anonymous (no token) -> full visibility, preserving the legacy operator
        console / kiosk behavior (compatibility mode).
      * Privileged operator/admin -> full visibility.
      * Citizen/user -> only incidents they themselves reported.
      * Department staff -> only incidents routed to their own department.
      * Any other authenticated actor -> nothing (fail closed).
    """
    if principal is None or principal.is_privileged:
        return True
    if principal.is_user:
        return incident.user_id is not None and str(incident.user_id) == str(principal.id)
    if principal.is_department:
        dept = normalize_department(principal.department)
        return dept is not None and dept in _incident_departments(incident)
    return False


@router.get("", response_model=List[IncidentRead])
def list_incidents(
    status_filter: Optional[IncidentStatus] = Query(None, alias="status"),
    severity_filter: Optional[SeverityLevel] = Query(None, alias="severity"),
    incident_type_filter: Optional[IncidentType] = Query(None, alias="type"),
    db: Session = Depends(get_db),
    principal: Optional[Principal] = Depends(get_optional_principal),
):
    """
    Retrieve reported incidents, ordered by most recent first.

    RBAC scoping (Increment 2 — server-enforced, never trusts the frontend):
      * Privileged operator/admin (and, in compatibility mode, an anonymous
        command-console caller) -> ALL incidents (unchanged behavior).
      * Citizen/user -> ONLY incidents they themselves reported.
      * Department staff -> ONLY incidents routed to their department.
    This makes the department/citizen portals' isolation real at the data layer,
    rather than merely hiding rows in the UI.
    """
    query = db.query(IncidentDB)

    if status_filter:
        query = query.filter(IncidentDB.status == status_filter.value)
    if severity_filter:
        query = query.filter(IncidentDB.severity == severity_filter.value)
    if incident_type_filter:
        query = query.filter(IncidentDB.incident_type == incident_type_filter.value)

    incidents = query.order_by(desc(IncidentDB.created_at)).all()
    return [inc for inc in incidents if _principal_can_view_incident(inc, principal)]


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    principal: Optional[Principal] = Depends(get_optional_principal),
):
    """
    Retrieve a specific incident by its ID.

    RBAC scoping (Increment 2): an out-of-scope caller (a citizen requesting an
    incident they did not report, or a department requesting one not routed to
    it) receives a 404 rather than a 403 — the record's existence is not
    disclosed. Privileged/anonymous callers are unaffected.
    """
    incident = db.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID '{incident_id}' not found."
        )
    if not _principal_can_view_incident(incident, principal):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID '{incident_id}' not found."
        )
    return incident


@router.post("/{incident_id}/analyze", response_model=IncidentAnalysisResponse)
def analyze_incident_by_id(
    incident_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_command_principal),
):
    """
    Step 3 Supervisor AI Agent:
    - Analyzes incident description using centralized LLM (Gemini / OpenAI / safety fallback)
    - Classifies category and assesses severity
    - Extracts location and strictly preserves unknown injured count as null
    - Updates SQLite record with summary, confidence, and classified status

    RBAC: operator/admin only (server-enforced). Internal agent reasoning is a
    command-center capability, not exposed to citizens or single departments.
    """
    db_incident = db.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
    if not db_incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID '{incident_id}' not found."
        )

    # Perform Supervisor AI Agent Analysis
    with perf_stage("supervisor_agent", incident_id=incident_id):
        analysis_result = supervisor_agent.analyze_incident(
            description=db_incident.description,
            reported_location=db_incident.location,
            reported_by=db_incident.reported_by,
            incident_id=incident_id,
        )
    provider_metadata = llm_service.get_last_call_metadata()
    provider_status = str(provider_metadata.get("status") or "UNKNOWN").upper()
    provider_reason = provider_metadata.get("failure_reason")
    workflow_cache.store_supervisor(
        incident_id,
        {"description": db_incident.description, "reported_by": db_incident.reported_by},
        analysis_result.model_dump(),
    )

    # Deterministic Severity & Explainability Evaluation
    with perf_stage("classification", incident_id=incident_id):
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
    # Keep category + routed departments in sync with the (re)classification so
    # department dashboards and the real-time layer scope this incident correctly.
    db_incident.category = analysis_result.incident_type.value
    db_incident.required_departments = json.dumps(
        departments_for_incident(db_incident.incident_type, db_incident.severity)
    )
    if analysis_result.location and analysis_result.location != "Campus Premises":
        db_incident.location = analysis_result.location
    if db_incident.injured_count is None:
        db_incident.injured_count = analysis_result.injured_count
    db_incident.summary = sev_eval.explanation
    db_incident.confidence = sev_eval.confidence
    db_incident.ai_provider_status = provider_status
    db_incident.status = IncidentStatus.CLASSIFIED.value
    db_incident.current_step = f"Incident classified as {db_incident.incident_type.upper()} ({db_incident.severity.upper()} severity) at {db_incident.location}."
    db_incident.next_action = "Resource availability check and response plan preparation."
    db_incident.updated_at = now

    with perf_stage("classification_persistence", incident_id=incident_id):
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
            "ai_provider": provider_metadata.get("provider"),
            "ai_provider_status": provider_status,
            "ai_provider_reason": provider_reason,
        },
        db=db
    )

    if provider_status == "FALLBACK_ACTIVE":
        audit_service.log(
            action_type="ai_provider_fallback",
            description=f"AI provider fallback used for incident '{incident_id}'.",
            incident_id=incident_id,
            actor="System",
            details={
                "provider": provider_metadata.get("provider"),
                "reason": provider_reason or "provider_unavailable",
                "fallback": "existing_heuristic_safety_model",
            },
            db=db,
        )

    with perf_stage("websocket_publish", incident_id=incident_id):
        event_engine.publish_event(
            event_name="incident_updated",
            incident_id=incident_id,
            payload={
                "event_name": "incident_updated",
                "description": f"AI classified incident as {db_incident.severity.upper()}.",
                "status": db_incident.status,
                "severity": db_incident.severity,
                "incident_type": db_incident.incident_type,
                "ai_provider_status": provider_status,
                "ai_provider_reason": provider_reason,
            },
            db=db,
        )

    event_engine.publish_event(
        event_name="incident_assessed",
        incident_id=incident_id,
        payload={
            "event_name": "incident_assessed",
            "status": db_incident.status,
            "severity": db_incident.severity,
            "incident_type": db_incident.incident_type,
            "ai_provider_status": provider_status,
            "ai_provider_reason": provider_reason,
            "description": "AI incident assessment completed.",
        },
        db=None,
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
def orchestrate_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_command_principal),
):
    """
    Step 4 LangGraph Multi-Agent Orchestration Endpoint:
    Executes LangGraph state graph across Supervisor, Security, Medical, Transport, and Communication Agents.
    Consolidates specialized recommendations and sets status to 'response_planning'.

    RBAC: operator/admin only (server-enforced). Full multi-agent reasoning is a
    command-center capability, never exposed to citizens or single departments.
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
    cached_analysis = workflow_cache.take_supervisor(
        incident_id,
        {"description": db_incident.description, "reported_by": db_incident.reported_by},
    )
    if cached_analysis:
        initial_state["supervisor_analysis"] = cached_analysis

    # Execute LangGraph Multi-Agent Workflow
    with perf_stage("orchestration", incident_id=incident_id):
        final_state = run_emergency_workflow(initial_state)
    workflow_cache.store_graph(incident_id, initial_state, final_state)

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
    db_incident.required_departments = json.dumps(
        departments_for_incident(db_incident.incident_type, db_incident.severity)
    )

    db_incident.status = IncidentStatus.RESPONSE_PLANNING.value
    db_incident.current_step = "Available response resources verified and recommended action plan prepared."
    db_incident.next_action = "Review recommended response plan and authorize emergency deployment."
    db_incident.updated_at = now

    with perf_stage("orchestration_persistence", incident_id=incident_id):
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

    with perf_stage("websocket_publish", incident_id=incident_id):
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
        fire_result=final_state.get("fire_result"),
        facilities_result=final_state.get("facilities_result"),
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
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_command_principal),
):
    """
    Operator Action: Confirm that the response team has arrived on-scene and is actively handling the situation.
    Transitions status to 'monitoring'.

    RBAC: operator/admin only (server-enforced).
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
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_command_principal),
):
    """
    Administrative Finalization: Officially close a resolved emergency incident and archive the record.

    RBAC: operator/admin only (server-enforced). The Main Admin verifies
    resolution — incidents are never auto-closed.
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

    event_engine.publish_event(
        event_name="incident_closed",
        incident_id=db_incident.incident_id,
        payload={
            "event_name": "incident_closed",
            "description": "Incident closed and administratively archived.",
            "status": db_incident.status,
            "closed_at": now.isoformat(),
        },
        db=db,
    )

    return db_incident





