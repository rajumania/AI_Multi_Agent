from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.database.database import get_db
from backend.services.simulation_service import simulation_service
from backend.services.event_engine import event_engine

router = APIRouter(prefix="/api/v1/simulation", tags=["Digital Twin Simulation"])


class StartScenarioRequest(BaseModel):
    scenario_key: str = "ublock_fire"


class FailResourceRequest(BaseModel):
    incident_id: str
    failed_resource_id: str = "AMB-001"


class BlockRoadRequest(BaseModel):
    node_a: str
    node_b: str
    blocked: bool = True


@router.get("/scenarios")
def get_available_scenarios():
    """Returns the list of available digital twin simulation scenarios."""
    return [
        {
            "key": k,
            "title": v["title"],
            "description": v["description"],
            "location": v["location"],
            "incident_type": v["incident_type"]
        }
        for k, v in simulation_service.SCENARIOS.items()
    ]


@router.post("/start")
def start_simulation(payload: StartScenarioRequest, db: Session = Depends(get_db)):
    """Starts an autonomous digital twin emergency scenario and executes multi-agent coordination."""
    result = simulation_service.start_scenario(payload.scenario_key, db)
    return result


@router.post("/fail-resource")
def inject_resource_failure(payload: FailResourceRequest, db: Session = Depends(get_db)):
    """Injects a resource breakdown failure to trigger autonomous monitoring and re-planning."""
    result = simulation_service.inject_resource_failure(payload.incident_id, payload.failed_resource_id, db)
    return result


@router.get("/trace/{incident_id}")
def get_ai_decision_trace(incident_id: str):
    """Fetches the live chronological AI decision trace for an incident."""
    trace = event_engine.get_decision_trace(incident_id)
    return {"incident_id": incident_id, "trace": trace, "count": len(trace)}


@router.post("/block-road")
def block_road_segment(payload: BlockRoadRequest):
    """Simulates a road blockage or clearance on a campus segment."""
    from backend.services.road_network import road_network
    
    node_a = road_network.map_location_to_node(payload.node_a)
    node_b = road_network.map_location_to_node(payload.node_b)

    if payload.blocked:
        road_network.block_edge(node_a, node_b)
        event_name = "route_blocked"
        description = f"Route blockage detected between {payload.node_a} ({node_a}) and {payload.node_b} ({node_b})."
    else:
        road_network.unblock_edge(node_a, node_b)
        event_name = "route_recalculated"
        description = f"Route segment cleared between {payload.node_a} ({node_a}) and {payload.node_b} ({node_b})."

    # Publish to event engine (which will broadcast via WebSockets)
    event_engine.publish_event(
        event_name=event_name,
        incident_id="SYSTEM",
        payload={
            "event_name": event_name,
            "node_a": node_a,
            "node_b": node_b,
            "blocked": payload.blocked,
            "description": description
        }
    )
    return {"status": "success", "node_a": node_a, "node_b": node_b, "blocked": payload.blocked}
