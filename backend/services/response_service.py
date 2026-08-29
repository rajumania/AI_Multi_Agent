import uuid
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.database.models import DepartmentResponseDB, IncidentDB, ResponsePlanDB
from backend.models.incident import IncidentStatus
from backend.models.response import ResponsePlanRead, ApprovalStatus
from backend.graph.workflow import run_emergency_workflow
from backend.services.audit_service import audit_service
from backend.services.event_engine import event_engine
from backend.services.performance import perf_stage
from backend.services.workflow_cache import workflow_cache


def generate_plan_id() -> str:
    now = datetime.now(timezone.utc)
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"PLAN-{now.strftime('%Y%m%d')}-{short_uuid}"


class ResponseService:
    """
    Response Planner Service:
    Combines:
    - Incident Report details
    - Multi-Agent Recommendations (Security, Medical, Transport, Communication)
    - MCP Grounded Response Resources
    Generates structured, auditable response plans requiring Human-In-The-Loop approval.
    """

    def generate_plan(self, incident_id: str, db: Session) -> ResponsePlanDB:
        # 1. Fetch Incident
        incident = db.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found."
            )

        # 2. Run LangGraph Multi-Agent Workflow
        initial_state = {
            "incident_id": incident.incident_id,
            "description": incident.description,
            "location": incident.location,
            "incident_type": incident.incident_type,
            "severity": incident.severity,
            "injured_count": incident.injured_count,
            "evidence_source": incident.evidence_source,
            "reported_by": incident.reported_by,
            "summary": incident.summary or "",
            "audit_trail": []
        }
        with perf_stage("response_plan", incident_id=incident_id):
            graph_state = workflow_cache.take_graph(incident_id, initial_state)
            if graph_state is None:
                cached_analysis = workflow_cache.take_supervisor(
                    incident_id,
                    {"description": incident.description, "reported_by": incident.reported_by},
                )
                if cached_analysis:
                    initial_state["supervisor_analysis"] = cached_analysis
                graph_state = run_emergency_workflow(initial_state)

        # 3. Consolidate Recommendations and MCP Resources
        recommended_actions = graph_state.get("all_recommendations", [])
        mcp_resources = graph_state.get("mcp_resources", [])
        allocated_resource_ids = [r["resource_id"] for r in mcp_resources if "resource_id" in r]

        # Determine approval requirement
        required_approvals = graph_state.get("required_approvals", [])
        requires_approval = len(required_approvals) > 0 or incident.severity in ["high", "critical", "medium"]

        plan_id = generate_plan_id()
        title = f"Emergency Action Plan: {incident.incident_type.upper()} at {incident.location}"

        now = datetime.now(timezone.utc)
        plan_db = ResponsePlanDB(
            plan_id=plan_id,
            incident_id=incident.incident_id,
            title=title,
            severity=incident.severity,
            location=incident.location,
            recommended_actions=json.dumps(recommended_actions),
            allocated_resources=json.dumps(allocated_resource_ids),
            requires_approval="true" if requires_approval else "false",
            approval_status=ApprovalStatus.PENDING.value,
            created_at=now,
            updated_at=now
        )

        db.add(plan_db)

        # Update Incident status and operational progress
        incident.status = IncidentStatus.AWAITING_APPROVAL.value
        incident.current_step = "Recommended response plan prepared. Awaiting commander authorization."
        incident.next_action = "Authorized operator must review recommended response and authorize dispatch."
        incident.updated_at = now
        with perf_stage("response_plan_persistence", incident_id=incident_id):
            db.commit()
            db.refresh(plan_db)

        # 4. Audit Logging
        audit_service.log(
            action_type="response_plan_generated",
            description=f"Response plan prepared with {len(recommended_actions)} action(s) and {len(allocated_resource_ids)} assigned resource(s).",
            incident_id=incident.incident_id,
            plan_id=plan_id,
            actor="System",
            details={
                "actions": recommended_actions,
                "resources": allocated_resource_ids,
                "requires_approval": requires_approval
            },
            db=db
        )

        if requires_approval:
            audit_service.log(
                action_type="approval_requested",
                description=f"Commander authorization requested for emergency response at {incident.location}.",
                incident_id=incident.incident_id,
                plan_id=plan_id,
                actor="System",
                details={"required_approvals": required_approvals},
                db=db
            )

        with perf_stage("websocket_publish", incident_id=incident_id):
            event_engine.publish_event(
                event_name="response_plan_generated",
                incident_id=incident.incident_id,
                payload={
                    "event_name": "response_plan_generated",
                    "plan_id": plan_id,
                    "status": incident.status,
                    "description": f"Response plan generated with {len(allocated_resource_ids)} assigned resource(s).",
                    "allocated_resources": allocated_resource_ids,
                    "approval_status": plan_db.approval_status,
                },
                db=db,
            )

        # Real "pause for human approval" signal for the live command center.
        # Broadcast-only (db=None): the audit trail already records
        # 'approval_requested' above; this is the additive real-time event the
        # frontend uses to move the workflow into its WAITING_APPROVAL state.
        if requires_approval:
            event_engine.publish_event(
                event_name="approval_required",
                incident_id=incident.incident_id,
                payload={
                    "event_name": "approval_required",
                    "event": "approval_required",
                    "plan_id": plan_id,
                    "status": "waiting_approval",
                    "message": "Human operator approval required before dispatch.",
                    "description": f"Response plan for {incident.location} requires human authorization before dispatch.",
                    "severity": incident.severity,
                    "required_approvals": required_approvals,
                    "approval_status": plan_db.approval_status,
                },
                db=None,
            )
            event_engine.publish_event(
                event_name="awaiting_human_authorization",
                incident_id=incident.incident_id,
                payload={
                    "event_name": "awaiting_human_authorization",
                    "event": "awaiting_human_authorization",
                    "plan_id": plan_id,
                    "status": incident.status,
                    "approval_status": plan_db.approval_status,
                    "message": "Response plan is ready for explicit human authorization.",
                },
                db=None,
            )

        return plan_db

    def decide_approval(
        self,
        plan_id: str,
        decision: str,
        operator_name: str = "AITAM Response Commander",
        notes: Optional[str] = None,
        db: Session = None
    ) -> ResponsePlanDB:
        plan = db.query(ResponsePlanDB).filter(ResponsePlanDB.plan_id == plan_id).first()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Response Plan '{plan_id}' not found."
            )

        if (plan.approval_status or "pending").lower() != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This response plan has already reached a final approval state.",
            )

        decision_clean = decision.lower().strip()
        if decision_clean not in ["approve", "approved", "reject", "rejected"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Decision must be 'approve' or 'reject'."
            )

        is_approved = decision_clean in ["approve", "approved"]
        new_status = ApprovalStatus.APPROVED.value if is_approved else ApprovalStatus.REJECTED.value

        now = datetime.now(timezone.utc)
        plan.approval_status = new_status
        plan.approved_by = operator_name
        plan.approval_notes = notes or ("Approved for emergency execution." if is_approved else "Rejected by safety commander.")
        plan.updated_at = now

        # Update parent incident
        incident = db.query(IncidentDB).filter(IncidentDB.incident_id == plan.incident_id).first()
        if incident:
            incident.status = IncidentStatus.APPROVED.value if is_approved else IncidentStatus.REJECTED.value
            if is_approved:
                incident.current_step = f"Emergency response authorized by {operator_name}."
                incident.next_action = "Initiate response workflow and notify physical dispatch units."
            else:
                incident.current_step = f"Response plan rejected by {operator_name}."
                incident.next_action = "Re-assess emergency parameters or prepare alternate plan."
            incident.updated_at = now

            if is_approved:
                # Approval is the authorization boundary for department work.
                # Create idempotent, department-scoped tasks immediately so
                # each required unit receives only its own operational alert.
                from backend.services.assignment_service import create_required_assignments
                existing_assignment_count = db.query(DepartmentResponseDB).filter(DepartmentResponseDB.incident_id == incident.incident_id).count()
                required_assignments = create_required_assignments(
                    incident, db, actor=operator_name
                )
                if existing_assignment_count and not required_assignments:
                    from backend.services.assignment_service import notify_replan_approval
                    notify_replan_approval(incident, plan.plan_id, db, actor=operator_name)
                incident.next_action = "Approved department tasks are dispatched; teams must acknowledge and update status."
            else:
                required_assignments = []
        else:
            required_assignments = []

        db.commit()
        db.refresh(plan)

        # Audit Logging
        audit_service.log(
            action_type="approval_decision",
            description=f"Response plan {new_status.upper()} by {operator_name}. Note: {plan.approval_notes}",
            incident_id=plan.incident_id,
            plan_id=plan.plan_id,
            actor=operator_name,
            details={
                "decision": new_status,
                "notes": plan.approval_notes,
                "operator": operator_name
            },
            db=db
        )

        event_engine.publish_event(
            event_name="approval_granted" if is_approved else "approval_rejected",
            incident_id=plan.incident_id,
            payload={
                "event_name": "approval_granted" if is_approved else "approval_rejected",
                "plan_id": plan.plan_id,
                "description": "Response plan authorized for emergency execution." if is_approved else "Response plan rejected by commander.",
                "approval_status": new_status,
            },
            db=db,
        )

        # Additive canonical event for the live command center. The existing
        # 'approval_granted' event (with its audit row) is preserved above for
        # current consumers/tests; 'approval_approved' is broadcast-only (db=None)
        # and matches the frontend contract used by the 3D workflow. Rejections
        # already emit the canonical 'approval_rejected' above.
        if is_approved:
            event_engine.publish_event(
                event_name="department_tasks_dispatched",
                incident_id=plan.incident_id,
                payload={
                    "event_name": "department_tasks_dispatched",
                    "event": "department_tasks_dispatched",
                    "plan_id": plan.plan_id,
                    "departments": [item.department for item in required_assignments],
                    "assignment_ids": [item.id for item in required_assignments],
                    "status": "notified",
                    "message": "Approved department-scoped response tasks are available.",
                },
                db=None,
            )
            event_engine.publish_event(
                event_name="approval_approved",
                incident_id=plan.incident_id,
                payload={
                    "event_name": "approval_approved",
                    "event": "approval_approved",
                    "plan_id": plan.plan_id,
                    "status": "approved",
                    "message": f"Response plan approved by {operator_name}.",
                    "approval_status": new_status,
                    "approved_by": operator_name,
                },
                db=None,
            )

        return plan

    def get_plan(self, plan_id: str, db: Session) -> ResponsePlanDB:
        plan = db.query(ResponsePlanDB).filter(ResponsePlanDB.plan_id == plan_id).first()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Response plan '{plan_id}' not found."
            )
        return plan

    def list_plans(self, incident_id: Optional[str] = None, status_filter: Optional[str] = None, db: Session = None) -> List[ResponsePlanDB]:
        query = db.query(ResponsePlanDB)
        if incident_id:
            query = query.filter(ResponsePlanDB.incident_id == incident_id)
        if status_filter:
            query = query.filter(ResponsePlanDB.approval_status == status_filter.lower().strip())
        return query.order_by(ResponsePlanDB.created_at.desc()).all()


response_service = ResponseService()
