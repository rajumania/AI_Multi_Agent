"""Lightweight timing instrumentation for the emergency workflow.

The instrumentation is deliberately log-only: it does not alter control flow,
event delivery, authorization, persistence, or agent outputs.
"""

from contextlib import contextmanager
from time import perf_counter
from typing import Iterator, Optional


def _context(incident_id: Optional[str]) -> str:
    return f" incident={incident_id}" if incident_id else ""


def perf_log(stage: str, elapsed_ms: Optional[float] = None, incident_id: Optional[str] = None) -> None:
    if elapsed_ms is None:
        print(f"[PERF] {stage}_start{_context(incident_id)}", flush=True)
    else:
        print(f"[PERF] {stage}_complete: {elapsed_ms:.1f} ms{_context(incident_id)}", flush=True)


def perf_start(stage: str, incident_id: Optional[str] = None) -> float:
    started = perf_counter()
    perf_log(stage, incident_id=incident_id)
    return started


def perf_complete(stage: str, started: float, incident_id: Optional[str] = None) -> None:
    perf_log(stage, (perf_counter() - started) * 1000, incident_id=incident_id)


@contextmanager
def perf_stage(stage: str, incident_id: Optional[str] = None) -> Iterator[None]:
    started = perf_counter()
    perf_log(stage, incident_id=incident_id)
    try:
        yield
    finally:
        perf_log(stage, (perf_counter() - started) * 1000, incident_id=incident_id)
