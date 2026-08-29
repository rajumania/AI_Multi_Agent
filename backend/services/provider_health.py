"""Process-local health telemetry for external provider adapters.

This registry deliberately stores only operational metadata. It never stores
request URLs with query strings, credentials, response bodies, or secrets.
"""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Any


class ProviderHealthRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._providers: dict[str, dict[str, Any]] = {}

    def _entry(self, provider: str) -> dict[str, Any]:
        return self._providers.setdefault(provider, {
            "provider": provider,
            "status": "NOT_CONFIGURED",
            "last_success": None,
            "last_failure": None,
            "last_latency_ms": None,
            "freshness_seconds": None,
            "source": provider.lower(),
            "failure_count": 0,
        })

    def success(self, provider: str, *, latency_ms: float, freshness_seconds: float | None = None, source: str | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            entry = self._entry(provider)
            entry.update({
                "status": "HEALTHY",
                "last_success": now,
                "last_latency_ms": round(max(0.0, latency_ms), 2),
                "freshness_seconds": round(freshness_seconds, 2) if freshness_seconds is not None else None,
                "source": source or entry["source"],
            })

    def declare(self, provider: str, *, configured: bool, source: str | None = None) -> None:
        with self._lock:
            entry = self._entry(provider)
            if entry.get("last_success") or entry.get("last_failure"):
                return
            entry.update({"status": "READY" if configured else "NOT_CONFIGURED", "source": source or entry["source"]})

    def failure(self, provider: str, *, latency_ms: float, error_type: str, source: str | None = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            entry = self._entry(provider)
            entry.update({
                "status": "FAILED",
                "last_failure": now,
                "last_latency_ms": round(max(0.0, latency_ms), 2),
                "last_failure_type": error_type,
                "source": source or entry["source"],
                "failure_count": int(entry.get("failure_count", 0)) + 1,
            })

    def mark_fallback(self, provider: str, *, source: str) -> None:
        with self._lock:
            entry = self._entry(provider)
            entry.update({"status": "FALLBACK", "source": source})

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(value) for value in self._providers.values()]


provider_health = ProviderHealthRegistry()
