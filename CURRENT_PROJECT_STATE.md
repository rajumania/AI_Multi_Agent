# AITAM Disaster Response AI — Current Project State Audit

Audit type: read-only repository, runtime, API, database, and test audit.

Audit date: 2026-08-28

Repository: `C:\Users\rajub\Downloads\genai\AITAM`

No application code, tests, configuration, dependencies, or database rows
were modified during this audit. The only new file from this audit is this
report. The working tree already contained earlier migration/phase changes.

## 1. Executive Summary

The repository contains a substantial AITAM disaster-response implementation,
but the actual current state is not a uniformly complete end-to-end product.

Implemented and runtime-confirmed:

- FastAPI backend with SQLite persistence.
- Disaster regions, zones, communities, weather observations, environmental
  observations, sensors, sensor anomalies, risk predictions, resources,
  shelters, hospitals, emergency services, rescue requests, alerts, response
  plans, approvals, audit logs, and route APIs.
- Two LangGraph workflows: an older incident-response graph and a newer
  sensor/domain disaster-intelligence graph.
- Newer sensor path converges into the newer disaster-intelligence graph.
- Nepal Mountain / N-14 deterministic sensor scenario.
- Database-backed risk, resource coordination, route calculation, approval
  state, travel safety, map overview, and WebSocket events.
- React command dashboard, community portal, department portal, risk panel,
  map, resource page, response page, travel-safety page, offline queue, and PWA
  assets.

Important partial or disconnected areas:

- The router currently redirects `/`, `/login`, `/signup`, and unknown paths to
  `/command`, so the Community/Department login UI exists in source but is not
  reachable through normal routing. Authentication APIs and guards still exist.
- Rescue Requests, Shelters & Hospitals, and Alerts dashboard tabs render
  `DomainPlaceholderPage` rather than dedicated data-driven pages.
- There is no dedicated Sensors frontend page; sensor data is consumed by the
  map and backend APIs.
- The newer disaster graph reaches an approval gate but continues to
  monitoring/recovery with a pending status; the human decision is made later
  through the approval API rather than a LangGraph interrupt/resume.
- The local database still contains historical Vignan-branded persisted rows
  and old account records. They were not changed because this audit forbids
  database modification.
- External weather and physical sensor providers are adapter boundaries; the
  running local system uses deterministic demo/fallback providers.

There are no active `complaint`/`complaints` matches under `backend`,
`frontend/src`, or `tests`, and no complaint-specific API/router/agent/model
was found. Remaining legacy terms are mostly compatibility identifiers,
historical documentation, tests, database values, or internal role names.

## 2. Current Architecture

```text
React/Vite frontend
  ├─ command dashboard / community portal / department portals
  ├─ REST client -> http://127.0.0.1:8000/api/v1
  ├─ WebSocket client -> ws://127.0.0.1:8000/api/v1/events/ws
  ├─ Leaflet map + backend MapOverview
  └─ IndexedDB/localStorage offline queue and map snapshots

FastAPI backend
  ├─ auth/RBAC and compatibility anonymous-command shim
  ├─ incident intake graph (legacy emergency graph)
  ├─ disaster-domain/sensor graph (current convergence graph)
  ├─ deterministic weather/environment/risk services
  ├─ resource/rescue/routing/approval/alert/monitoring services
  ├─ SQLite database through SQLAlchemy
  └─ event engine -> filtered WebSocket clients
```

The backend lifespan creates additive schema objects, runs an additive schema
check, and invokes idempotent seed functions. The configured runtime database
is `sqlite:///./campusflow.db`, despite `.env.example` naming a future
`aitam_disaster_response.db` default. The actual running process therefore
uses the existing `campusflow.db`.

## 3. Current Repository Structure

```text
backend/
  api/          FastAPI routers for incidents, domain, risk, weather, map,
                sensors, resources, response, approval, dispatch, auth,
                departments, transport, telemetry, alerts, voice, chat
  agents/       Incident agents and connected disaster-intelligence agents
  database/     SQLAlchemy database, additive migration, seed functions
  graph/        emergency, disaster-intelligence, risk graphs and state
  mcp/          resource/facility/medical/security/shelter/transport tools
  models/       API schemas and database-domain models
  services/     intake, event, risk, weather, sensors, resources, routing,
                rescue, approval, alert, monitoring, auth, offline-adjacent
frontend/
  src/pages/    command, community, department, risk, map, travel, resources,
                responses, activity, login and placeholder pages
  src/components/ map, report modal, risk, offline, notification, voice,
                  command, transport, resource and assistant components
  src/services/ REST client, offline store/sync, voice and notification logic
  public/       manifest, service worker, SVG application icons
tests/          root integration/legacy-era tests
```

The root also contains phase reports, migration documents, `.env`,
`.env.example`, `campusflow.db`, `verify.bat`, `check_env.py`, and runtime log
files. No Dockerfile, docker-compose file, Procfile, or Render configuration
was found by the repository inventory.

## 4. Frontend Inventory

| Page/component | Purpose | Role | Backend/API or WS | Status |
|---|---|---|---|---|
| `LoginPage.tsx` | Community/Department login UI | Community, Department | Existing auth endpoints | PARTIAL: source exists, route redirects away |
| Registration UI | User registration screen | Community | Auth registration methods/endpoints exist | MISSING: `SignupPage.tsx` absent |
| `App.tsx` / `Dashboard.tsx` | Command dashboard and incident overview | Command/admin compatibility role | `/health`, incidents, activity, system, WebSocket | IMPLEMENTED |
| `CitizenPortal.tsx` | Community report and private incident progress | Community/user | incidents, chat, locations, notifications, WS | IMPLEMENTED, auth-gated route |
| `DepartmentPortal.tsx` | Department-scoped feed and assignment actions | Department | incidents, assignments, resources, transport, WS | IMPLEMENTED |
| `RiskPanel.tsx` | Risk summary and early-warning display | Command | risk summary API | IMPLEMENTED |
| `DisasterRiskMap.tsx` | Leaflet map with risk, vulnerability, hazards, sensors, incidents, rescue requests, resources, facilities, routes and alerts | Command | `/api/v1/map/overview`, route APIs, offline snapshot, WS | IMPLEMENTED, backend-connected |
| `ResourcesPage.tsx` | Search/filter resource inventory | Command | `/api/v1/resources` | IMPLEMENTED |
| `ResponsesPage.tsx` | Pending response plans and approval decisions | Command | response plans and approvals | IMPLEMENTED |
| `TravelSafetyPage.tsx` | Destination risk and recommendation | Command/user | travel safety API | IMPLEMENTED |
| `ActivityPage.tsx` | Audit/event timeline | Command | activity API | IMPLEMENTED |
| Sensors UI | Sensor status and sensor history | Command | sensor APIs | MISSING as a dedicated page; map consumes data |
| Rescue Requests tab | Rescue intake/coordination | Command/community | backend rescue API exists | PARTIAL: `DomainPlaceholderPage` |
| Shelters & Hospitals tab | Facility discovery | Command/community | backend resource APIs exist | PARTIAL: `DomainPlaceholderPage` |
| Alerts tab | Alert list and warning management | Command/community | notifications/alerts/WS exist | PARTIAL: `DomainPlaceholderPage`; bell/WS exist |
| Monitoring page | Monitoring/re-plan visibility | Command | backend re-plan and activity APIs | PARTIAL: no dedicated page |
| `OfflineStatus.tsx` | Connectivity indicator and sync action | All active shells | IndexedDB/localStorage and sync | IMPLEMENTED in source; browser E2E not run |

