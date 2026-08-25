from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.deps import get_current_principal
from backend.database.database import get_db
from backend.models.transport import TransportTrackingRead
from backend.services.transport_tracking_service import transport_tracking_snapshot


router = APIRouter(prefix="/api/v1/transport", tags=["Transport Tracking"])


@router.get("/assignments/{assignment_id}/tracking", response_model=TransportTrackingRead)
def get_transport_tracking(
    assignment_id: int,
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
):
    snapshot = transport_tracking_snapshot(db, assignment_id)
    if principal.is_privileged:
        return snapshot
    if not principal.is_department or str(principal.department).upper() != "TRANSPORT":
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Transport department access required.")
    if str(snapshot["department"]).upper() != "TRANSPORT":
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Transport assignment access denied.")
    return snapshot
