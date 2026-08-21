import json
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.services.response_service import response_service
from backend.models.response import ResponsePlanRead, ApprovalStatus

router = APIRouter(prefix="/api/v1/response-plans", tags=["Response Plans"])


def serialize_plan_model(plan_db) -> Dict[str, Any]:
    return {
        "plan_id": plan_db.plan_id,
        "incident_id": plan_db.incident_id,
        "title": plan_db.title,
        "severity": plan_db.severity,
        "location": plan_db.location,
        "recommended_actions": json.loads(plan_db.recommended_actions) if isinstance(plan_db.recommended_actions, str) else plan_db.recommended_actions,
        "allocated_resources": json.loads(plan_db.allocated_resources) if isinstance(plan_db.allocated_resources, str) else plan_db.allocated_resources,
        "requires_approval": plan_db.requires_approval.lower() == "true" if isinstance(plan_db.requires_approval, str) else bool(plan_db.requires_approval),
        "approval_status": plan_db.approval_status,
        "approved_by": plan_db.approved_by,
        "approval_notes": plan_db.approval_notes,
        "created_at": plan_db.created_at,
        "updated_at": plan_db.updated_at,
    }


@router.post("/generate/{incident_id}", response_model=ResponsePlanRead, status_code=status.HTTP_201_CREATED)
def generate_response_plan(incident_id: str, db: Session = Depends(get_db)):
    """
    Step 6 Response Planner Endpoint:
    Combines Incident + Agent recommendations + MCP resource discovery into a structured Response Plan.
    Enforces Human-in-the-Loop approval requirements for critical/high impact dispatch actions.
    """
    plan_db = response_service.generate_plan(incident_id=incident_id, db=db)
    return serialize_plan_model(plan_db)


@router.get("", response_model=List[ResponsePlanRead])
def list_response_plans(
    incident_id: Optional[str] = Query(None),
    status_filter: Optional[ApprovalStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db)
):
    """
    List all generated response plans with optional incident or approval status filter.
    """
    plans = response_service.list_plans(
        incident_id=incident_id,
        status_filter=status_filter.value if status_filter else None,
        db=db
    )
    return [serialize_plan_model(p) for p in plans]


@router.get("/{plan_id}", response_model=ResponsePlanRead)
def get_response_plan(plan_id: str, db: Session = Depends(get_db)):
    """
    Retrieve specific response plan by ID.
    """
    plan_db = response_service.get_plan(plan_id=plan_id, db=db)
    return serialize_plan_model(plan_db)