The sidebar labels are disaster-focused: Dashboard, AI Command 3D, Risk &
Early Warning, Travel Safety, Disaster Map, Disaster Events, Emergency
Resources, Rescue Requests, Shelters & Hospitals, Response Plans, Alerts, and
Activity Logs. There is no complaint navigation.

## 5. Backend Inventory

The FastAPI application is `backend.main:app`. Registered routers include:

- incidents, resources, responses, approvals, dispatch, audit, simulation,
  events, routes, auth, telemetry, voice, system, assignments, notifications,
  alerts, disaster domain, chat, campus locations, transport, road
  conditions, risk, weather, phase3/disaster intelligence, and map.
- `/health` performs `SELECT 1` and counts database resources.
- CORS includes localhost/127.0.0.1 ports 5173, 5175, 5176, and 3000.

Current backend services include authentication, duplicate/corroboration,
incident severity, event visibility, event engine, audit, weather providers,
environment providers, sensor monitoring, deterministic risk, early warning,
resource coordination, rescue priority, safe routing, response planning,
dispatch, assignment, notification, monitoring/re-planning, travel safety,
transport tracking, voice, memory, and provider adapters.

## 6. Database Inventory

Actual SQLite tables read-only from `campusflow.db`:

| Table/model | Purpose | Current/legacy | Status |
|---|---|---|---|
| `users` / `UserDB` | Admin/operator-compatible and community user accounts | Current auth with compatibility roles | Used |
| `department_users` / `DepartmentUserDB` | Department account and role records | Current auth | Used |
| `incidents` / `IncidentDB` | Human/community and disaster events | Current | Used by both intake paths |
| `campus_resources` / `CampusResourceDB` | Emergency resources, vehicles, teams, shelters, hospitals | Current functionality with compatibility name | Used by map, MCP, routing, response |
| `response_plans` / `ResponsePlanDB` | Recommended action plans and approval state | Current | Used |
| `audit_logs` / `AuditLogDB` | Immutable operational actions and traces | Current | Used |
| `incident_status_history` | Incident lifecycle history | Current model, sparse runtime use | Present |
| `agent_runs` / `AgentRunDB` | Disaster intelligence run/results | Current | Used; 15 rows observed |
| `agent_events` / `AgentEventDB` | Agent event persistence model | Current | Table present; 0 rows observed in DB audit |
| `department_responses` | Department assignment/response state | Current | Used; 284 rows observed |
| `resource_assignments` | Assigned physical resources | Current | Present; 0 rows observed in DB audit |
| `routes` / `RouteDB` | Route versions and geometry/path | Current | Used; 2 rows observed |
| `route_replans` | Re-planning records | Current | Present; 0 rows observed |
| `transport_telemetry` | Vehicle GPS telemetry | Current | Present; 0 rows observed |
| `road_conditions` | Blocked/cleared road conditions | Current | Present; 0 rows observed |
| `notifications` | Alerts and targeted notifications | Current | Used; 1,294 rows observed |
| `chat_messages` | Community assistant chat history | Current | Present; 0 rows observed |
| `regions` | Disaster regions | Current | Used; 2 rows observed |
| `zones` | Risk/geographic zones | Current | Used; 3 rows observed |
| `communities` | Community metadata | Current | Used; 1 row observed |
| `weather_observations` | Normalized weather history | Current | Used; 11 rows observed |
| `environmental_observations` | Normalized environmental indicators | Current | Used; 25 rows observed |
| `risk_predictions` | Persisted deterministic predictions | Current | Used; 18 rows observed |
| `sensor_observations` | Persisted normalized sensor readings | Current | Used; 28 rows observed |
| `sensor_events` | Persisted anomalies | Current | Used; 28 rows observed |
| `rescue_requests` | Community/rescue requests | Current | Used; 1 row observed |

No complaint-specific table or model was found.

The database is not cleanly rebranded. Read-only samples showed historical
values such as Vignan resource names, `security@vignan.ac.in`,
`student@vignan.ac.in`, `Campus Safety Director`, `Campus Operator`, and
`Demo Student`, alongside newer `@aitam.local` accounts and Nepal records.
This is an actual persisted-state issue, not merely documentation.

## 7. Agent Inventory

### Current disaster-intelligence agent classes

Defined in `backend/agents/disaster_intelligence.py` and registered in
`SPECIALIST_AGENTS`:

- `DisasterAnalysisAgent`
- `WeatherAnalysisAgent`
- `RiskAnalysisAgent`
- `GeoVulnerabilityAgent`
- `HydrologyEnvironmentalAgent`
- `MedicalTriageAgent`
- `SearchRescueAgent`
- `SecurityPublicSafetyAgent`
- `InfrastructureAgent`
- `ResourceAgent`
- `RescuePriorityAgent`
- `RoutingAgent`
- `ShelterAgent`
- `HospitalAgent`
- `ResponsePlannerAgent`
- `CommunicationAgent`
- `MonitoringAgent`
- `RecoveryAgent`
- `TravelSafetyAgent`
- `SupervisorIncidentCommander`

The base specialist classes for several operational agents return generic
completed results. They are registered and connected, but not all are
specialized implementations in the newer graph.

### Operational incident agents

Concrete evaluation agents exist in separate modules for supervisor,
security, medical, transport, communication, fire, and facilities. These are
connected to the older `backend/graph/workflow.py` incident graph and are used
by normal incident analysis/response-plan paths.

No complaint classifier, student-complaint agent, campus-complaint router, or
Vignan complaint agent exists in the current source tree.

## 8. LangGraph Architecture

### New disaster-intelligence graph — actually used by sensor/domain events

`backend/services/disaster_intelligence_service.py` imports and invokes
`run_disaster_workflow` from `backend/graph/disaster_workflow.py`.

```text
START
  ↓
supervisor
  ↓ conditional Send fan-out
┌─────────────────────────────────────────────────────────────┐
│ disaster_analysis | weather_analysis | risk_prediction      │
│ geo_vulnerability | hydrology_environmental (conditional)   │
│ medical_triage | search_rescue | security_public_safety     │
│ infrastructure | communication | shelter | hospital         │
│ (selection depends on disaster_type/event_source)           │
└─────────────────────────────────────────────────────────────┘
  ↓ all selected specialist branches join
situation_state
  ↓
resource_coordination
  ↓
priority_evaluation
  ↓
safe_routing
  ↓
response_planner
  ↓
approval_gate
  ↓
monitoring
  ↓
recovery
  ↓
END
```

