from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_principal
from backend.database.database import get_db
from backend.models.assignment import AssignmentDecisionPayload, AssignmentTeamPayload, DepartmentAssignmentRead
from backend.services.assignment_service import ACCEPTED, COMPLETED, DECLINED, EN_ROUTE, ON_SCENE, TEAM_ASSIGNED, list_for_department, list_for_incident, transition

router = APIRouter(prefix="/api/v1", tags=["Department Assignments"])


def _rows(rows):
    return [DepartmentAssignmentRead.model_validate(row) for row in rows]


@router.get("/incidents/{incident_id}/assignments", response_model=List[DepartmentAssignmentRead])
def get_incident_assignments(incident_id: str, db: Session = Depends(get_db), principal=Depends(get_current_principal)):
    if not (principal.is_privileged or principal.is_department):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Assignment access denied.")
    return _rows(list_for_incident(incident_id, db, principal))


@router.get("/portal/my-assignments", response_model=List[DepartmentAssignmentRead])
def get_my_assignments(db: Session = Depends(get_db), principal=Depends(get_current_principal)):
    if not (principal.is_privileged or principal.is_department):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department account required.")
    return _rows(list_for_department(db, principal))


@router.post("/incidents/{incident_id}/assignments/{department}/accept", response_model=DepartmentAssignmentRead)
def accept_assignment(incident_id: str, department: str, payload: Optional[AssignmentDecisionPayload] = None, db: Session = Depends(get_db), principal=Depends(get_current_principal)):
    return transition(incident_id, department, ACCEPTED, db, principal, message=payload.message if payload else None)


@router.post("/incidents/{incident_id}/assignments/{department}/decline", response_model=DepartmentAssignmentRead)
def decline_assignment(incident_id: str, department: str, payload: Optional[AssignmentDecisionPayload] = None, db: Session = Depends(get_db), principal=Depends(get_current_principal)):
    return transition(incident_id, department, DECLINED, db, principal, message=payload.message if payload else None)


@router.post("/incidents/{incident_id}/assignments/{department}/team-assigned", response_model=DepartmentAssignmentRead)
def assign_team(incident_id: str, department: str, payload: AssignmentTeamPayload, db: Session = Depends(get_db), principal=Depends(get_current_principal)):
    return transition(incident_id, department, TEAM_ASSIGNED, db, principal, message=payload.team_name, resource_ids=payload.resource_ids)


def _status_endpoint(target):
    def endpoint(incident_id: str, department: str, db: Session = Depends(get_db), principal=Depends(get_current_principal)):
        return transition(incident_id, department, target, db, principal)
    return endpoint


router.add_api_route("/incidents/{incident_id}/assignments/{department}/en-route", _status_endpoint(EN_ROUTE), methods=["POST"], response_model=DepartmentAssignmentRead)
router.add_api_route("/incidents/{incident_id}/assignments/{department}/on-scene", _status_endpoint(ON_SCENE), methods=["POST"], response_model=DepartmentAssignmentRead)
router.add_api_route("/incidents/{incident_id}/assignments/{department}/completed", _status_endpoint(COMPLETED), methods=["POST"], response_model=DepartmentAssignmentRead)
