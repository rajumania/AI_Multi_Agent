# Phase 6 Report — AITAM Disaster Response AI

## Status

**PARTIAL** — the current disaster platform is connected end-to-end for the
validated community and sensor paths. Existing approval/RBAC and image-storage
limitations are documented below.

## Database configuration resolution

The authoritative runtime database remains `campusflow.db`. `backend/config.py`
and the checked-in `.env` resolve `sqlite:///./campusflow.db`; `aitam.db`
was not present. `.env.example` now uses the same filename, leaving one
documented runtime choice. No database was renamed, reset, dropped, or
recreated.

Read-only verification found 13 incidents, 28 sensor observations, 18 risk
predictions, 11 resources, and 20 response plans. Nepal N-14 data remains.

## Authentication completion

`/login` now renders the real login screen instead of redirecting to
`/command`. The choices are Community and Department. Community uses the
existing email/phone identity flow and redirects to `/portal`; it cannot
obtain command privileges. Department authentication uses the existing
department email/password/department flow and redirects to its authorized
`/dept/<DEPARTMENT>` portal. `/command` is protected by the existing
privileged-role guard.

## Community portal and report flow

The existing report modal remains the intake surface. The community portal now
also exposes nearby risk, zone-targeted alerts, the existing backend map,
rescue-request submission, travel-safety checking, report progress, and offline
status. Reports retain disaster type, severity, GPS/manual map location,
casualty state, evidence source, and reporter data.

Disaster-domain reports now persist `disaster_type`, `zone_id`,
`region_id`, and a bounded evidence reference, then enter the shared
event-fusion callback and existing disaster LangGraph. Offline replay still
uses the existing idempotency header and queue. GPS/manual selection remains
available, with backend-provided disaster zones such as Nepal N-14 available as
location presets.

The existing photo picker is connected to intake using a reference such as
`photo:route-evidence.jpg`. The current backend has no binary-object upload
endpoint, so binary media storage remains a known limitation.

## Department command and operations

The privileged command center retains the working overview, incident queue,
risk, map, response-plan, approval, activity, and 3D views. Department portals
retain server-scoped incident assignment workflows and now include live
Sensors, Alerts, Rescue Requests, Shelters & Hospitals, and Monitoring views
using the existing APIs.

The Alerts placeholder now displays backend notifications with severity,
message, incident, and timestamp. It refreshes from the existing WebSocket
event timeline and polls for reconciliation. Critical community warnings now
use a community recipient type while preserving existing audience, cooldown,
deduplication, and nearby-alert behavior.

The Rescue Requests placeholder now shows request ID, location, affected
people, injured count, hazard level, timestamp, server priority score, status,
and assignment availability. Priority remains owned by the backend priority
engine.

The Shelters & Hospitals placeholder now consumes `/shelters` and
`/hospitals`, showing name, location, capacity, emergency beds where
available, availability/safety state, and explicit missing-data labels.

## Sensors, monitoring, map, and 3D

The Sensor Dashboard consumes `/sensors`, `/sensors/status`, and
`/sensor-events`. It supports Nepal rainfall, river level, soil moisture,
and ground movement observations, detail inspection, current/previous values,
thresholds, anomaly state, source, location, and timestamps. Backend sensor
status derives NORMAL, WARNING, CRITICAL, and OFFLINE from stored readings and
age.

Monitoring combines current incidents, sensor health, risk freshness, response
plans, pending approvals, alerts, database health, and recent re-planning
events. Existing `POST /monitoring/replan/{event_id}` remains the single
re-planning path.

The existing Leaflet map and cleaned 3D visualization were preserved. Map
layers remain backend-driven for risks, vulnerability, hazards, sensors,
incidents, rescue requests, shelters, hospitals, resources, rescue teams,
safe/blocked routes, alerts, and tourist safety. The 3D catalog continues to
fold existing WebSocket workflow events through the realtime reducer; no fake
activity loop or second visualization was added.

## Event fusion and orchestration

