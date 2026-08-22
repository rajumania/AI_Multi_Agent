import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
from sqlalchemy.orm import Session
from backend.services.audit_service import audit_service


class EventEngine:
    """
    Asynchronous Event Engine & AI Decision Trace Logger.
    Manages autonomous event flows across specialized agents and maintains
    a live, searchable stream of AI thoughts, tool calls, and decisions.
    """

    def __init__(self):
        # Maps incident_id -> list of timestamped trace items
        self._decision_traces: Dict[str, List[Dict[str, Any]]] = {}
        # Registered event subscribers
        self._subscribers: Dict[str, List[Callable]] = {}

    def log_trace(
        self,
        incident_id: str,
        agent_name: str,
        action: str,
        thought: str,
        tool_call: Optional[Dict[str, Any]] = None,
        confidence: Optional[float] = None,
        why: Optional[str] = None
    ) -> Dict[str, Any]:
        """Logs a structured AI reasoning and tool-execution step into the decision trace."""
        now = datetime.now(timezone.utc)
        entry = {
            "timestamp": now.isoformat(),
            "time_display": now.strftime("%H:%M:%S"),
            "agent": agent_name,
            "action": action,
            "thought": thought,
            "tool_call": tool_call,
            "confidence": confidence,
            "why": why
        }

        if incident_id not in self._decision_traces:
            self._decision_traces[incident_id] = []

        self._decision_traces[incident_id].append(entry)
        self.publish_event("trace_updated", incident_id, {"event_name": "trace_updated", "entry": entry, "incident_id": incident_id})
        return entry

    def get_decision_trace(self, incident_id: str) -> List[Dict[str, Any]]:
        """Retrieves the complete chronological AI decision trace for an incident."""
        return self._decision_traces.get(incident_id, [])

    def publish_event(
        self,
        event_name: str,
        incident_id: str,
        payload: Dict[str, Any],
        db: Optional[Session] = None
    ) -> None:
        """Publishes an event to all subscribers and records an audit log if database session is present."""
        now = datetime.now(timezone.utc)

        # Preserve the server event time for an honest client-side live
        # timeline. This applies consistently to all existing event types.
        payload.setdefault("timestamp", now.isoformat())
        payload.setdefault("time_display", now.strftime("%H:%M:%S"))
        payload.setdefault("incident_id", incident_id)

        # Audit log integration
        if db:
            audit_service.log(
                action_type=event_name.lower(),
                description=payload.get("description", f"Event '{event_name}' published for incident '{incident_id}'."),
                incident_id=incident_id,
                actor=payload.get("actor", "System (Event Engine)"),
                details=payload,
                db=db
            )

        # Notify registered subscribers
        subscribers = self._subscribers.get(event_name, [])
        for handler in subscribers:
            try:
                handler(incident_id, payload, db)
            except Exception as e:
                print(f"[EventEngine] Error in handler for {event_name}: {e}")

    def subscribe(self, event_name: str, handler: Callable) -> None:
        """Registers a callback handler for an event name."""
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(handler)


event_engine = EventEngine()
