# CampusFlow AI — PHASE 0 AUDIT (read-only inspection)

**Scope:** Full architecture audit ahead of the 29-phase "real-time 3D AI command
center" master plan. **No code was modified.** Findings below are grounded in the
actual source (file paths cited). Where a claim is load-bearing it was verified by
direct grep/read, not inference.

> **Environment caveat (important for Phase 1):** I could not execute anything in
> this session — the Linux sandbox is out of disk, and the backend/frontend
> toolchains live in your Windows venv/Node. So the "51 backend / 38 frontend /
> build OK" baseline you cited is **taken as reported** and must be re-established
> by you in Phase 1. This audit is static only.

---

## CURRENT ARCHITECTURE

### Backend
FastAPI app in `backend/main.py` (lifespan creates tables, runs an idempotent
migration, seeds). LangGraph multi-agent pipeline under `backend/graph/` +
`backend/agents/`. Business logic in `backend/services/`; REST routers in
`backend/api/`; SQLAlchemy models in `backend/database/models.py` (plus Pydantic
schemas in `backend/models/`). MCP read-only resource lookup in `backend/mcp/`.
Single event bus (`services/event_engine.py`) feeding one WebSocket.

### Database
SQLite via SQLAlchemy (`backend/database/database.py`). All ORM tables are declared
in `backend/database/models.py` — **15 models defined, but only 6 are actually
read/written**:

- **Wired (live):** `incidents` (`IncidentDB`), `campus_resources`
  (`CampusResourceDB`), `response_plans` (`ResponsePlanDB`), `audit_logs`
  (`AuditLogDB`), `users` (`UserDB`), `department_users` (`DepartmentUserDB`).
- **Defined but DEAD (never read/written anywhere):** `incident_status_history`,
  `agent_runs` (`AgentRunDB`), `agent_events` (`AgentEventDB`),
  `department_responses`, `resource_assignments`, `routes`, `route_replans`,
  `notifications`, `chat_messages`.
- **No dedicated `approvals` table** — approval state lives as columns on
  `response_plans` (`approval_status`, `approved_by`, `approval_notes`).
- **No `dispatches` table and no telemetry table** — dispatch state is just
  `campus_resources.availability_status`; GPS is written to
  `campus_resources.latitude/longitude` (`backend/models/telemetry.py` is
  request/response Pydantic only).

Init + seed happen in `main.py` lifespan: `Base.metadata.create_all` →
`ensure_schema()` (`database/migrate.py`, additive `ALTER TABLE ADD COLUMN`,
idempotent) → `seed_resources()` + `seed_users()` (`database/seed.py`). **Seeding is
idempotent** — resources seed only when the table is empty; each user insert is
guarded by an existence check, so startup never duplicates rows.

### Authentication
`backend/services/auth_service.py`: HMAC-SHA256 signed tokens (`decode_token`
verifies signature with `hmac.compare_digest` + `exp`), unsalted SHA-256 password
hashing (legacy, acknowledged in comments). Auth endpoints in `backend/api/auth.py`:
operator login, citizen email+phone login/register, department email+password+dept
login, admin `/department/register`, `/me`. Tokens are genuinely validated on every
request (not dead code).

### RBAC
Enforcement in `backend/api/deps.py`: `get_optional_principal` (never raises),
`get_current_principal` (401 if absent), `get_command_principal` (privileged-only;
non-privileged token → 403). Principal is re-loaded from the DB each request and
rejected if the account is missing/inactive. **Gap:** `ALLOW_ANONYMOUS_ADMIN`
defaults **True** (`backend/config.py`), so `get_command_principal` synthesizes a
privileged "Campus Operator" for unauthenticated callers — meaning every command
endpoint is effectively open by default. The `require_roles` / `require_privileged`
/ `require_department_member` factories in `deps.py` are **defined but never wired**
to any route.

### Agents
Seven real agents (`backend/agents/`): `supervisor` (classify + severity +
recommended_agents), `security`, `medical`, `transport`, `communication`, `fire`,
`facilities`, plus a `synthesizer_node`. All are **real** (LLM-or-heuristic +, for
most, MCP resource lookup) and **synchronous**. LLM layer
(`services/llm_service.py`) uses Gemini/OpenAI if a key is set, else a deterministic
heuristic fallback. **Quirk (demo-critical):** each specialized agent returns early
on the LLM path *before* its MCP lookup, so **MCP resource grounding runs only in
the no-key heuristic path** — with a real key set, agents allocate 0 physical
resources.

### Incident workflow
Synchronous manual REST chain (`backend/api/incidents.py`, `responses.py`,
`approvals.py`, `dispatch.py`):
`POST /incidents` (create) → `/incidents/{id}/analyze` → `/incidents/{id}/orchestrate`
(runs the whole LangGraph graph) → `POST /response-plans/generate/{id}` →
`POST /approvals/{plan_id}/decide` (approve/reject) →
`POST /dispatch/{plan_id}/execute` → `/incidents/{id}/confirm-response` →
`/incidents/{id}/resolve` → `/incidents/{id}/close`. Command steps use
`get_command_principal`; create/list/get use `get_optional_principal` (row-scoped).