Parallel behavior is explicit: `Send` objects are returned by `_fan_out`, and
each selected specialist edge joins at `situation_state`. Resource, priority,
routing, planning, approval-gate, monitoring, and recovery are sequential.

The graph state contains normalized event source, zone/region, weather,
environment, sensors, geography, community reports, rescue requests,
resources, routes, response plan, alerts, approval status, agent results,
errors, audit events, and re-plan state.

The response plan is constructed in `_planner` after resource, priority, and
routing nodes. Human approval is represented as `approval_status = pending`
and persisted to `response_plans`; the graph itself then proceeds to
monitoring/recovery. The actual human decision occurs in
`POST /api/v1/approvals/{plan_id}/decide`.

### Older emergency graph — actually used by normal incident response plans

`backend/graph/workflow.py` is imported by `backend/api/incidents.py` and
`backend/services/response_service.py`.

```text
START → supervisor
          ↓ conditional selected branches
security / medical / transport / communication / fire / facilities
          ↓ fan-in
      synthesizer → END
```

Selected branches execute through LangGraph fan-out and merge at the
synthesizer. This graph generates recommendations, approval requirements, and
MCP-grounded resources. It does not itself dispatch teams or send external
notifications.

### Risk graph

`backend/graph/risk_workflow.py` is sequential:

```text
START → deterministic_risk_engine → risk_prediction_agent → END
```

The risk engine calculates the score; `RiskPredictionAgent` interprets the
result. This is not a multi-agent fan-out graph.

## 9. Sensor Architecture

`backend/services/sensor_monitoring.py` provides:

- `SensorProvider` protocol.
- `DemoSensorProvider` with `nepal_mountain`, `urban_flood`, `cyclone`, and
  `heatwave` scenarios.
- `ExternalSensorProvider` boundary that currently raises
  `SensorProviderUnavailable` because no physical gateway is configured.
- `SensorAnomalyDetector` with per-sensor thresholds and `high`/`critical`
  levels.
- Persistence to `sensor_observations` and `sensor_events`.
- Mirroring rainfall/temperature/wind to weather observations and water,
  moisture, ground movement, and tilt to environmental observations.
- Event-engine events `sensor_update`, `environment_anomaly`, and
  `disaster_detected`.
- `phase3.py` routes sensor events into
  `trigger_disaster_intelligence`, which uses the shared disaster graph.

The Nepal provider emits rainfall 180, river level 88, soil moisture 92, and
ground movement 80. A live run produced sensor events, anomalies, and the
shared disaster event without a human image upload.

## 10. Risk Architecture

`backend/services/risk_engine.py` contains deterministic scoring with typed
features, normalized 0–100 values, risk levels low/medium/high/critical,
confidence, contributing factors, explanations, recommendations, freshness,
and stale-data fields. `backend/services/risk_service.py` joins provider data,
environmental data, community/rescue signals, historical zone data, persists
predictions, and invokes `risk_workflow.py`.

Weather provider abstraction:

- `DemoWeatherProvider` is active locally.
- `ExternalWeatherProvider` uses configured HTTP provider settings when
  configured.
- `fetch_with_fallback` returns normalized data plus provider/fallback status.

Environmental provider abstraction:

- `DemoEnvironmentalProvider` is active locally.
- `EnvironmentalProvider` is a protocol boundary.
- `/api/v1/weather/environment` exposes persisted environment observations;
  there is no `/api/v1/environmental-observations` path.

Risk APIs include current predictions, summary, zones, history, early
warnings, prediction, and weather/environment ingestion/history. The event
engine publishes weather/environment/risk-related updates, and the frontend
uses WebSocket refresh triggers, but there is no separate dedicated frontend
risk-history/trend visualization beyond the risk panel/map.

Runtime N-14 evidence produced a current critical landslide prediction of
94.44/100 and a high flood prediction of 63.32/100 with 100% confidence.

## 11. GIS Architecture

`frontend/src/components/DisasterRiskMap.tsx` uses Leaflet and an OpenStreetMap
tile layer. It requests `/api/v1/map/overview`, caches the response as an
offline snapshot, and renders backend data for:

- risk polygons
- vulnerable zones
- hazard polygons
- sensor markers and status/trend
- active incident markers
- rescue-request markers
- resource markers classified into shelter, hospital, rescue team, vehicle,
  emergency-service, and generic resource layers
- safe and blocked route lines
- alert areas
- tourist-safety overlay
- current device/operator location when available

Filters include disaster type, risk level, region, zone, resource status,
sensor status, and alert status. Marker popups use backend fields including
confidence, freshness, source, capacity, assignment, contact, and route ETA.

`backend/services/map_overview.py` assembles the overview from persisted
`RiskPredictionDB`, `ZoneDB`, `SensorObservationDB`, `IncidentDB`,
`RescueRequestDB`, `CampusResourceDB`, `RouteDB`, and `NotificationDB` rows.
The map is therefore backend-connected, not just a static component.

Limitations: route geometry still uses compatibility campus graph names and
coordinates for some persisted rows; current map/resource data is mixed with
historical Vignan/campus rows in the local database. No browser visual audit
or console capture was available in this environment.

## 12. Authentication Architecture

Backend auth APIs:

- `/api/v1/auth/login` for username/password operator/admin-compatible users.
- `/api/v1/auth/user/login` and `/api/v1/auth/user/register` for community
  user email/phone flow.
- `/api/v1/auth/department/login` and `/api/v1/auth/department/register` for
  department accounts.
- `/api/v1/auth/signup` compatibility endpoint.
- `/api/v1/auth/me` token validation.

Frontend `AuthContext` maintains `cf_token`/`cf_user`, validates `/me`, and
provides operator-compatible, citizen, registration, and department helpers.
`ProtectedRoute` and role helpers enforce command, community, department, and
department-management access where those routes are reached.

Current intended visible roles in `LoginPage.tsx` are exactly Community and
Department. However, `AppRoutes.tsx` currently redirects `/login` and
`/signup` to `/command`, and `/command` is unguarded. Therefore the intended
login screen is not part of the default runtime flow. The source still has
auth behavior, while the local demo intentionally bypasses it.

The read-only database audit found 14 `operator`, 4 `student`, and 35 `user`
rows in `users`, plus 18 department rows. Both old `@vignan.ac.in` and newer
`@aitam.local` department accounts are persisted. No account was created or
changed during this audit.

## 13. Offline/PWA Architecture

Implemented source elements:

- `frontend/public/manifest.webmanifest` with AITAM name, theme, start URL,
  and 192/512 SVG icons.
- `frontend/public/sw.js` caches app shell and same-origin GET resources;
  API responses and external map tiles are intentionally not cached by the
  service worker.
