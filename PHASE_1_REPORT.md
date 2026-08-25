# PHASE 1 REPORT — Backend: Real Agent Lifecycle Events

**Part of:** CampusFlow AI — Real-Time 3D Command Center master plan
**Date:** 2026-08-23
**Rule compliance:** Additive only. No rebuild, no new project, no replaced backend/DB/auth/RBAC/agents/APIs, no second WebSocket system, no fake timers, backend remains source of truth.

---

## PHASE
Phase 1 — Emit **real** agent lifecycle events from the existing LangGraph pipeline over the existing event engine / WebSocket.

## STATUS
Implementation COMPLETE. Test execution PENDING on the Windows venv (this environment cannot execute Python — see "How to verify").

## Implemented
Real lifecycle events are now emitted around the **actual** execution of each graph node — no timers, no synthetic progress, no fabricated ordering. The backend stays the source of truth; the future 3D UI will merely react to these events.

Events now emitted (JSON contract keys: `event`, `incident_id`, `agent`, `agent_label`, `status`, `message`, and `output` on completion / `error` on failure):

- `agent_started` — just before a node runs (status `working`)
- `agent_completed` — after a node returns (status `completed`, with STRUCTURED `output` only: counts / severities / booleans — never chain-of-thought)
- `agent_failed` — if a node raises (status `failed`, `error` message); the exception still propagates so behavior is unchanged
- `approval_required` — when a generated plan needs human authorization (status `waiting_approval`)
- `approval_approved` — when an operator approves (status `approved`)
- `response_dispatched` — when dispatch executes (status `in_progress`, with `dispatched_resources` + `location`)

Mechanism: a thin wrapper (`instrument_node`) is applied **at graph-registration time** in `workflow.py`. Node bodies in `nodes.py` are untouched, node names/edges are identical, and the wrapper returns each node's result unchanged, so LangGraph state-merging and all existing behavior are preserved. Emission failures are swallowed and logged — instrumentation can never break the real workflow. All new events are published **broadcast-only** (`db=None`), so they add no audit rows and cannot disturb existing audit-log assertions.

`approval_required`, `approval_approved`, and `response_dispatched` are published from the real service methods (`response_service.generate_plan` / `decide_approval`, `dispatch_service.execute_plan`) alongside the pre-existing `approval_requested` / `approval_granted` / `dispatch_started` events, which are all preserved for current consumers and tests.

`agent_progress` is registered as a supported broadcast channel but is **deliberately not emitted**: the real nodes are atomic (they either complete or fail), so emitting mid-node "progress" would be fake. This is an honest design choice, revisited only if a node genuinely gains sub-steps.

## Files changed
- `backend/graph/instrumentation.py` — **NEW.** `instrument_node` wrapper, `AGENT_META` (labels/messages/structured-output extractors for all 8 nodes), `_summarize_result`, `_emit_agent_event` (broadcast-only, never raises).
- `backend/graph/workflow.py` — wrapped all 8 nodes with `instrument_node(...)`; topology/edges unchanged.
- `backend/api/events.py` — added `agent_progress`, `approval_required`, `approval_approved`, `response_dispatched` to `EVENTS_TO_BROADCAST` (auto-subscribed by the existing loop). `agent_started/agent_completed/agent_failed` were already registered.
- `backend/services/response_service.py` — emit `approval_required` (after plan generation, when approval is required) and `approval_approved` (on approve). Existing events preserved.
- `backend/services/dispatch_service.py` — emit `response_dispatched` (after `dispatch_started`). Existing event preserved.
- `backend/services/event_visibility.py` — added `response_dispatched` to `USER_SAFE_EVENTS` (student-safe status event, consistent with the existing dispatch events). `agent_*` and `approval_*` intentionally NOT added (they stay operator/department-only per RBAC).
- `backend/tests/test_agent_lifecycle_events.py` — **NEW** (RBAC suite): unit tests for the wrapper — started+completed with structured output, failed+reraise, no-incident-id emits nothing, `AGENT_META` covers all 8 real nodes. No DB/LLM/agents required.
- `tests/test_realtime_events.py` — **NEW** (legacy suite): integration tests — a high-severity plan run emits `agent_started`/`agent_completed` for all 8 nodes plus `approval_required`; approve emits `approval_approved` (and preserves `approval_granted`); dispatch emits `response_dispatched` (and preserves `dispatch_started`). Captures events by wrapping `event_engine.publish_event` while still calling the original.

## Existing functionality preserved
**YES.** No node bodies, edges, endpoints, DB models, auth, or RBAC changed. All new events are broadcast-only (no audit rows). Existing `approval_requested` / `approval_granted` / `dispatch_started` events and their audit rows are untouched. Student RBAC unchanged except the addition of `response_dispatched` to the user-safe set (a status event, not internal reasoning).

## Backend tests
TO BE RUN BY USER (this environment cannot execute Python). Two suites, run SEPARATELY:

- RBAC suite: `python -m pytest backend/tests -q` — expected to include the new `test_agent_lifecycle_events.py` (4 tests).
- Legacy suite: `python -m pytest tests -q` — expected to include the new `test_realtime_events.py` (3 tests).

Baseline to preserve: all previously passing backend tests must still pass. Target: baseline + 7 new tests green.

## Frontend tests
N/A this phase (backend-only). Frontend real-time state consumption is Phase 2. Frontend baseline (38 tests, production build) is untouched.

## Build
Backend has no build step. No dependencies added (Rule 23 honored). Frontend untouched.

## Known issues
- `agent_progress` is supported-but-not-emitted by design (atomic nodes; emitting fake progress would violate the "no fake progress" rule).
- Students cannot receive `agent_*` / `approval_*` events (RBAC). Phase 4 will add a **user-safe progress projection** so citizens still see honest, high-level progress derived from real backend state.
- Tests are written but not yet executed here; must be run on the Windows venv before Phase 2.

## Next phase
Phase 2 — Frontend real-time agent-state model driven purely by these WebSocket events (no timers), establishing the state layer the 3D command center (Phase 3+) will render.