### Response planning
`services/response_service.py::generate_plan` runs the graph, consolidates
`all_recommendations` + `mcp_resources` (resource IDs), stores a `ResponsePlanDB`
row (title, severity, location, `recommended_actions` JSON, `allocated_resources`
JSON, `requires_approval`, `approval_status`). Rule: medium/high/critical always
require approval. `required_approvals` are computed inline in
`backend/graph/nodes.py` (synthesizer), not by `policy_engine` (which is unused).

### Approval
`backend/api/approvals.py::decide_approval` — **approver identity is
server-authoritative**: `operator_name = principal.full_name or principal.username
or payload.operator_name` (body value is last-resort fallback only). Stored to
`response_plans.approved_by`; emits `approval_granted` / `approval_rejected`. (This
already satisfies the master plan's Phase 17/23 "authenticated approver" rule.)

### Dispatch
`backend/api/dispatch.py` → `services/dispatch_service.py::execute_plan`. Gated on
`approval_status == "approved"`. Uses **real** `campus_resources`, flips them to
`busy`, spawns a background asyncio task that moves vehicles along a real Dijkstra
path (`services/road_network.py`) emitting live `vehicle_location_updated`; writes
an audit row; emits `dispatch_started` / `resource_dispatched` etc. Resolve releases
resources back to `available`. External SMS/push/email/CAD adapters are optional
no-ops unless configured.

### WebSocket
**One** endpoint: `@router.websocket("/ws")` → `/api/v1/events/ws`
(`backend/api/events.py`). Frontend attaches `?token=`. A legacy unfiltered
`manager.broadcast()` exists but is not wired to the engine (effectively dead).

### Events
**Single** in-memory pub/sub (`services/event_engine.py`, one singleton). Services
call `publish_event(name, incident_id, payload, db)`; `events.py` subscribes a fixed
`EVENTS_TO_BROADCAST` list and delivers over the socket **scoped by
role/department** via `services/event_visibility.py` (privileged = all; department =
only incidents routed to them; citizen = only `USER_SAFE_EVENTS` for incidents they
own). Emitted names include `incident_created`, `incident_updated`,
`response_plan_updated`, `response_plan_generated`, `approval_granted`,
`approval_rejected`, `dispatch_started`, `resource_dispatched`, `incident_resolved`,
`vehicle_location_updated`, `trace_updated`, and route events.

### Frontend
React 18 + TS + Vite 7 + React Router v6 SPA. State via React Context
(`src/auth/AuthContext.tsx`) + local `useState` — no Redux. API client
`src/services/api.ts` (base `VITE_API_BASE_URL` || `http://127.0.0.1:8000`, sends
both `Authorization: Bearer` and `X-Auth-Token`, global 401 → session teardown).
Real WebSocket in `App.tsx` (backoff reconnect). Leaflet 2D map. Voice alerts via
Web Speech API. **No React error boundary anywhere.**

### Student portal
`src/pages/CitizenPortal.tsx` (route `/portal`): report button (reuses
`ReportEmergencyModal`), own-incidents list (backend-scoped), a 5-phase
agent-free progress timeline (`src/portal/incidentProgress.ts`); Notifications +
"Safety Assistant" are labeled disabled previews.

### Operator portal
`src/App.tsx` (route `/command`) — the full command center: `Header`, `Sidebar`
(overview/incidents/resources/responses/activity), `IncidentCommandView`
(assess→plan→approve→dispatch→resolve→close), `CampusMap`, `RealOperationsControls`,
`AIDecisionTrace`, `ExplainabilityCard`.

### Admin portal
**Does not exist as a distinct UI.** `src/auth/roles.ts::homePathFor` routes both
`admin` and `operator` (via `isPrivileged`) to `/command` — admin renders the exact
same operator console. No admin-only components, tabs, or routes.

### Existing tests
- Backend legacy suite `tests/`: `test_health`, `test_incidents`,
  `test_multi_agent_graph`, `test_supervisor_agent`, `test_mcp_tools`,
  `test_map_and_spatial`, `test_dispatch_and_resolution`, `test_autonomous_operations`,
  `test_auth`, `test_response_and_approval`, `test_sms_verification`.
- Backend RBAC suite `backend/tests/`: `test_auth_rbac`, `test_incident_scoping`
  (+ `conftest.py` sets `ALLOW_ANONYMOUS_ADMIN=false` and a temp DB;
  `verify_real_operations.py` is a script). **Run the two suites SEPARATELY.**
- Frontend `frontend/src/` (vitest, DOM-free — no jsdom/testing-library):
  `auth/roles.test.ts`, `services/voiceAlertController.test.ts`,
  `portal/incidentProgress.test.ts`. `npm run build` = `tsc && vite build` (strict
  typecheck gates the build).

### Missing functionality (vs the 3D master plan)
1. **Agent lifecycle events — ABSENT.** `agent_queued/started/progress/completed/
   failed` are **never emitted**. They appear only in `events.py` EVENTS_TO_BROADCAST,
   a comment, and tests. Grep `publish_event(` in `backend/agents/` and
   `backend/graph/` = **zero**. `nodes.py` nodes only append strings to
   `audit_trail`. The graph runs silently and only `response_plan_updated` fires at
   the end of `/orchestrate`.
2. **Agent execution records — ABSENT.** `agent_runs` / `agent_events` tables exist
   but are never populated (no `duration` / `structured_output` columns).
3. **`approval_required` event — ABSENT.** Only `approval_requested` (audit action)
   + `approval_granted/rejected` exist; there is no explicit "pause + await approval"
   event.
4. **All 3D — ABSENT.** No three.js / react-three-fiber / WebGL / `.glb` / `public/`
   assets. Current agent viz is 2D (`AIDecisionTrace`, `ExplainabilityCard`, and the
   orphaned `AgentsPage`).
5. **No dedicated admin dashboard.**
6. **No React error boundary** (blank-page risk).
7. **Per-agent structured output** is returned in the `/orchestrate` response but
   not persisted, so a portal can't reconstruct a past run's per-agent detail.

### Potential risks
- **`ALLOW_ANONYMOUS_ADMIN=True` default** → command endpoints open unless set
  False; flipping it breaks the legacy no-login demo (user decision).
- **LLM/MCP early-return** → with a real API key, 0 resources allocated; demo relies
  on keyless heuristic mode (or a fix).
- **WS URL inconsistency** → `CampusMap.tsx` / `IncidentCommandView.tsx` hardcode
  `:8000` from `window.location` while `App.tsx` uses `VITE_API_BASE_URL`; diverges
  off-`:8000`.
- **No error boundary** → any render throw = white screen after login.
- **Synchronous `/orchestrate`** → the whole 7-agent graph runs in one request; to
  show agents lighting up one-by-one, events must be emitted *during* the run.
- **Unused services** (`duplicate_service` imported-not-called, `policy_engine`,
  RBAC `require_*` factories) — cosmetic dead code, low risk.
- **Cannot self-verify tests here** (sandbox) — baseline is your responsibility in
  Phase 1.

### Recommended implementation order
The 3D visual work (master Phases 9–14) is **blocked** on real events, so the
critical path is:

1. **Phase 6 first (foundation):** emit real agent lifecycle events from the graph.
   Smallest safe change = instrument each node in `backend/graph/nodes.py` to call
   `event_engine.publish_event("agent_started"/"agent_completed"/"agent_failed", ...)`
   around the agent call, and add `agent_queued` when the graph is entered. Add an
   explicit `approval_required` emit in `response_service.generate_plan`. Events will
   stream over the existing scoped WS while the synchronous `/orchestrate` request is
   in flight — no second event system, no async rewrite required.
2. **Phase 7:** persist `AgentRunDB` / `AgentEventDB` (add `duration` /
   `structured_output` columns) as each node runs, so runs are reconstructable.
3. **Phase 8:** reuse the existing WS on the frontend; add subscriptions for the new
   `agent_*` events; **fix the WS URL** to use `VITE_API_BASE_URL` everywhere.
4. **Phases 9–14:** build the 3D command center as a lazy-loaded module driven purely
   by those events; map `agent_started→WORKING`, `agent_completed→COMPLETED`,
   `agent_failed→FAILED`, `approval_required→WAITING_APPROVAL`.
5. **Cross-cutting early wins:** add a React error boundary (kills the blank-page
   risk) and decide the `ALLOW_ANONYMOUS_ADMIN` posture + the LLM/MCP grounding fix,
   since both affect whether the end-to-end demo shows real data.

### Suggested exact files for future phases (no changes made yet)
- Events/records: `backend/graph/nodes.py`, `backend/graph/workflow.py`,
  `backend/services/event_engine.py`, `backend/api/events.py`,
  `backend/services/event_visibility.py`, `backend/database/models.py`
  (`AgentRunDB`/`AgentEventDB`), `backend/api/incidents.py` (`/orchestrate`),
  `backend/services/response_service.py` (`approval_required`).
- Frontend realtime + 3D: `frontend/src/services/api.ts` (WS URL),
  `frontend/src/App.tsx`, `frontend/src/components/CampusMap.tsx`,
  `frontend/src/components/IncidentCommandView.tsx`, `frontend/src/main.tsx` (error
  boundary), plus new lazy-loaded `AgentWorld`/`AgentNode` components and
  `frontend/package.json` (add a 3D lib).
- Admin: new admin dashboard page + a route in `frontend/src/AppRoutes.tsx`.

---

**Phase 0 status: COMPLETE. No files were modified. Awaiting your authorization to
begin Phase 1 (baseline test run).**
