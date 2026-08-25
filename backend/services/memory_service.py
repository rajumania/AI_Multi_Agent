"""Authenticated-user-scoped Mem0 integration for the personal assistant.

Mem0 is an optional hosted dependency.  This adapter intentionally has no
local semantic-memory substitute: when the package or key is unavailable,
callers receive ``available=False`` and the emergency system is unaffected.
Every operation requires the server-resolved user id and passes it to Mem0.
"""

from __future__ import annotations

import os
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import settings

# Mem0 creates its local telemetry/config directory during import.  Keep that
# runtime state inside the application directory instead of relying on a
# potentially non-writable user-profile location on Windows.  An explicit
# MEM0_DIR remains authoritative for deployments that provide one.
_APPLICATION_MEM0_DIR = Path(__file__).resolve().parents[1] / ".mem0"
os.environ.setdefault("MEM0_DIR", str(_APPLICATION_MEM0_DIR))

try:  # Optional dependency; installed in production when Mem0 is enabled.
    from mem0 import MemoryClient  # type: ignore
except ImportError:  # pragma: no cover - exercised by the deployment check
    MemoryClient = None  # type: ignore


class Mem0MemoryService:
    @staticmethod
    def _user_scope_kwargs(client: Any, method_name: str, user_id: str) -> Dict[str, Any]:
        """Use the installed Mem0 API's scoped-user shape.

        Mem0 2.x uses filters for search, while the hosted add endpoint still
        requires the user entity as ``user_id``.  The fallback keeps existing
        lightweight test doubles and older client shapes compatible.
        """
        method = getattr(client, method_name)
        try:
            parameters = inspect.signature(method).parameters
        except (TypeError, ValueError):
            parameters = {}
        if method_name == "search" and ("filters" in parameters or (
            any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values())
            and type(client).__module__.startswith("mem0.")
        )):
            return {"filters": {"user_id": user_id}}
        return {"user_id": user_id}

    def __init__(self) -> None:
        self.client = None
        self.reason = "not_configured"
        if not settings.MEM0_ENABLED:
            self.reason = "disabled"
        elif MemoryClient is None:
            self.reason = "package_not_installed"
        elif not settings.MEM0_API_KEY:
            self.reason = "api_key_not_configured"
        else:
            kwargs: Dict[str, Any] = {"api_key": settings.MEM0_API_KEY}
            if settings.MEM0_ORGANIZATION_ID:
                kwargs["organization_id"] = settings.MEM0_ORGANIZATION_ID
            try:
                self.client = MemoryClient(**kwargs)
                self.reason = "available"
            except Exception:
                # Do not expose provider details or credentials to clients.
                self.reason = "client_initialization_failed"

    @property
    def available(self) -> bool:
        return self.client is not None

    def search(self, *, user_id: str, query: str) -> List[str]:
        if not self.client:
            return []
        # user_id is mandatory and is never accepted from the request body.
        result = self.client.search(query, **self._user_scope_kwargs(self.client, "search", user_id))
        if isinstance(result, dict):
            result = result.get("results", [])
        memories: List[str] = []
        for item in result or []:
            if isinstance(item, dict) and isinstance(item.get("memory"), str):
                memories.append(item["memory"])
        return memories[:8]

    def add(self, *, user_id: str, user_message: str, assistant_message: str) -> bool:
        if not self.client:
            return False
        self.client.add(
            [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message},
            ],
            **self._user_scope_kwargs(self.client, "add", user_id),
        )
        return True


memory_service = Mem0MemoryService()