- `offlineStore.ts` uses IndexedDB stores `snapshots` and `incident-queue`.
- localStorage fallback is used when IndexedDB is unavailable.
- `offlineSync.ts` queues incident reports, retries on reconnect, removes
  successfully synced operations, and sends a client operation ID.
- `OfflineStatus.tsx` listens for online/offline events and exposes sync UI.
- The map saves/reads backend overview snapshots with cached timestamps.
- Backend incident intake contains duplicate/idempotency handling via the
  client operation ID path.

Unit tests cover operation ID generation and basic offline safeguards. The
browser offline transition, service-worker install, IndexedDB replay, and
duplicate replay were not executed with browser automation, so the full
runtime claim is PARTIALLY VERIFIED rather than fully verified.

## 14. WebSocket Architecture

Backend endpoint: `/api/v1/events/ws`.

The backend resolves connection scope from a token query parameter and filters
events through `event_visibility.py`. The frontend builds the local URL from
`VITE_API_BASE_URL`, defaulting to `http://127.0.0.1:8000` and changing the
scheme to `ws`.

The command app, community portal, department portal, map, and realtime
provider all consume the existing event stream; the source contains comments
about avoiding a second socket, although several components have their own
client listeners.

A live read-only WebSocket connection received these events while the existing
Nepal simulation was triggered: `sensor_update`, `environment_anomaly`, and
`disaster_detected`. The backend also publishes workflow, agent, resource,
response-plan, approval, alert, monitoring, and re-plan events.

## 15. API Inventory

All paths below were obtained from the running `/openapi.json`, not from phase
reports. They are grouped by router and classified as current, partial, or
compatibility. `Auth` means server-side protection exists or is applied by
the endpoint; exact anonymous behavior also depends on the configured
`ALLOW_ANONYMOUS_ADMIN` compatibility flag.

### System/auth/current domain APIs

| Method | Path | Purpose | Auth | Frontend consumer | Status |
|---|---|---|---|---|---|
| GET | `/health` | Service/database/resource health | No | App/header | WORKING |
| GET | `/api/v1/system/status` | Core service status | No | Header | WORKING |
| GET | `/api/v1/activity`, `/api/v1/activity/{incident_id}` | Audit timeline | Command-compatible | Activity/incident view | WORKING |
| POST | `/api/v1/auth/login` | Username/admin-compatible login | Credentials | AuthContext/LoginPage | WORKING API |
| GET | `/api/v1/auth/me` | Validate token | Token | AuthContext | WORKING API |
| POST | `/api/v1/auth/user/login` | Community email/phone login | Credentials | AuthContext | WORKING API |
| POST | `/api/v1/auth/user/register` | Community registration | No/endpoint policy | AuthContext method; no page | PARTIAL |
| POST | `/api/v1/auth/signup` | Compatibility signup | Endpoint policy | API method; no page | PARTIAL/compatibility |
| POST | `/api/v1/auth/department/login` | Department login | Credentials | AuthContext/LoginPage | WORKING API |
| POST | `/api/v1/auth/department/register` | Department provisioning | Command/admin | Department management | WORKING API |
| GET | `/api/v1/departments`, `/api/v1/departments/{department_id}` | Department catalog | Mixed | Department UI | WORKING |
| GET | `/api/v1/communities` | Community catalog | No | No dedicated consumer identified | WORKING API |
| GET | `/api/v1/regions`, `/api/v1/zones` | Disaster geography | No | Map/domain services | WORKING |
| GET,POST | `/api/v1/disasters` | Disaster events | Optional/command policy | Domain/service paths | WORKING |
| GET,POST | `/api/v1/incidents` | Generic/community incident intake | Optional/role-scoped | App/community/report modal | WORKING |
| GET | `/api/v1/incidents/{incident_id}` | Incident detail | Scoped | Incident command/community | WORKING |
| POST | `/api/v1/incidents/analyze-raw` | Supervisor analysis | Command-compatible | Report/incident flow | WORKING |
| POST | `/api/v1/incidents/{incident_id}/analyze` | Analyze incident | Command | Command view | WORKING |
| POST | `/api/v1/incidents/{incident_id}/orchestrate` | Run incident orchestration | Command | Command/response | WORKING |

### Response, rescue, resources, and routing APIs

| Method | Path | Purpose | Auth | Frontend consumer | Status |
|---|---|---|---|---|---|
| GET | `/api/v1/resources`, `/api/v1/resources/{resource_id}` | Resource inventory/details | Mixed | Resources/map | WORKING |
| GET | `/api/v1/resources/search/available` | Available resource search | Command-compatible | Backend agents | WORKING API |
| GET | `/api/v1/shelters` | Shelter records | No | Map; placeholder tab | WORKING API |
| GET | `/api/v1/hospitals` | Hospital records | No | Map; placeholder tab | WORKING API |
| GET | `/api/v1/emergency-services` | Emergency-service resources | No | Map/domain | WORKING API |
| GET,POST | `/api/v1/rescue-requests` | Rescue intake/list | Optional/scoped | Backend/map; placeholder tab | PARTIAL UI |
| GET | `/api/v1/response-plans`, `/api/v1/response-plans/{plan_id}` | Response plans | Command-compatible | Responses/command | WORKING |
| POST | `/api/v1/response-plans/generate/{incident_id}` | Generate plan | Command | Command/Responses | WORKING |
| GET | `/api/v1/approvals/pending` | Pending approvals | Current endpoint | Responses | WORKING |
| POST | `/api/v1/approvals/{plan_id}/decide` | Human decision | Command/admin | Responses | WORKING |
| POST | `/api/v1/dispatch/{plan_id}/execute` | Execute approved dispatch | Command | Command | WORKING API |
| GET | `/api/v1/routes/calculate` | Safe route calculation | Mixed | Map/agents | WORKING |
| POST | `/api/v1/road-conditions` | Block/clear road report | Command | Command simulation | WORKING API |
| POST | `/api/v1/simulation/block-road` | Demo route blockage | Command | Incident command | WORKING |
| POST | `/api/v1/simulation/fail-resource` | Demo resource failure | Command | Simulation controls | WORKING |

### Weather, environment, risk, sensors, map, travel

