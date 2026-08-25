from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.services.response_service import response_service
from backend.models.response import ResponsePlanRead, ApprovalDecisionPayload
from backend.api.responses import serialize_plan_model
from backend.api.deps import get_command_principal
from backend.services.auth_service import Principal

router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals"])


@router.get("/pending", response_model=List[ResponsePlanRead])
def get_pending_approvals(db: Session = Depends(get_db)):
    """
    Retrieve all response plans currently awaiting human commander approval.
    """
    plans = response_service.list_plans(status_filter="pending", db=db)
    return [serialize_plan_model(p) for p in plans]


@router.post("/{plan_id}/decide", response_model=ResponsePlanRead)
def decide_approval(
    plan_id: str,
    payload: ApprovalDecisionPayload,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_command_principal),
):
    """
    Step 6 Human-in-the-Loop Approval Decision:
    Allows authorized operator/commander to Approve or Reject high-impact response plans.
    Maintains complete audit logging of who approved the plan and why.

    RBAC: requires an operator/admin principal (enforced server-side). The
    approver recorded in the audit trail is the authenticated identity, not a
    client-supplied name.
    """
    operator_name = principal.full_name or principal.username or payload.operator_name
    plan_db = response_service.decide_approval(
        plan_id=plan_id,
        decision=payload.decision,
        operator_name=operator_name,
        notes=payload.notes,
        db=db
    )
    return serialize_plan_model(plan_db)
