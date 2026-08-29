import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any, Optional

from backend.services.event_engine import event_engine
from backend.services.event_visibility import (
    ConnectionScope,
    guest_scope,
    operator_scope,
    scope_from_principal,
    should_deliver,
)
from backend.services.departments import departments_for_incident, normalize_department
from backend.services.auth_service import decode_token
from backend.config import settings

router = APIRouter(prefix="/api/v1/events", tags=["Real-time Events"])


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_loops: Dict[WebSocket, asyncio.AbstractEventLoop] = {}
        # Per-connection authorization scope (drives event filtering).
        self.connection_scopes: Dict[WebSocket, ConnectionScope] = {}

    async def connect(self, websocket: WebSocket, scope: ConnectionScope):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_scopes[websocket] = scope
        # Synchronous API handlers run in worker threads. Keep the websocket
        # loop so they can safely publish live events to connected browsers.
        self.connection_loops[websocket] = asyncio.get_running_loop()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.connection_loops.pop(websocket, None)
        self.connection_scopes.pop(websocket, None)

    async def send_to(self, websocket: WebSocket, message: Dict[str, Any]):
        try:
            await websocket.send_json(message)
        except Exception:
            notification_id = message.get("notification_id")
            if notification_id:
                try:
                    from backend.services.notification_service import mark_notification_failed
                    scope = self.connection_scopes.get(websocket)
                    if scope is not None:
                        mark_notification_failed(notification_id, scope)
                except Exception:
                    pass

    async def broadcast(self, message: Dict[str, Any]):
        """Unfiltered broadcast (kept for backward compatibility)."""
        for connection in self.active_connections:
            await self.send_to(connection, message)


manager = ConnectionManager()


def _resolve_connection_scope(token: Optional[str]) -> ConnectionScope:
    """Resolve a connection's scope from its token (DB-verified).

    No/invalid token -> operator scope when ALLOW_ANONYMOUS_ADMIN is on (keeps
    the legacy operator console working), otherwise a guest scope (no events).
    """
    claims = decode_token(token) if token else None
    if claims:
        # Import here to avoid a module-load cycle (api.deps <-> api.events).
        from backend.database.database import SessionLocal
        from backend.api.deps import _principal_from_claims

        session = SessionLocal()
        try:
            principal = _principal_from_claims(claims, session)
        except Exception:
            principal = None
        finally:
            session.close()
        if principal is not None:
            return scope_from_principal(principal)

    return operator_scope() if settings.ALLOW_ANONYMOUS_ADMIN else guest_scope()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Browsers cannot set Authorization headers on a WebSocket, so the token is
    # accepted as a query parameter: ws://host/api/v1/events/ws?token=<token>
    token = websocket.query_params.get("token")
    scope = _resolve_connection_scope(token)
    await manager.connect(websocket, scope)
    try:
        while True:
            # Clients acknowledge receipt only after a notification frame has
            # reached the portal. The acknowledgement is authorization-scoped
            # and updates the durable row; it is not trusted as a department
            # identity claim.
            raw = await websocket.receive_text()
            try:
                incoming = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if incoming.get("type") != "notification_delivered":
                continue
            notification_id = incoming.get("notification_id")
            if isinstance(notification_id, bool):
                continue
            try:
                notification_id = int(notification_id)
            except (TypeError, ValueError):
                continue
            if notification_id > 0:
                from backend.services.notification_service import mark_notification_delivered
                mark_notification_delivered(notification_id, scope)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


def _resolve_incident_scope(incident_id: str, db=None) -> Dict[str, Any]:
    """Resolve which user + departments an incident's events belong to.

    Uses the persisted ``required_departments`` when present, otherwise derives
    the routing from the incident category/severity so department staff still
    receive relevant events before explicit routing is stored. Best-effort:
    any failure yields an empty scope (privileged clients still receive it).
    """
    from backend.database.database import SessionLocal
    from backend.database.models import IncidentDB

    owns_session = False
    session = db
    try:
        if session is None:
            session = SessionLocal()
            owns_session = True
        incident = session.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
        if incident is None:
            return {"user_id": None, "departments": set()}
        departments = set()
        raw = getattr(incident, "required_departments", None)
        if raw:
            try:
                departments = set(json.loads(raw))
            except Exception:
                departments = set()
        if not departments:
            departments = set(departments_for_incident(incident.incident_type, incident.severity))
        normalized = {normalize_department(d) for d in departments}
        normalized.discard(None)
        return {"user_id": getattr(incident, "user_id", None), "departments": normalized}
    except Exception:
        return {"user_id": None, "departments": set()}
    finally:
        if owns_session and session is not None:
            session.close()


def broadcast_engine_event(incident_id: str, payload: Dict[str, Any], db=None):
    # Ensure event payload has incident_id and event type
    payload_copy = dict(payload)
    if "incident_id" not in payload_copy:
        payload_copy["incident_id"] = incident_id
    event_name = payload_copy.get("event_name")

    # Resolve the incident's audience once (runs in the caller's worker thread).
    incident_scope = _resolve_incident_scope(incident_id, db)

    try:
        for connection in list(manager.active_connections):
            scope = manager.connection_scopes.get(connection)
            if not should_deliver(scope, event_name, incident_scope, payload_copy):
                continue
            loop = manager.connection_loops.get(connection)
            if loop is not None and loop.is_running():
                asyncio.run_coroutine_threadsafe(manager.send_to(connection, payload_copy), loop)
    except RuntimeError:
        # Auditing and traces still work when no browser is connected.
        pass


# Subscribe to events to broadcast them to the frontend
EVENTS_TO_BROADCAST = [
    "incident_created",
    "assessment_started",
    "incident_assessed",
    "assessment_failed",
    "incident_updated",
    "response_plan_updated",
    "agent_assigned",
    "workflow_started",
    "agent_started",
    "agent_progress",
    "agent_completed",
    "agent_failed",
    "tool_started",
    "tool_completed",
    "tool_failed",
    "resource_verified",
    "response_plan_generated",
    "response_plan_updated",
    "approval_requested",
    "approval_required",
    "awaiting_human_authorization",
    "approval_granted",
    "approval_approved",
    "approval_rejected",
    "dispatch_started",
    "response_dispatched",
    "response_execution_started",
    "response_execution_completed",
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
    ,"event_fused"
    ,"sensor_correlated"
    ,"provider_connected"
    ,"provider_failed"
    ,"notification_requested"
    ,"notification_accepted"
    ,"notification_delivered"
    ,"notification_read"
    ,"notification_failed"
    ,"notification_failed"
    ,"in_app_alert_available"
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
    ,"department_notified"
    ,"dept_assignment_accepted"
    ,"dept_assignment_declined"
    ,"dept_team_assigned"
    ,"dept_en_route"
    ,"dept_on_scene"
    ,"dept_assignment_completed"
    ,"notification_created"
    ,"department_tasks_dispatched"
    ,"transport_location_updated"
    ,"transport_route_created"
    ,"transport_route_updated"
    ,"transport_eta_updated"
    ,"transport_arrived"
    ,"road_condition_updated"
    ,"risk_updated"
    ,"early_warning_created"
    ,"weather_updated"
    ,"environment_updated"
    ,"sensor_update"
    ,"environment_anomaly"
    ,"disaster_detected"
    ,"community_alert"
    ,"rescue_request_created"
    ,"resource_updated"
    ,"travel_risk_updated"
    ,"replan_triggered"
]

for event in EVENTS_TO_BROADCAST:
    event_engine.subscribe(event, broadcast_engine_event)