| Method | Path | Purpose | Auth | Frontend consumer | Status |
|---|---|---|---|---|---|
| GET | `/api/v1/weather/current` | Current normalized weather | No | Risk/travel/backend | WORKING |
| GET | `/api/v1/weather/zone/{zone_id}` | Zone weather | No | Backend | WORKING |
| GET | `/api/v1/weather/history` | Weather history | No | Backend/travel | WORKING |
| GET | `/api/v1/weather-observations` | Weather rows | No | Domain/backend | WORKING |
| GET,POST | `/api/v1/weather/environment` | Environmental rows/ingestion | Mixed | Backend/risk | WORKING |
| POST | `/api/v1/weather/ingest` | Weather ingestion | Command | Backend/provider | WORKING |
| GET | `/api/v1/risk`, `/api/v1/risk/{prediction_id}` | Risk data/detail | Mixed | Risk/map/backend | WORKING |
| GET | `/api/v1/risk/summary`, `/api/v1/risk/zones` | Risk summary/zones | No | RiskPanel/map | WORKING |
| GET | `/api/v1/risk/early-warnings` | Warning records | No | Backend/risk | WORKING |
| POST | `/api/v1/risk/predict` | Deterministic prediction | Mixed | Backend | WORKING |
| GET | `/api/v1/risk-predictions` | Prediction history | No | Backend | WORKING |
| GET,POST | `/api/v1/sensor-events` | Sensor anomaly list/ingest | Mixed | Backend/map | WORKING |
| GET | `/api/v1/sensors`, `/api/v1/sensors/status` | Sensors/status | No | Backend/map | WORKING API |
| POST | `/api/v1/sensor-simulations` | Existing deterministic scenarios | Command | Simulation control/backend | WORKING |
| GET | `/api/v1/map/overview`, `/api/v1/map/{layer}` | Consolidated map layers | No | DisasterRiskMap | WORKING |
| GET,POST | `/api/v1/travel/safety-check` | Travel safety result | No | TravelSafetyPage | WORKING |

### Events, monitoring, departments, transport, ancillary APIs

| Method | Path | Purpose | Auth | Frontend consumer | Status |
|---|---|---|---|---|---|
| POST | `/api/v1/events` | Trigger converged disaster event | Optional | Backend/domain | WORKING API |
| WebSocket | `/api/v1/events/ws` | Filtered live event stream | Token/query or compatibility | App/portals/map | WORKING |
| POST | `/api/v1/monitoring/replan/{event_id}` | Re-run approval-gated plan | Command-compatible | Backend/command | WORKING API |
| GET | `/api/v1/agent-runs/{run_id}`, `/trace` | Agent results/trace | Command-compatible | Command trace | WORKING |
| GET | `/api/v1/notifications` | Notifications | Scoped | Bell/portals | WORKING |
| POST | `/api/v1/notifications/read-all`, `/{id}/read` | Notification state | Scoped | Bell/portals | WORKING |
| GET | `/api/v1/portal/my-assignments` | Department assignments | Department | Department portal | WORKING |
| GET | `/api/v1/incidents/{id}/assignments` | Incident assignments | Scoped | Command/department | WORKING |
| POST | `/api/v1/incidents/{id}/assignments/{department}/...` | Accept, decline, team-assign, en-route, on-scene, completed | Department/command | Department portal | WORKING |
| GET | `/api/v1/campus-locations` | Location catalog | No | Report modal/map | CURRENT compatibility API |
| GET | `/api/v1/transport/assignments/{id}/tracking` | Transport tracking | Scoped | Department/map | WORKING |
| POST | `/api/v1/telemetry/location` | Vehicle location ingest | Device secret | Transport map | WORKING API |
| GET | `/api/v1/telemetry/status/{vehicle_id}` | Vehicle telemetry status | Mixed | Transport map | WORKING API |
| POST | `/api/v1/chat/message`; GET/DELETE `/api/v1/chat/history` | Community assistant | Community | PersonalAssistant | WORKING API |
| GET | `/api/v1/voice/audio/{audio_id}`; POST `/api/v1/voice/generate-audio` | Voice alert audio | Mixed | Voice controls | WORKING API |
| POST | `/api/v1/system/test-sms` | Provider test | Admin/command | No normal page | WORKING API |
| GET | `/api/v1/demo/scenarios/flood-critical` | Demo scenario endpoint | Mixed | No primary frontend consumer | WORKING API |

No legacy complaint API group was registered. The only missing path observed
for an expected name was `/api/v1/environmental-observations`; the actual
environment API is `/api/v1/weather/environment`.

## 16. Current User Flows

### Command flow

The local default route is `/command`. `App.tsx` loads health, incidents,
activity/system state, opens the command WebSocket, displays dashboard/map/risk
and permits report intake, simulation, response-plan review, approval,
dispatch, resolution, activity, and travel safety. The route is currently
unguarded because `/login` redirects to it and the command route itself does
not wrap `App` in `ProtectedRoute`.

### Community flow

The intended protected route is `/portal`. `CitizenPortal` fetches the current
user's incidents, opens a token-scoped safe-event WebSocket, polls as
reconciliation, opens `ReportEmergencyModal`, and provides the assistant.
The report uses the existing incident API and offline queue. The code supports
text/structured report fields and optional image/GPS fields; a photo is not
required for the sensor path.

### Department flow

`/dept/:department` validates the department and role. `DepartmentPortal`
fetches scoped incidents and assignments, supports accept/decline/en-route/on-
scene/completed/team-assigned actions, tracks transport assignments, consumes
targeted notification/assignment WebSocket events, and provides voice alert
controls.

## 17. Current Department Flows

Department codes represented in the actual frontend/backend are SECURITY,
MEDICAL, TRANSPORT, COMMUNICATION, FIRE, and FACILITIES. The newer domain
department catalog also includes search/rescue, logistics, shelter/relief,
infrastructure/utilities, GIS/geospatial, weather/environment, public
information, and community volunteer. The portal implementation is concrete
for the six primary department codes; the larger domain list is primarily
coordination metadata.

Department assignment APIs are backend-connected. However, the database audit
showed 0 rows in `resource_assignments`, so the existence of assignment code
does not mean the current local database has active resource-assignment rows.

## 18. Nepal Demo Flow

The existing `POST /api/v1/sensor-simulations` with
`{"scenario":"nepal_mountain"}` was executed against the running backend.

Observed path:

```text
DemoSensorProvider
  ↓ rainfall / river_level / soil_moisture / ground_movement
SensorMonitoringService.ingest
  ↓ sensor_observations + sensor_events + mirrored weather/environment rows
SensorAnomalyDetector
  ↓ high/critical anomalies
disaster_detected event
  ↓
run_demo_scenario -> trigger_disaster_intelligence
  ↓
deterministic risk prediction
  ↓
SupervisorIncidentCommander + LangGraph Send fan-out
  ↓
resource -> priority -> routing -> response plan -> pending approval
  ↓
monitoring/recovery state + WebSocket events
```

Latest live verification evidence:

- Region: `DEMO-NEPAL-MOUNTAIN`
- Zone: `DEMO-N14`
- Sensor values: rainfall 180, river level 88, soil moisture 92, ground
  movement 80
- Latest agent run: `RUN-FEE7D14E43B1` in the earlier clean run; the later
  live run also returned status 200 and a new event ID.
- Required specialist results were completed, including disaster, weather,
  risk, geo, hydrology, medical, search/rescue, public safety, resource,
  rescue priority, routing, response planner, approval gate, monitoring, and
  recovery states.
- Flood risk: 63.32/100, HIGH, 100% confidence.
- Landslide risk: 94.44/100, CRITICAL, 100% confidence.
- Response plan approval state: pending.
- Travel-safety endpoint returned a current NOT_RECOMMENDED result for N-14.
- Map overview returned risks, zones, hazards, sensors, incidents, rescue
  requests, resources, routes, alerts, and affected population.

