# AITAM Disaster Response AI — Clean Baseline Report

Audit and cleanup date: 2026-08-28  
Product: **AITAM Disaster Response AI**  
Product description: **Disaster Prediction & Community Response System**  
Institution: **Aditya Institute of Technology and Management**

## 1. Executive summary

The repository was inspected, the active SQLite database was backed up and cleaned of confirmed legacy campus/Vignan records, and the 3D command-center catalog was changed from the stale five-node/human-team visualization to the nodes represented by the current disaster workflow.

The current active database is **`campusflow.db`**, not `aitam.db`. The checked-in `.env` and `backend/config.py` both resolve `sqlite:///./campusflow.db`; `.env.example` mentions `aitam_disaster_response.db`. No configuration was changed during this cleanup. This filename/configuration mismatch is therefore an outstanding baseline issue and is documented rather than silently corrected.

The current backend is healthy, its database connection is healthy, the current authentication paths work for Community and Department accounts, the Nepal map/risk/alert/travel-safety APIs respond, and the authenticated WebSocket handshake succeeds. Backend and frontend tests pass at the stated baseline (111 and 96 respectively). The root legacy suite retains its known timing/behavior failure.

The cleanup did not add a new feature or a second orchestration system. No backend source, API contract, dependency, schema, or configuration was changed in this pass. The only application-code changes in this pass are the 3D visualization cleanup and its focused regression test updates; database changes are data-only deletion of confirmed legacy records.

## 2. Database before cleanup

The configured database file before cleanup was:

`C:\Users\rajub\Downloads\genai\AITAM\campusflow.db`

The requested `aitam.db` file does not exist in the repository. The database was inspected before deletion. The initial row counts were:

| Table | Before |
|---|---:|
| agent_events | 0 |
| agent_runs | 15 |
| audit_logs | 10,609 |
| campus_resources | 24 |
| chat_messages | 0 |
| communities | 1 |
| department_responses | 284 |
| department_users | 18 |
| environmental_observations | 25 |
| incident_status_history | 0 |
| incidents | 1,011 |
| notifications | 1,294 |
| regions | 2 |
| rescue_requests | 1 |
| resource_assignments | 0 |
| response_plans | 831 |
| risk_predictions | 18 |
| road_conditions | 0 |
| route_replans | 0 |
| routes | 2 |
| sensor_events | 28 |
| sensor_observations | 28 |
| transport_telemetry | 0 |
| users | 53 |
| weather_observations | 11 |
| zones | 3 |

## 3. Database backup

Backups were created before destructive cleanup and were not overwritten:

- `campusflow_pre_cleanup_20260828_202918.db` — original pre-cleanup database copy.
- `campusflow_retry_pre_cleanup_20260828_203948.db` — safety copy made before the cleanup retry after a test-process contamination was detected.

Both files are in the repository root. The second backup protects the pre-retry state; the first is the original baseline backup. No database was dropped or reset.

## 4. Legacy records identified and removed

Records were classified by relationships, identifiers, location semantics, and references rather than by blindly replacing generic words. Confirmed obsolete data included:

- old Vignan/student/campus user accounts;
- old campus department accounts;
- the old campus resource set, including the original ambulance/security/medical/shelter/vehicle/facility/fire identifiers;
- old campus/operator incident batches and their linked old response plans;
- linked old department responses, notifications, and non-current audit rows.

The cleanup removed approximately **45 legacy user rows**, **6 legacy department-user rows**, **13 confirmed old campus resource rows**, **998 confirmed old campus/operator incident rows**, **811 linked old response plans**, **284 linked department-response rows**, **1,266 linked notifications**, and **10,436 linked legacy audit rows**. Counts are approximate for the cleanup summary because a transient test row was created and removed while isolating the root test suite; the final database counts below are the authoritative state.

No tables were dropped. Shared tables such as `users`, `incidents`, `campus_resources`, `audit_logs`, and `response_plans` were preserved because the current system still uses them.

## 5. Database after cleanup

Final active counts:

