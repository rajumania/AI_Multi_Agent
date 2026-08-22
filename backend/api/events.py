import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
from backend.services.event_engine import event_engine

router = APIRouter(prefix="/api/v1/events", tags=["Real-time Events"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_loops: Dict[WebSocket, asyncio.AbstractEventLoop] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Synchronous API handlers run in worker threads. Keep the websocket
        # loop so they can safely publish live events to connected browsers.
        self.connection_loops[websocket] = asyncio.get_running_loop()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.connection_loops.pop(websocket, None)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Wait for any incoming messages or just keep the socket open
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

def broadcast_engine_event(incident_id: str, payload: Dict[str, Any], db=None):
    # Ensure event payload has incident_id and event type
    payload_copy = dict(payload)
    if "incident_id" not in payload_copy:
        payload_copy["incident_id"] = incident_id
    try:
        loops = {loop for loop in manager.connection_loops.values() if loop.is_running()}
        for loop in loops:
            asyncio.run_coroutine_threadsafe(manager.broadcast(payload_copy), loop)
    except RuntimeError:
        # Auditing and traces still work when no browser is connected.
        pass

# Subscribe to events to broadcast them to the frontend
EVENTS_TO_BROADCAST = [
    "incident_created",
    "incident_updated",
    "response_plan_updated",
    "agent_assigned",
    "workflow_started",
    "agent_started",
    "agent_completed",
    "agent_failed",
    "tool_started",
    "tool_completed",
    "tool_failed",
    "resource_verified",
    "response_plan_generated",
    "response_plan_updated",
    "approval_requested",
    "approval_granted",
    "approval_rejected",
    "dispatch_started",
    "resource_dispatched",
    "vehicle_location_updated",
    "route_selected",
    "route_blocked",
    "route_recalculated",
    "vehicle_arrived",
    "response_status_changed",
    "monitoring_started",
    "replan_started",
    "replan_completed",
    "incident_resolved",
    "incident_closed",
    "trace_updated"
    ,"provider_connected"
    ,"provider_failed"
    ,"notification_requested"
    ,"notification_accepted"
    ,"notification_delivered"
    ,"notification_failed"
    ,"demo_push_available"
    ,"call_requested"
    ,"call_ringing"
    ,"call_answered"
    ,"call_failed"
    ,"gps_connected"
    ,"gps_updated"
    ,"gps_stale"
    ,"gps_offline"
    ,"dispatch_requested"
    ,"dispatch_accepted"
    ,"dispatch_failed"
]

for event in EVENTS_TO_BROADCAST:
    event_engine.subscribe(event, broadcast_engine_event)