This is the strongest currently connected demonstration and does not require
an uploaded image.

## 19. Community Report Flow

### Backend path

`POST /api/v1/incidents` enters `backend/api/incidents.py`. Depending on the
operation, it invokes supervisor analysis and the older emergency graph,
persists the incident, publishes lifecycle events, and later creates a
response plan through `response_service.py`.

### Domain event path

`POST /api/v1/events` enters `phase3.py` and calls
`trigger_disaster_intelligence`, which creates an `IncidentDB` disaster event,
creates a rescue request for community/human sources, adds community signal
data, predicts risk, and invokes the newer disaster graph.

These are both current paths, but they do not share one single graph: ordinary
incident intake uses the older graph, while domain/sensor event intake uses
the newer graph. That is an integration distinction requiring future design,
not an issue to fix during this audit.

## 20. Sensor-Only Flow

Sensor-only flow is actually connected and runtime-verified:

`DemoSensorProvider` → `SensorMonitoringService.ingest` → persisted reading and
anomaly → `disaster_detected` → `trigger_disaster_intelligence` → risk → newer
LangGraph → resources/priority/routes/plan/approval/monitoring → WebSocket.

Community alert creation is conditional on a critical prediction and uses a
notification row/event. Department/response notifications are produced by
the response and lifecycle notification services. The local system labels the
scenario as `DEMO/SIMULATION`.

## 21. Offline Flow

```text
ReportEmergencyModal
  ↓ network error/offline
queueIncidentReport
  ↓
IndexedDB incident-queue, or localStorage fallback
  ↓ browser online event / manual Sync
flushOfflineQueue
  ↓ POST /api/v1/incidents with client operation ID
duplicate/idempotency handling
  ↓
database incident + normal workflow
```

The map separately stores backend map-overview snapshots in IndexedDB or
localStorage fallback. The service worker caches the app shell but deliberately
does not cache API responses or external map tiles. Unit tests exist; browser
offline/reconnect behavior was not executed in this environment.

## 22. Tourist Safety Flow

`TravelSafetyPage` sends destination and optional current location to
`GET/POST /api/v1/travel/safety-check`. `travel_safety.py` resolves a zone,
reads current risk, weather, alerts, and route context, and returns risk,
hazards, active alerts, route status, recommendation, reasons, and timestamp.

For N-14 the running API returned current risk/alerts and `NOT_RECOMMENDED`.
The recommendation is not hard-coded in the frontend.

## 23. Feature Matrix — Original Requirements

| Requirement | Current implementation | Actual file(s) | API | Status |
|---|---|---|---|---|
| Risk prediction / early warning | Deterministic 0–100 engine, levels, warnings | `backend/services/risk_engine.py`, `risk_service.py`, `early_warning.py` | `/api/v1/risk/*` | IMPLEMENTED |
| Interactive vulnerable-location map | Leaflet + backend overview and filters | `DisasterRiskMap.tsx`, `map_overview.py` | `/api/v1/map/overview` | IMPLEMENTED |
| Nearby shelters | Resource records and map layer | `disaster_domain.py`, `map_overview.py` | `/api/v1/shelters` | PARTIAL: no dedicated page/distance UI |
| Nearby hospitals | Resource records and map layer | `disaster_domain.py`, `map_overview.py` | `/api/v1/hospitals` | PARTIAL: no dedicated page/distance UI |
| Emergency services | Resource filtering and map classification | `disaster_domain.py` | `/api/v1/emergency-services` | IMPLEMENTED API / PARTIAL UI |
| Emergency resources | Resource page, MCP, coordination | `ResourcesPage.tsx`, `resource_coordination.py` | `/api/v1/resources` | IMPLEMENTED |
| Real-time notifications/alerts | Notification rows, Bell, WS events | `notification_service.py`, `NotificationBell.tsx` | `/api/v1/alerts`, `/notifications`, WS | PARTIAL: Alerts tab placeholder |
| Administrator/rescue dashboard | Command dashboard and department portals | `App.tsx`, `DepartmentPortal.tsx` | incidents/assignments/etc. | IMPLEMENTED with auth bypass |
| Rescue prioritization | Deterministic priority node/service | `priority_engine.py`, disaster graph | rescue requests/domain APIs | IMPLEMENTED backend / PARTIAL UI |
| Offline/low-connectivity | Queue, fallback storage, sync, cached snapshots | `offlineStore.ts`, `offlineSync.ts`, `OfflineStatus.tsx` | incident API | PARTIAL: no browser E2E |
| Community-generated reports | Report modal and community portal | `ReportEmergencyModal.tsx`, `CitizenPortal.tsx` | `/api/v1/incidents`, `/disasters`, `/events` | IMPLEMENTED paths |
| Weather/environment/geographical analysis | Provider abstractions, normalized observations, zone vulnerability | `weather_providers.py`, `environmental_providers.py`, `risk_service.py` | weather/environment/risk APIs | IMPLEMENTED with demo/external boundary |

## 24. Feature Matrix — Extended Requirements

| Extended feature | Implementation | Status |
|---|---|---|
| Sensor-only detection | Demo provider, anomaly detector, persistence, event trigger | IMPLEMENTED |
| Nepal scenario | `DemoSensorProvider`, `run_demo_scenario`, N-14 seed data | IMPLEMENTED/runtime verified |
| Multi-agent orchestration | Two LangGraph workflows | IMPLEMENTED but split across paths |
| Parallel specialist agents | `Send` fan-out in `disaster_workflow.py`; branch fan-out in old graph | IMPLEMENTED |
| Human approval | Pending plans and approval decision API | IMPLEMENTED, graph does not interrupt/resume |
| Dynamic monitoring | Monitoring node and monitoring API | PARTIAL: dedicated UI absent |
| Re-planning | `replan_event`, route/plan regeneration | IMPLEMENTED API, sparse DB rows/UI |
| Tourist safety | Risk/weather/alerts/recommendation API and page | IMPLEMENTED |
| Offline incident queue | IndexedDB/localStorage queue and replay | IMPLEMENTED source, browser unverified |
| PWA | Manifest, service worker, icons | IMPLEMENTED source |
| WebSocket | Scope filtering, event engine, frontend clients | IMPLEMENTED/runtime event verified |
| Safe routing | Local graph/OSRM boundary, route records, map lines | IMPLEMENTED with compatibility campus graph |
| Blocked routes | Road condition/simulation and map style | IMPLEMENTED API/code, sparse current DB |
| Resource coordination | DB-backed resource selection/allocation | IMPLEMENTED backend/runtime verified |

## 25. Phase 1 Verification — Disaster Foundation

Classification: **IMPLEMENTED with persisted-data cleanup debt**.

Verified in code/runtime:

- Regions, zones, communities, incidents/disasters, resources, rescue
  requests, weather/environment observations, risk records, alerts, shelters,
  hospitals, emergency services, and API registration exist.