| Table | After | Current interpretation |
|---|---:|---|
| agent_events | 0 | Current event table exists; no persisted rows at audit time |
| agent_runs | 15 | Current Nepal disaster-intelligence execution history |
| audit_logs | 173 | Current and retained historical audit trail |
| campus_resources | 11 | Current generic/AITAM demo resources, including Nepal resources |
| chat_messages | 0 | Current chat table, empty in this dataset |
| communities | 1 | Demo community; shared Phase 1/test compatibility data |
| department_responses | 0 | Current table, no active rows |
| department_users | 12 | Current department accounts |
| environmental_observations | 25 | Current environmental observations |
| incident_status_history | 0 | Current table, empty in this dataset |
| incidents | 13 | Current/rebranded community records and Nepal sensor incidents |
| notifications | 28 | Current notifications |
| regions | 2 | AITAM demo region plus Nepal Mountain Region |
| rescue_requests | 1 | Current rescue request |
| resource_assignments | 0 | Current table, no active assignments |
| response_plans | 20 | Current/relevant response plans |
| risk_predictions | 18 | Current deterministic risk records |
| road_conditions | 0 | Current table, empty in this dataset |
| route_replans | 0 | Current table, empty in this dataset |
| routes | 2 | Current route records |
| sensor_events | 28 | Current sensor event records |
| sensor_observations | 28 | Current sensor observations |
| transport_telemetry | 0 | Current table, empty in this dataset |
| users | 8 | Current user accounts |
| weather_observations | 12 | Current weather observations |
| zones | 3 | Two generic demo zones and Nepal N-14 |

Current preserved scenario/data includes `DEMO-NEPAL-MOUNTAIN`, `DEMO-N14`, Nepal sensor observations for rainfall, river level, soil moisture and ground movement, Nepal flood/landslide incidents, risk predictions, alerts, routes, response plans, shelters, hospitals, rescue teams and vehicles.

The generic `DEMO-REGION-01`, `DEMO-ZONE-A`, `DEMO-ZONE-B`, and `DEMO-COMMUNITY-01` records were not deleted. They are ambiguous/shared Phase 1 demo and test fixtures, not confirmed Vignan records. Deleting them could break current tests and generic domain APIs.

### Ambiguous items intentionally preserved

| Item | Reason | Dependencies | Recommended action |
|---|---|---|---|
| `campus_resources` table/name | Shared model/API and current resource data; the name is historical compatibility terminology. | Resource API, map overview, response coordination, tests. | Rename only as a separately approved migration after all consumers are mapped. |
| Generic `DEMO-*` coastal region/zone/community | Used by current domain fixtures and generic APIs; not proven legacy. | Phase 1 tests and seed compatibility. | Keep until a domain-owner decision identifies it as obsolete. |
| Historical `agent_runs` JSON containing old resource names | These are current Nepal runs whose old snapshots retain values from before cleanup. | Agent trace/history and auditability. | Archive or redact historical snapshots in a controlled data-migration task; do not mutate audit history during this cleanup. |
| Historical audit terminology such as operator/campus identifiers | Retained audit history is not an active UI or workflow. | Audit trail. | Preserve for audit integrity; filter current UI labels separately. |

## 6. Authentication data status

The user-facing login UI is Community / Department. The existing internal `operator` role remains as compatibility data for the current department/admin path; it was not blindly renamed or removed. No password hashes were exposed and no duplicate accounts were created.

Runtime checks succeeded:

- Community login: `POST /api/v1/auth/user/login` with the existing `community@aitam.local` demo account returned a token; `/api/v1/auth/me` returned the current user role/profile.
- Department login: `POST /api/v1/auth/department/login` with the existing Medical department demo account returned a token; `/api/v1/auth/me` returned the department role and department.
- Department/admin account was preserved.

Authentication architecture, password handling, token handling, authorization and protected routing were not changed in this pass.

## 7. Old 3D visualization identified and cleaned

The previous 3D frontend catalog contained a stale five-node headline model (`supervisor`, `medical`, `fire`, `transport`, `synthesizer`) plus hardcoded human response-team cards and connections. Those cards and their visualization-only data were removed from the active 3D rendering.

The current 3D implementation is in:

- `frontend/src/command3d/agentCatalog.ts`
- `frontend/src/command3d/CommandCenter3D.tsx`
- `frontend/src/command3d/CommandCenterScene.ts`
- `frontend/src/realtime/workflowReducer.ts`