Human community reports with disaster-domain location now enter
`trigger_disaster_intelligence`, the same service used by sensor events. Both
paths use the existing supervisor, LangGraph `Send` fan-out, specialist merge,
resource coordination, rescue priority, safe routing, response planning,
approval gate, monitoring, and recovery stages. Legacy incident-only callers
retain their compatibility path.

The existing response-plan approval UX and API-gated authorization were
preserved. High-impact plans remain pending until the authorized command
principal approves or rejects them; no automatic high-impact dispatch was
introduced.

Tourist Safety continues to use current risk predictions, hazards, alerts,
route state, and weather, returning explicit SAFE/CAUTION/NOT_RECOMMENDED/
CRITICAL guidance. No second WebSocket server was created. PWA manifest,
service worker, icons, offline queue, cached map snapshots, and reconnect
synchronization were preserved.

## Nepal scenario

The retained N-14 scenario remains intact. Read-only inspection found:

| Hazard | Score | Level | Confidence |
|---|---:|---|---:|
| Flood | 63.32 | HIGH | 100% |
| Landslide | 94.44 | CRITICAL | 100% |

These values are backend-generated and are not hardcoded in the UI.

## End-to-end validation

Validated with isolated backend tests and a read-only runtime smoke check:

- Community login returns a `user` principal and `/auth/me` confirms it.
- Department login succeeds for the retained Security account.
- Community report persists GPS, disaster type, and evidence reference.
- The automatic report callback creates an approval-pending shared response plan.
- Sensor anomaly input reaches risk, agents, resources, priority, routing, and plan output.
- Alerts, nearby community alerts, map, sensors, travel-safety, and monitoring APIs respond.
- Existing offline idempotency, approval, WebSocket, and 3D reducer tests remain active.

## Tests and build

- Backend full suite: **113 passed**.
- Frontend suite: **96 passed**.
- Root suite: **52 passed, 1 skipped, 1 known pre-existing timing failure** in
  `tests/test_supervisor_agent.py::test_api_analyze_incident_by_id`.
- Python compilation and `git diff --check`: passed.
- Frontend production build: passed; TypeScript and Vite compilation succeeded.
- Build emits a non-failing large-chunk warning for the main and 3D bundles.
- Browser-level offline automation was unavailable; offline source and backend
  idempotency tests pass.

## Remaining issues

1. Department staff remain server-scoped operational users. Existing approval
   mutation authorization is privileged admin/operator-only; changing that
   boundary requires a separate RBAC decision.
2. Photo evidence is a bounded reference, not binary media. Durable image
   retrieval requires an object-storage/upload endpoint.
3. External IoT, weather, routing tiles, SMS, and related providers remain
   configuration-dependent; unavailable providers use the existing fallback or
   unavailable states.
4. The root timing failure is the known asynchronous background-workflow race
   documented by the baseline and is unrelated to Phase 6.

## Files created in Phase 6

- `PHASE_6_REPORT.md`
- `backend/tests/test_phase6_integration.py`
- `frontend/src/components/CommunitySafetyPanel.tsx`
- `frontend/src/pages/OperationalDataPage.tsx`

## Files modified in Phase 6

- `.env.example`
- `backend/api/incidents.py`
- `backend/api/phase3.py`
- `backend/services/disaster_intelligence_service.py`
- `backend/services/llm_service.py`
- `frontend/src/App.tsx`
- `frontend/src/AppRoutes.tsx`
- `frontend/src/auth/AuthContext.tsx`
- `frontend/src/components/ReportEmergencyModal.tsx`
- `frontend/src/components/Sidebar.tsx`
- `frontend/src/index.css`
- `frontend/src/pages/CitizenPortal.tsx`
- `frontend/src/pages/DepartmentPortal.tsx`
- `frontend/src/pages/LoginPage.tsx`
- `frontend/src/services/api.ts`

## Files deleted in Phase 6

None. Existing cleanup deletions were preserved and not repeated.