- Runtime counts included 2 regions, 3 zones, 1 community, 7 disasters, 28
  sensors/events, 13 resource API results, 4 shelters, 2 hospitals, 9
  emergency services, and 1 rescue request.
- The current local DB also contains historical campus/Vignan labels and
  extra old incidents/users; this is not a missing schema feature.

## 26. Phase 2 Verification — Weather + Risk

Classification: **IMPLEMENTED, demo-provider dependent locally**.

Verified:

- Weather provider protocol, external provider boundary, demo fallback,
  normalized values, timestamps, freshness/staleness fields.
- Environmental provider and persisted normalized indicators.
- Deterministic score, confidence, contributing factors, explanation,
  disaster-specific feature weights/logic, and risk levels low/medium/high/
  critical.
- Risk graph sequential engine → interpretation.
- Risk APIs, history, summary, early warnings, and weather/environment APIs.
- Weather/environment event publication exists.

Partial:

- No dedicated frontend historical trend visualization.
- External provider credentials/gateways are not configured in the local run;
  DEMO provider/fallback is the observed mode.
- An expected `/environmental-observations` path does not exist; the actual
  path is `/weather/environment`.

## 27. Phase 3 Verification — Multi-Agent + Sensor

Classification: **IMPLEMENTED for the sensor/domain path; PARTIALLY INTEGRATED
for the overall product UI/auth flow**.

Verified:

- Supervisor selection, newer LangGraph Send fan-out, specialist results,
  resource coordination, rescue priority, routing, response plan, approval
  state, monitoring, re-plan API, alerts, travel safety, audit logs, and trace
  API.
- Nepal sensor path reaches the newer graph without an image.
- Community/domain report path exists and converges through
  `trigger_disaster_intelligence` when using the domain event API.

Partial:

- Normal `/incidents` intake still uses the older emergency graph, so there are
  two orchestration paths rather than one unified pipeline.
- Several frontend capability tabs are placeholders.
- `agent_events` and assignment/replan/telemetry tables were empty in the
  read-only local DB audit even though their code/API exists.

## 28. Phase 4 Verification — GIS

Classification: **IMPLEMENTED and backend-connected, with data-quality debt**.

The map reads `/api/v1/map/overview` and renders actual persisted risk, zone,
hazard, sensor, incident, rescue, resource/facility, route, alert, and tourist
layers. Filters and marker details are implemented in source. Runtime map
overview returned all expected top-level collections.

The local database includes older campus-coordinate resource rows and the
route graph retains compatibility campus names. This prevents a clean claim
that all displayed geospatial data is already AITAM/Nepal-consistent.

## 29. Phase 5 Verification — Offline/PWA

Classification: **PARTIALLY IMPLEMENTED / PARTIALLY VERIFIED**.

Manifest, service worker, app icons, offline indicator, IndexedDB store,
localStorage fallback, queued report replay, client operation IDs, sync, and
map snapshots exist in source and frontend tests pass. Full browser offline
transition, service-worker install, cached snapshot load, and duplicate replay
were not exercised with browser automation.

## 30. Legacy Cleanup Status

### Active legacy functionality

None found for complaint semantics. No complaint route, API, service, agent,
model, prompt, or active frontend source match exists.

### Historical documentation

Legacy terms remain in migration/phase/audit documents such as
`MIGRATION_PLAN.md`, `PHASE_0_AUDIT.md`, `INCREMENT_2_REPORT.md`, and the
previous cleanup reports. These are historical records, not active code paths.

### Internal compatibility code

Remaining `operator`, `student`, `campusflow`, and campus names occur in auth
roles, API compatibility methods, test fixtures, storage keys, database/table
names, route graph names, and comments. These were not removed during this
read-only audit.

### Persisted legacy data

The local database contains Vignan-branded resources and department accounts,
including `@vignan.ac.in` addresses, plus historical incident strings. This is
the most important actual remaining legacy state.

### Current disaster functionality

Terms such as incident, community report, emergency, sensor, resource, risk,
rescue, and alert are active current functionality and must be preserved.

## 31. Broken Features

- Root test suite has one known pre-existing failure:
  `tests/test_supervisor_agent.py::test_api_analyze_incident_by_id`, where the
  expected null injured count becomes `1` through the existing LLM/event-loop
  fallback behavior. Final result: 52 passed, 1 skipped, 1 failed.
- No dedicated browser-console/runtime UI audit was possible, so visual and
  browser-only failures are UNKNOWN rather than claimed absent.
- Normal login navigation is intentionally bypassed by current route redirects;
  this is a behavior/configuration state, not a runtime crash.

## 32. Missing Features

- Reachable login/registration UI in the active route graph.
- Dedicated Sensors page.
- Dedicated Alerts data page.
- Dedicated Rescue Requests data page.
- Dedicated Shelters & Hospitals data page.
- Dedicated Monitoring/Re-planning page.
- Browser-level offline/PWA verification harness.
- Physical external sensor gateway integration.
- Configured live weather/environment provider integration.

## 33. Disconnected Features

- Backend rescue, shelter, hospital, emergency-service, and alert APIs are not
  connected to dedicated frontend pages; some are only consumed by the map or
  shown through placeholders.
- The normal human incident path and sensor/domain path use different graphs.
- The newer approval gate produces pending state but does not suspend/resume
  the graph itself; approval occurs in a separate API flow.
- Agent event persistence table was empty even though lifecycle events and
  trace output are available through other paths.
- Resource assignment and route-replan persistence tables were empty in the
  current database audit, so those code paths are not evidenced as populated
  by current local data.
- The community UI is protected in source, but default route behavior bypasses
  login and opens the command shell.

## 34. Technical Debt

- Compatibility naming remains across database/table names, auth roles,
  storage keys, campus-location APIs, and local routing graph.
- The running DB path remains `campusflow.db`, while `.env.example` advertises
  an AITAM database filename.
- Local persisted seed data is mixed old/new and was not migrated.
- `google-generativeai` emits a deprecation warning; tests also emit async gRPC
  cleanup warnings.
- Root and backend tests contain historical operator/campus/student fixtures.
- Some active UI copy still says command/operator internally even though the
  visible login role labels are Community/Department.
- The frontend package is buildable, but the ordinary Vite dev-server path was
  not the verified local serving path; port 5173 currently served the built
  `frontend/dist` output through an existing static server.

## 35. Test Results

Tests were run without changing tests during this audit.

- Backend suite: **111 passed**, 4 warnings.
- Frontend suite: **96 passed**, 10 test files.
- Root/legacy suite: **52 passed, 1 skipped, 1 known/pre-existing failure**.
- Frontend production TypeScript/Vite build: successful.
- Sensor, risk, map, phase, offline, and auth tests are present in the
  repository and included in the backend/frontend runs where applicable.
- Live integration checks were performed for health, OpenAPI, database-backed
  domain endpoints, Nepal sensor simulation, agent trace, risk, map,
  resources, routing, approval pending state, travel safety, and WebSocket
  events.