The scene now renders the current disaster workflow catalog and obtains execution status from the existing realtime workflow events/reducer. It does not create another agent system and does not pretend that static layout data is live execution.

### Current 3D agents/stages

The current catalog has 21 nodes/stages corresponding to the current disaster graph:

1. Supervisor / Incident Commander
2. Disaster Analysis Agent
3. Weather Agent
4. Risk Prediction Agent
5. Geo Vulnerability Agent
6. Hydrology / Environment Agent
7. Medical Triage Agent
8. Search & Rescue Agent
9. Security / Public Safety Agent
10. Infrastructure Agent
11. Shelter Agent
12. Hospital Agent
13. Communication Agent
14. Situation State
15. Resource Coordination Agent
16. Rescue Priority Agent
17. Routing Agent
18. Response Planner Agent
19. Human Approval Gate
20. Monitoring Agent
21. Recovery Agent

`TravelSafetyAgent` exists in the backend agent registry, but it is not selected by the current disaster graph's specialist selector and is served through the travel-safety API/service. It is therefore not falsely drawn as a connected disaster-graph node.

### 3D data source and truthful status

The catalog and geometry are static presentation metadata. Agent status is derived from the existing WebSocket/realtime event stream and `workflowReducer`, not from a fake timer or a second mock workflow. Current status values include idle, running, completed, failed and approval-waiting where corresponding backend events/state exist. `situation_state` has no independent lifecycle event in the current backend graph, so it remains a truthful idle/queued architecture stage rather than a fabricated completed event.

## 8. Actual LangGraph architecture

The current disaster graph is implemented in `backend/graph/disaster_workflow.py` and uses agent implementations from `backend/agents/disaster_intelligence.py`.

```text
INPUT (community event or sensor-created event)
  ↓
SUPERVISOR / INCIDENT COMMANDER
  ↓ conditional Send fan-out
┌──────────────────────────────────────────────────────────┐
│ selected parallel specialists                            │
│ disaster_analysis, weather_analysis, risk_prediction,    │
│ geo_vulnerability, plus hazard-specific specialists      │
│ hydrology/environmental, medical_triage, search_rescue,  │
│ security/public_safety, infrastructure, shelter,         │
│ hospital, communication                                  │
└──────────────────────────────────────────────────────────┘
  ↓ each specialist result
SITUATION STATE
  ↓
RESOURCE COORDINATION
  ↓
RESCUE PRIORITY
  ↓
SAFE ROUTING
  ↓
RESPONSE PLANNER
  ↓
HUMAN APPROVAL GATE
  ↓
MONITORING
  ↓
RECOVERY
  ↓
END
```

Classification from code:

- **Parallel:** selected specialist nodes are dispatched with LangGraph `Send` after supervisor classification.
- **Sequential:** situation state, resource coordination, priority evaluation, routing, response planning, approval gate, monitoring and recovery.
- **Conditional:** supervisor selection of specialists and the hazard-specific specialist selection; approval status determines whether the plan is pending/approved/rejected.
- **Human-in-the-loop:** the approval gate records `pending` and publishes approval-required state for high-impact plans; it is not bypassed.

The repository also retains an older compatibility graph in `backend/graph/workflow.py` and its related instrumentation/incident API path. It is not the current 3D model and was not deleted because current compatibility tests and older incident operations still reference it. This is a real remaining unification/cleanup item, not an assertion that both graphs are one workflow.

## 9. Sensor architecture and Nepal evidence

The sensor boundary and deterministic demo provider are implemented in `backend/services/sensor_monitoring.py` and exposed through `backend/api/phase3.py`. The `nepal_mountain` scenario provides rainfall, river level, soil moisture and ground movement observations for `DEMO-N14`. The flow persists sensor observations/events, detects anomalies, creates disaster incidents, invokes the current intelligence workflow, writes risk/response state, and publishes realtime events.

An existing Nepal simulation run was previously exercised before this cleanup and produced sensor updates, environmental anomalies and disaster-detected events; the retained database contains seven Nepal sensor incidents and the current agent-run history. No new simulation was triggered during this cleanup audit, to avoid adding more data while establishing the baseline.

