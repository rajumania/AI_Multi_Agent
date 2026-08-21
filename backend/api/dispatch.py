from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.services.dispatch_service import dispatch_service
from backend.models.dispatch import DispatchExecutionResult, IncidentResolutionRequest
from backend.models.incident import IncidentRead

router = APIRouter(tags=["Dispatch & Resolution"])


@router.post("/api/v1/dispatch/{plan_id}/execute", response_model=DispatchExecutionResult)
def execute_approved_dispatch(plan_id: str, db: Session = Depends(get_db)):
    """
    Step 7 Dispatch Automation Execution Endpoint:
    Dispatches real physical campus assets, changes SQLite availability status to 'busy',
    and generates multi-channel emergency broadcast notifications.
    """
    return dispatch_service.execute_plan(plan_id=plan_id, db=db)


@router.post("/api/v1/incidents/{incident_id}/resolve", response_model=IncidentRead)
def resolve_emergency_incident(
    incident_id: str,
    payload: IncidentResolutionRequest,
    db: Session = Depends(get_db)
):
    """
    Step 7 Incident Resolution Endpoint:
    Marks the incident as RESOLVED, automatically releases all locked physical resources back
    to 'available' in SQLite, and logs complete final closure in the audit trail.
    """
    db_incident = dispatch_service.resolve_incident(
        incident_id=incident_id,
        payload=payload,
        db=db
    )
    return IncidentRead.model_validate(db_incident)
