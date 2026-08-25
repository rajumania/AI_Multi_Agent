"""Short-lived reuse of already-computed workflow results.

The cache only reuses results produced by the real agents in the current
process. It is a performance hint, not a source of authorization or
persistence. A cache miss always runs the normal workflow safely.
"""

import copy
import json
from threading import RLock
from typing import Any, Dict, Optional, Tuple


def _fingerprint(state: Dict[str, Any]) -> str:
    relevant = {
        key: state.get(key)
        for key in (
            "description", "location", "incident_type", "severity",
            "injured_count", "evidence_source", "reported_by",
        )
    }
    return json.dumps(relevant, sort_keys=True, default=str)


class WorkflowCache:
    def __init__(self) -> None:
        self._lock = RLock()
        self._supervisor: Dict[str, Tuple[str, Dict[str, Any]]] = {}
        self._graph: Dict[str, Tuple[str, Dict[str, Any]]] = {}

    def store_supervisor(self, incident_id: str, state: Dict[str, Any], result: Dict[str, Any]) -> None:
        with self._lock:
            self._supervisor[incident_id] = (_fingerprint(state), copy.deepcopy(result))

    def take_supervisor(self, incident_id: str, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._supervisor.get(incident_id)
            if not entry or entry[0] != _fingerprint(state):
                return None
            self._supervisor.pop(incident_id, None)
            return copy.deepcopy(entry[1])

    def store_graph(self, incident_id: str, state: Dict[str, Any], result: Dict[str, Any]) -> None:
        with self._lock:
            self._graph[incident_id] = (_fingerprint(state), copy.deepcopy(result))

    def take_graph(self, incident_id: str, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._graph.get(incident_id)
            if not entry or entry[0] != _fingerprint(state):
                return None
            self._graph.pop(incident_id, None)
            return copy.deepcopy(entry[1])


workflow_cache = WorkflowCache()