## 10. Risk architecture

The deterministic risk engine is in `backend/services/risk_engine.py`, with services/workflows/API in `backend/services/risk_service.py`, `backend/graph/risk_workflow.py`, and `backend/api/risk.py`. Runtime checks returned current N-14 risk data, early warnings and risk summaries. The verified Nepal values include a critical landslide prediction and high/critical hazard conditions based on rainfall, slope/terrain vulnerability and soil moisture. The frontend consumes backend risk results; it does not calculate a second risk score.

## 11. GIS architecture

The map UI is in `frontend/src/components/DisasterRiskMap.tsx` and supporting map components/services. Backend aggregation is in `backend/api/map.py` and `backend/services/map_overview.py`.

Authenticated runtime check for `/api/v1/map/overview?zone_id=DEMO-N14` returned current demo data with:

- 1 risk record;
- 1 hazard zone;
- 4 sensors;
- 7 incidents;
- 11 resources;
- 2 routes;
- 9 alerts;
- Nepal DEMO/SIMULATION status.

The map code supports risk/vulnerability/hazard overlays, sensor and incident markers, resource/hospital/shelter/rescue data, routes, filtering and marker detail. Browser visual inspection was not automated in this audit environment, so pixel-level map interaction is reported as API/build verified rather than manually browser-certified.

## 12. Offline/PWA architecture

The current frontend contains `OfflineStatus`, `offlineStore`, and `offlineSync` implementations. `frontend/public/manifest.webmanifest`, `sw.js`, `icon-192.svg`, and `icon-512.svg` are present. The service worker uses the current AITAM app-shell cache, and the application contains IndexedDB snapshot/queue handling with a local-storage fallback and idempotent replay support.

The frontend offline tests pass. Manifest and service-worker HTTP checks returned 200 from the production preview. A full browser offline/reconnect interaction was not run in this environment; therefore the feature is marked **implemented/tested in code, runtime interaction not fully exercised**.

## 13. WebSocket architecture

The backend WebSocket endpoint is `/api/v1/events/ws` in `backend/api/events.py`. The frontend builds its URL from `VITE_API_BASE_URL` (default `http://127.0.0.1:8000`) and converts it to `ws://127.0.0.1:8000/api/v1/events/ws`, including a token.

An authenticated WebSocket connection succeeded during this audit. Existing event publication includes sensor update, environmental anomaly, disaster detection, agent execution, risk/alert, response-plan and approval-related events. No new event was generated during this cleanup run.

## 14. API inventory

The running OpenAPI document returned 92 registered paths. Current route groups include:

| Group | Representative paths | Status |
|---|---|---|
| System | `/health`, `/api/v1/system/status` | Working |
| Authentication | `/api/v1/auth/user/login`, `/api/v1/auth/department/login`, `/api/v1/auth/me` | Working |
| Disaster domain | `/api/v1/regions`, `/zones`, `/communities`, `/disasters`, `/rescue-requests` | Registered/current |
| Incidents | `/api/v1/incidents`, `/{id}/analyze`, `/{id}/orchestrate`, response confirmation/close | Registered; old compatibility path remains |
| Weather/environment | `/api/v1/weather/current`, `/history`, `/environment` | Registered/current |
| Risk/early warning | `/api/v1/risk`, `/summary`, `/early-warnings`, `/zones` | Working |
| Sensors/intelligence | `/api/v1/sensors`, `/sensor-events`, `/sensor-simulations`, `/agent-runs`, `/monitoring/replan` | Registered/current |
| Map | `/api/v1/map/overview`, `/api/v1/map/{layer}` | Working with Nepal data |
| Resources | `/api/v1/resources`, `/search/available`, shelters/hospitals/emergency-services | Registered/current |
| Routing | `/api/v1/routes/calculate`, road conditions | Registered/current |
| Response/approval | `/api/v1/response-plans`, `/api/v1/approvals/pending`, approval decision | Working/pending plans observed |
| Alerts/notifications | `/api/v1/alerts`, `/api/v1/alerts/nearby`, notifications | Working with auth where required |
| Travel safety | `/api/v1/travel/safety-check` | Working with N-14 critical result |
| Realtime | `/api/v1/events/ws` | WebSocket handshake passed |
| Assignments/dispatch/telemetry | department assignments, dispatch, transport telemetry | Registered; no active assignment/telemetry rows in baseline |
| Chat/voice | personal assistant and voice routes | Registered; not a core Nepal flow |
| Legacy-named compatibility | `campus_locations`, `CampusResource` model/tag, old graph path | Internal compatibility; no active Vignan complaint UI/data path found |

