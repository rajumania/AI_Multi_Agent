# PHASE 2 REPORT — Frontend: Real-Time Agent Workflow State (WebSocket-driven)

**Part of:** CampusFlow AI — Real-Time 3D Command Center master plan
**Date:** 2026-08-23
**Rule compliance:** Additive only. Reuses the EXISTING events WebSocket (no duplicate WS infrastructure). No timers, no synthetic progress — state is derived purely from real backend events. Backend remains the source of truth; this layer only *reflects* it. Operator dashboard, auth, routing, and all existing frontend code are untouched.

---

## PHASE
Phase 2 — a normalized, per-incident **agent workflow state model** on the frontend, driven entirely by the real events the backend emits (Phase 1). This is the data layer the 3D command center (Phase 3+) will render.

## STATUS
Implementation COMPLETE. Test execution PENDING on the Windows venv (this environment cannot run `npm`/`vitest`/`tsc`).

## Implemented
A new, self-contained `src/realtime/` module — nothing else in the app changed:

- **`workflowReducer.ts` (PURE, DOM-free).** The heart of Phase 2. `reduceRealtime(state, event)` folds one real `LiveEvent` into a normalized state:
  - Per incident, the eight real pipeline agents (supervisor → security → medical → transport → communication → fire → facilities → synthesizer), each with `status` (`idle`/`working`/`completed`/`failed`), `message`, structured `output`, `error`, and real `startedAt`/`completedAt` timestamps taken from the events.
  - Approval state (`required`, `pending`/`approved`/`rejected`, `planId`, `approvedBy`) and dispatch state (`dispatched`, `resources`, `location`) — all set only by real `approval_required` / `approval_approved` (+ legacy `approval_granted`) / `approval_rejected` / `response_dispatched` (+ existing `dispatch_started`) events.
  - `derivePhase()` computes a single human-facing workflow phase (`idle → analyzing → coordinating → synthesizing → planned → awaiting_approval → approved → rejected → dispatched → resolved`, plus `attention` on failure) from accumulated signals, so it is correct regardless of event arrival order.
  - `workflowProgress()` returns a truthful completion fraction (nodes the backend actually finished ÷ total) — a real progress signal, never time-based.
  - Order-tolerant and idempotent (a `completed`/`failed` event stands alone; re-delivery is harmless); future-proof (an unknown agent key is tracked and labeled from the event, never dropped); bounded (`MAX_TRACKED_INCIDENTS = 25`, least-recently-active pruned) so a long demo can't grow without limit. Irrelevant channels (map/telemetry/notifications) and `system`/`live_telemetry` ids are ignored, returning the same state object (so consumers don't re-render).
- **`RealtimeWorkflowProvider.tsx`.** A React context provider that owns **one** WebSocket to the EXISTING endpoint via the shared `buildEventsWsUrl()` helper (token-scoped like every other connection), folds each frame through the pure reducer with `useReducer`, and exposes `{ state, wsState, activeWorkflow, getWorkflow, lastEvent }` through a `useRealtimeWorkflow()` hook. Same proven reconnect/backoff pattern as the operator dashboard. It is read-only: all mutations still go through the existing REST APIs.

## Files changed
- `frontend/src/realtime/workflowReducer.ts` — **NEW** (pure state model + selectors).
- `frontend/src/realtime/RealtimeWorkflowProvider.tsx` — **NEW** (single-connection provider + `useRealtimeWorkflow` hook).
- `frontend/src/realtime/workflowReducer.test.ts` — **NEW** (Vitest, DOM-free): ~20 cases covering agent lifecycle, structured-output capture, order-tolerance, failure/attention, unknown-agent tracking, full 8-agent pipeline, progress fractions, approval/dispatch/lifecycle transitions, phase precedence, an end-to-end phase sequence, idempotency, pruning cap, and safe coercion of malformed payloads.

No existing files were modified.

## Existing functionality preserved
**YES.** Purely additive new files. The operator dashboard keeps its own inline socket and behaves exactly as before; auth, routing, portals, and the 38 existing frontend tests are untouched. The new provider is not mounted yet (wired in Phase 5), so there is no second live connection in the current app.

## Backend tests
N/A this phase (frontend-only). Phase 1's backend suites are unaffected.

## Frontend tests
TO BE RUN BY USER (this environment cannot execute npm/vitest):

```
cd frontend
npm run test        # vitest: expect the existing suites + the new realtime suite green
npm run build       # tsc && vite build: expect a clean type-check + production build
```

Baseline to preserve: the 38 existing tests still pass and the production build still succeeds; target is baseline + the new `workflowReducer` suite.

## Build
No dependencies added (Rule 23 honored) — uses only React (already present) and the existing `buildEventsWsUrl` helper. New files are written to compile under the repo's strict `tsc` (`strict`, `noUnusedLocals/Parameters`, `noFallthroughCasesInSwitch`).

## Known issues / notes
- The provider is intentionally **not mounted** in Phase 2 to avoid a second WebSocket alongside the operator dashboard's existing one. Phase 5 mounts it around the command-center view (which is not rendered at the same time as the legacy dashboard) or refactors the dashboard to consume it — either way, one connection.
- `agent_progress` is handled as a working-state signal but the backend deliberately doesn't emit it (atomic nodes) — the branch stays dormant, consistent with the no-fake-progress rule.
- This model consumes operator/admin-visible events (agent_*, approval_*). Citizens don't receive those by RBAC, so Phase 4 will add a separate user-safe progress projection rather than reusing this model directly.

## Next phase
Phase 3 — the lazy-loaded 3D agent system (Three.js, code-split so login/signup stay lightweight) that renders this state model, with a non-3D fallback.
