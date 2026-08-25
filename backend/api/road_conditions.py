from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import require_privileged
from backend.database.database import get_db
from backend.database.models import RoadConditionDB
from backend.models.transport import RoadConditionCreate
from backend.services.event_engine import event_engine
from backend.services.road_network import road_network
from backend.services.transport_tracking_service import recalculate_for_condition


router = APIRouter(prefix="/api/v1/road-conditions", tags=["Road Conditions"])


@router.post("")
def report_road_condition(
    payload: RoadConditionCreate,
    db: Session = Depends(get_db),
    principal=Depends(require_privileged),
):
    node_a = road_network.map_location_to_node(payload.node_a)
    node_b = road_network.map_location_to_node(payload.node_b)
    if node_a not in road_network.graph or node_b not in road_network.graph:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown campus road nodes.")
    if node_a == node_b:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Road condition requires two distinct nodes.")
    if not road_network.graph.get(node_a, {}).get(node_b):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The selected nodes are not a known campus road segment.")

    reported_by = principal.full_name or principal.username or principal.email or "Authorized operator"
    row = RoadConditionDB(
        node_a=node_a,
        node_b=node_b,
        status=payload.status,
        reason=payload.reason,
        source="authorized_operator_report",
        reported_by=reported_by,
        incident_id=payload.incident_id,
    )
    db.add(row)
    if payload.status == "blocked":
        road_network.block_edge(node_a, node_b)
    else:
        road_network.unblock_edge(node_a, node_b)
    db.commit()
    db.refresh(row)

    event_engine.publish_event(
        "road_condition_updated",
        payload.incident_id or "SYSTEM",
        {
            "event_name": "road_condition_updated",
            "event": "road_condition_updated",
            "condition_id": row.id,
            "node_a": node_a,
            "node_b": node_b,
            "status": payload.status,
            "reason": payload.reason,
            "source": row.source,
            "incident_id": payload.incident_id or "SYSTEM",
            "department": "TRANSPORT",
        },
    )
    replanned = recalculate_for_condition(db, row) if payload.status == "blocked" else 0
    return {
        "condition_id": row.id,
        "node_a": node_a,
        "node_b": node_b,
        "status": row.status,
        "source": row.source,
        "replanned_routes": replanned,
    }