## 36. Build Results

`npm.cmd run build` succeeded:

- 1,875 frontend modules transformed.
- TypeScript compilation passed.
- Vite production bundle generated in `frontend/dist`.
- Only the existing large-chunk warning was emitted.

## 37. Local Run Status

| Service | Status | Evidence |
|---|---|---|
| Backend | RUNNING | `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`, `/health` 200 |
| Frontend built output | RUNNING | `http://127.0.0.1:5173/` returned 200 |
| Database | CONNECTED | `/health` returned `database: connected`; read-only SQLite audit succeeded |
| REST API | CONNECTED | `/openapi.json` and domain endpoints returned 200 |
| WebSocket | CONNECTED | Live sensor simulation delivered `sensor_update`, `environment_anomaly`, `disaster_detected` |
| Map data | WORKING | `/api/v1/map/overview` returned all layer collections |
| PWA files | PRESENT | manifest, service worker, and icons present |

Local URLs:

- Backend: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`
- Frontend: `http://127.0.0.1:5173`
- WebSocket: `ws://127.0.0.1:8000/api/v1/events/ws?token=<token>`

## 38. Critical Issues

1. **Persisted database is not fully cleaned.** Historical Vignan resource
   names, department emails, student/community records, and campus incidents
   remain in `campusflow.db`. This audit did not alter them.
2. **Authentication is bypassed at runtime.** `/login` and `/signup` redirect
   to an unguarded `/command` route even though auth code and role guards
   exist.
3. **Frontend feature completeness is lower than backend completeness.** The
   rescue, shelters/hospitals, and alerts tabs are placeholders; Sensors and
   Monitoring lack dedicated pages.
4. **There are two active orchestration graphs.** Human incident intake uses
   `backend/graph/workflow.py`; sensor/domain events use
   `backend/graph/disaster_workflow.py`.
5. **Approval is API-gated, not graph-interrupt gated.** The newer graph
   records pending approval and continues to monitoring/recovery.
6. **External integrations are not live locally.** Demo weather/environment
   providers are active and the physical sensor provider explicitly reports
   unavailable.

## Recommended Next Implementation Order

Recommendations only; nothing below was implemented during this audit.

1. Decide and implement the intended authentication runtime: either restore
   the reachable Community/Department login flow or formally document the
   unguarded local-demo mode. Actual files: `frontend/src/AppRoutes.tsx`,
   `LoginPage.tsx`, `AuthContext.tsx`, and `ProtectedRoute.tsx`.
2. Prepare a reviewed, backup-first data migration for `campusflow.db` to
   classify/replace historical Vignan resources, department accounts, and
   old incident display values without deleting current disaster records.
3. Replace the three `DomainPlaceholderPage` uses in `App.tsx` with connected
   Alerts, Rescue Requests, and Shelters/Hospitals pages using the already
   registered APIs.
4. Add a dedicated Sensors/Monitoring view over `/sensors`, `/sensor-events`,
   `/sensors/status`, `/agent-runs`, and `/monitoring/replan` so judge-visible
   sensor-to-response evidence does not depend on map popups or backend logs.
5. Choose and unify the human-report and sensor/domain orchestration paths, or
   explicitly define their boundary. The concrete split is
   `backend/api/incidents.py`/`graph/workflow.py` versus
   `backend/api/phase3.py`/`graph/disaster_workflow.py`.
6. Add a real LangGraph interrupt/resume checkpoint around
   `approval_gate` if the intended requirement is that execution genuinely
   waits before subsequent graph nodes; currently the decision is separate in
   `backend/api/approvals.py`.
7. Populate and expose agent lifecycle persistence consistently: the current
   `agent_runs`/trace path works, but `agent_events` was empty in the local DB
   audit. Review `event_engine.py`, `instrumentation.py`, and the agent-event
   model/API boundary.
8. Add browser-level integration checks for map layer rendering, WebSocket
   updates, offline queue/reconnect/idempotency, service-worker caching, and
   console/network errors. Existing frontend unit tests do not prove these
   browser behaviors.
9. Replace or clearly isolate compatibility campus routing/location data from
   the active AITAM/Nepal demonstration. Relevant files are
   `campus_locations.py`, `road_network.py`, `map_overview.py`, and persisted
   `campus_resources` rows.
10. Configure and verify external weather/environment and physical sensor
    adapters behind their existing provider protocols, while retaining the
    deterministic demo fallback for offline judging.

## Project Completion Estimate

These are audit estimates based on actual connected behavior, not claims from
historical phase reports.

- Core Problem Statement: **75%**
- Extended Features: **65%**
- End-to-End Integration: **58%**
- Judge Demo Readiness: **62%**

## Top 10 Remaining Work Items

1. Resolve the runtime login bypass and make Community/Department auth flow
   intentional and demonstrable.
2. Safely migrate historical Vignan-branded local database data while
   preserving current disaster rows and compatibility requirements.
3. Build connected Alerts, Rescue Requests, and Shelters/Hospitals frontend
   pages in place of the three current `DomainPlaceholderPage` instances.
4. Add a dedicated sensor and monitoring dashboard with visible agent trace,
   anomaly, risk, approval, and re-plan state.
5. Unify or clearly reconcile the two existing LangGraph orchestration paths.
6. Make the approval gate a true pause/resume boundary if that is required by
   the judge narrative.
7. Ensure agent lifecycle, resource assignment, and route-replan records are
   persisted and visible; those tables were empty in the current DB audit.
8. Add browser E2E coverage for the actual map, WebSocket, PWA, offline queue,
   reconnect, and idempotent replay behaviors.
9. Cleanly separate active AITAM/Nepal geospatial data from compatibility
   campus graph/resource names.
10. Verify live provider adapters and document the deterministic fallback mode
    for environments without external weather/sensor credentials.

## Final Classification

### Implemented

FastAPI backend, SQLite persistence, disaster domain, deterministic risk,
weather/environment abstractions, sensor-only Nepal detection, current map
overview, resources, rescue backend, routing, alerts backend, approval API,
travel safety, WebSocket events, LangGraph fan-out, offline source modules,
PWA assets, community report path, and department APIs.

### Partial

Reachable authentication UI, registration UI, dedicated sensor/monitoring UI,
alerts/rescue/shelter frontend pages, external provider operation, browser
offline/PWA behavior, unified human/sensor graph, and graph-level human
interrupt/resume.

### Broken/known failing

One known root-suite supervisor timing/fallback failure; dependency warnings;
no evidence of a browser-console audit in this environment.

### Missing

Dedicated Sensors page, dedicated Monitoring page, dedicated Alerts page,
dedicated Rescue Requests page, dedicated Shelters/Hospitals page, and a
reachable registration screen.

### Disconnected

Several backend domain APIs from their dedicated frontend screens; normal
human and sensor graph paths; graph approval interrupt semantics; some
agent-event/resource-assignment/replan persistence evidence; and runtime auth
from the active default route.