The resource endpoint defaults to excluding demo resources unless `include_demo=true`; the map overview does include the current demo resources. This is an API semantics issue to clarify later, not a data deletion issue.

## 15. Current frontend inventory

| Page/area | Purpose | Role | Backend/API | Status |
|---|---|---|---|---|
| Login | Community/Department entry | Public | Auth endpoints | Working; exactly two current labels |
| Registration | Current account registration | Community/Department | Auth endpoints | Registered; not changed |
| Community portal | Report and community safety flow | Community | Incidents, alerts, realtime | Implemented; current source terminology |
| Department dashboard/portal | Command, assignments and response | Department | Incidents, resources, plans, assignments | Implemented/connected |
| Disaster dashboard | Current incident/risk overview | Department | Incident/risk APIs | Implemented |
| Risk panel/dashboard | Risk level, score and explanation | Both/Department | Risk APIs | Backend-connected |
| Disaster-risk map | Layers, markers, routes and details | Both/Department | Map overview/layers, realtime | API/build verified; browser interaction not fully automated |
| Sensors | Sensor status/events and simulation controls | Department | Sensor APIs | Implemented/current |
| Alerts | Emergency notifications | Both | Alerts/notifications/WebSocket | Implemented/current |
| Resources | Resource availability/coordination | Department | Resources/assignments | Implemented; demo query needs `include_demo=true` |
| Rescue/responses | Priority and response plans | Department | Rescue, response-plan, dispatch | Implemented/current |
| Travel Safety | Destination risk and recommendation | Community | Travel safety/risk/alerts | N-14 runtime check passed |
| Monitoring/re-planning | Ongoing state and replan controls | Department | Monitoring/replan APIs/events | Implemented in current backend; sparse baseline rows |
| Approval | Human approval gate | Department | Approvals pending/decide | Pending plans observed |
| Offline/PWA | Offline status, queue and sync | Community | IndexedDB/local sync/API replay | Code/tests/assets verified; full offline browser exercise pending |
| 3D command center | Current agent architecture/status view | Department | Existing realtime event reducer | Cleaned/current catalog; build and focused tests pass |

No active Vignan complaint dashboard, campus complaint submission page, or old profile/team-card route was found in the current frontend inventory.

## 16. Current user and department flows

### Community flow

Community login uses the existing user authentication path. The community portal submits a current incident/disaster report with structured details and location to the existing incident/disaster APIs. The backend persists the incident, can invoke analysis/orchestration, derives risk and response state, and publishes current alerts/realtime events. Offline reports are queued and replayed through the existing sync service when connectivity returns.

### Department flow

Department login uses the existing department authentication path. The department portal consumes incidents, risk, sensors, resources, response plans, assignments, alerts and approvals. High-impact response plans remain pending at the human approval gate until an authorized decision is made.

### Nepal sensor flow

```text
Nepal Mountain Region / N-14
  → demo sensor observations
  → anomaly detection
  → disaster incident
  → supervisor
  → selected parallel specialists
  → situation state
  → deterministic risk
  → resources / rescue priority / route
  → response plan
  → human approval
  → alerts / monitoring / recovery
```

The flow is implemented in the current sensor service, disaster workflow, risk service, resource coordination, routing, alerts and monitoring modules. Existing retained Nepal data and prior simulation evidence confirm the flow; this cleanup itself did not trigger another simulation.

### Community report trace

`frontend report control → incident/disaster API → incidents table → current analysis/orchestration path → specialist results → risk/resource/rescue/routing/response plan → approval → alerts/WebSocket → frontend`. The older incident compatibility graph remains alongside the newer disaster-intelligence graph, so this is not yet a single unified graph for every entry endpoint.

