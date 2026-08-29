import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.database.models import IncidentDB
from backend.services.response_service import response_service
from backend.models.response import ResponsePlanRead, ApprovalDecisionPayload
from backend.api.responses import serialize_plan_model
from backend.api.deps import get_approval_viewer, resolve_department_scope
from backend.services.departments import departments_for_incident
from backend.services.auth_service import Principal, ROLE_DEPARTMENT_HEAD

router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals"])


@router.get("/pending", response_model=List[ResponsePlanRead])
def get_pending_approvals(db: Session = Depends(get_db), principal: Principal = Depends(get_approval_viewer)):
    """
    Retrieve all response plans currently awaiting human commander approval.
    """
    if principal.is_department and principal.role != ROLE_DEPARTMENT_HEAD:
        raise HTTPException(status_code=403, detail="Only an authorized department head may access approval work.")
    plans = response_service.list_plans(status_filter="pending", db=db)
    if not principal.is_privileged and principal.is_department:
        department = resolve_department_scope(principal, None)
        scoped = []
        for plan in plans:
            incident = db.query(IncidentDB).filter(IncidentDB.incident_id == plan.incident_id).first()
            if incident is None:
                continue
            try:
                departments = json.loads(incident.required_departments or "[]")
            except (TypeError, ValueError):
                departments = []
            if department in {str(item).upper() for item in departments}:
                scoped.append(plan)
        plans = scoped
    return [serialize_plan_model(p) for p in plans]


@router.post("/{plan_id}/decide", response_model=ResponsePlanRead)
def decide_approval(
    plan_id: str,
    payload: ApprovalDecisionPayload,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_approval_viewer),
):
    """
    Step 6 Human-in-the-Loop Approval Decision:
    Allows authorized operator/commander to Approve or Reject high-impact response plans.
    Maintains complete audit logging of who approved the plan and why.

    RBAC: requires an operator/admin principal (enforced server-side). The
    approver recorded in the audit trail is the authenticated identity, not a
    client-supplied name.
    """
    plan = response_service.get_plan(plan_id=plan_id, db=db)
    if principal.is_department:
        if principal.role != ROLE_DEPARTMENT_HEAD:
            raise HTTPException(status_code=403, detail="Only an authorized department head may approve a response plan.")
        incident = db.query(IncidentDB).filter(IncidentDB.incident_id == plan.incident_id).first()
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident for response plan not found.")
        department = resolve_department_scope(principal, None)
        try:
            routed = json.loads(incident.required_departments or "[]")
        except (TypeError, ValueError):
            routed = []
        if not routed:
            routed = departments_for_incident(incident.incident_type, incident.severity)
        if department not in {str(item).upper() for item in routed}:
            raise HTTPException(status_code=403, detail="This response plan is not routed to your department.")
    operator_name = principal.full_name or principal.username or payload.operator_name
    plan_db = response_service.decide_approval(
        plan_id=plan_id,
        decision=payload.decision,
        operator_name=operator_name,
        notes=payload.notes,
        db=db
    )
    return serialize_plan_model(plan_db)