### Offline trace

`frontend report → IndexedDB queue/local-storage fallback → reconnect synchronizer → idempotent API replay → current incident persistence → normal disaster workflow`. The implementation and tests are present; an end-to-end browser disconnect/reconnect was not manually exercised during this audit.

### Tourist safety trace

`destination N-14 → travel-safety service → current risk/geographic/alert data → recommendation`. Runtime returned critical risk and `NOT_RECOMMENDED` with reasons including rainfall, slope vulnerability, rainfall intensity, soil moisture and terrain vulnerability. The `warning` field was null in this response; the recommendation and reasons were present.

## 17. Mock/demo/seed audit

- **Current demo data:** `nepal_mountain`, `DEMO-N14`, `DEMO-NEPAL-MOUNTAIN`, sensor observations, risk data, current generic response resources and current AITAM demo records were preserved.
- **Shared infrastructure:** seed/migration code still contains compatibility names and generic demo setup needed by current tests/APIs; it was not blindly removed.
- **Test fixtures:** backend/frontend/root test fixtures remain and were not deleted or weakened.
- **Legacy active seed data:** confirmed old campus/Vignan resource and incident records were removed from the active database.
- **Unknown/ambiguous:** generic coastal demo records and historical agent/audit snapshots were preserved and documented above.

## 18. Legacy cleanup status

### Active references

Repository and active-data review found no active Vignan user-facing UI, Vignan complaint route, Vignan complaint workflow, Vignan complaint agent, or active Vignan records in the current core tables.

### Historical documentation

Vignan references remain in historical migration/audit documents such as `INCREMENT_1_REPORT.md`, `INCREMENT_2_REPORT.md`, `CURRENT_PROJECT_STATE.md`, `LEGACY_CLEANUP_PLAN.md`, and `LEGACY_CLEANUP_REPORT.md`. These are historical records and were not rewritten to falsify history.

### Internal compatibility

Some internal identifiers remain intentionally: `CampusResource`/`campus_resources`, `campus_locations`, `loginOperator`, `OperatorLocation`, old incident-graph instrumentation, and compatibility comments/tests. They are not user-visible Vignan complaint functionality and are still referenced by current code/tests. They require a separately approved dependency audit before removal.

### Historical stored snapshots

The current `agent_runs` table has 15 current Nepal runs, but some serialized historical `agent_results` contain old resource names. This is persisted historical execution content, not an active UI/data source. It was intentionally not rewritten because changing trace history would reduce auditability.

## 19. Tests and build

### Backend

`python -m pytest backend/tests -q` → **111 passed**, 4 warnings, 26.25 seconds.

### Frontend

`npm.cmd test -- --run` → **10 test files, 96 tests passed**.

### Root/legacy suite

The isolated root suite was run against a temporary copy of the cleaned database so the live database was not modified. Result: **52 passed, 1 skipped, 1 failed**. The failure is the known pre-existing `tests/test_supervisor_agent.py::test_api_analyze_incident_by_id` behavior/timing assertion (`injured_count` expected `None`, observed `1`), not a cleanup-induced test deletion. Google generative-AI/Pydantic deprecation warnings and gRPC coroutine warnings were also observed.

### Production build

`npm.cmd run build` → **successful**. TypeScript compilation and Vite build completed; 1,875 modules transformed. Vite emitted only the existing large-chunk warning (`CommandCenter3D`/index bundles), not a missing-import or missing-asset error.

## 20. Runtime/local status

- Backend: **RUNNING**, `http://127.0.0.1:8000`.
- Health: **PASS**, `/health` returned `200`, service AITAM Disaster Response AI, database connected.
- OpenAPI: **PASS**, `/openapi.json` returned `200` with 92 paths.
- Frontend production preview: **RUNNING**, `http://127.0.0.1:4175/` using the existing built output and runner-compatible preview command. `/`, `/manifest.webmanifest`, and `/sw.js` returned `200`.
- Frontend default Vite dev/preview loader: **ENVIRONMENT ISSUE**. The default loader encountered a local dependency/config path error (`Cannot read directory "../../../.." Access is denied` and unresolved React/Lucide optimizer modules). No dependencies or configuration were changed; the production build and runner-compatible preview work.
- WebSocket: **PASS**, authenticated connection to `ws://127.0.0.1:8000/api/v1/events/ws?token=<runtime-token>` succeeded.
- Map: **API PASS** with current N-14 data; manual browser interaction not fully automated.
- Database: **CONNECTED**, but active filename is `campusflow.db`, not the requested `aitam.db`.

## 21. Problems and remaining implementation items

1. **Database naming/config mismatch:** `aitam.db` is absent while `.env`/`backend/config.py` use `campusflow.db`; `.env.example` uses another name. Recommended action: approve and perform a controlled configuration/data migration only after deciding the canonical filename.
2. **Two orchestration compatibility paths:** `backend/graph/disaster_workflow.py` is the current sensor/disaster-intelligence graph, while `backend/graph/workflow.py` and related instrumentation support older incident operations. Recommended action: map all consumers and unify or retire only after regression coverage; no removal was safe in this cleanup.
3. **Historical trace contamination:** old names remain in serialized `agent_runs` results and historical audit records. Recommended action: archive/redact through an auditable migration if clean historical display is required.
4. **Local Vite runner/dependency issue:** default local dev/preview startup reports access/unresolved optimizer errors, although build and runner-compatible preview succeed. Recommended action: inspect the existing local Node installation/cache and package lock without changing versions.
5. **Resource API default:** `/api/v1/resources` returns no rows without `include_demo=true`, while map overview returns current demo resources. Recommended action: clarify the existing API contract or caller query.
6. **Realtime graph visibility:** the static 3D catalog is current and statuses use real events, but `situation_state` has no dedicated event and `travel_safety` is separate from the selected disaster graph. Recommended action: only add instrumentation/connection after defining the authoritative workflow contract.
7. **Known root test failure:** `test_api_analyze_incident_by_id` still has the prior injured-count assertion failure. Recommended action: diagnose the endpoint/test timing contract; do not hide it by changing tests.
8. **Browser-level audit limits:** no automated browser session with console/network recording was available for complete visual/offline interaction certification. API, WebSocket, build and asset checks were performed instead.

## 22. Files and data changed

### Created by this cleanup/reporting task

- `CLEAN_BASELINE_REPORT.md`
- `campusflow_pre_cleanup_20260828_202918.db` (backup)
- `campusflow_retry_pre_cleanup_20260828_203948.db` (backup)

### Application files modified by this cleanup task

- `frontend/src/command3d/agentCatalog.ts`
- `frontend/src/command3d/CommandCenter3D.tsx`
- `frontend/src/command3d/CommandCenterScene.ts`
- `frontend/src/realtime/workflowReducer.ts`
- `frontend/src/command3d/agentStatus.test.ts` (focused regression coverage for the cleaned catalog)
- `campusflow.db` (data-only legacy record cleanup)

No files were deleted by this cleanup task. The repository already contained unrelated modifications and previously created cleanup/audit files before this turn; those pre-existing changes were preserved and are not attributed to this report.

## 23. Final assessment

| Area | Status |
|---|---|
| Active Vignan complaint functionality | **NO active path found** |
| Active old Vignan data | **Removed from confirmed active records** |
| Current AITAM/Nepal data | **Preserved** |
| Community authentication | **Pass** |
| Department authentication | **Pass** |
| Nepal sensor/risk evidence | **Pass from retained run and current data; no new simulation in cleanup run** |
| LangGraph disaster workflow | **Pass in backend tests and code trace** |
| Parallel agents | **Pass in backend tests and actual Send fan-out code** |
| Risk engine | **Pass** |
| Map data connection | **Pass at API level; browser interaction pending** |
| Alerts/WebSocket | **Pass at endpoint/handshake level** |
| Human approval | **Pass; pending plans observed** |
| Offline/PWA | **Implemented and tests/assets pass; full browser offline interaction pending** |
| Production build | **Pass** |

This is a clean, usable current-project baseline with the documented database filename mismatch, compatibility graph, historical data references, local Vite startup issue and known root-suite failure still outstanding. No new feature phase was started.
