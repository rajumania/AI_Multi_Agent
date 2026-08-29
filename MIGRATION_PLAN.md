# Migration Plan

## Disaster Prediction and Community Response System

Status: audit and planning only. No application code was changed for this
document.

## Audit scope and baseline

The repository is an existing CampusFlow AI deployment, not a blank project.
The migration should therefore be additive and staged. The current stack is:

- Backend: Python, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy, and a SQLite
  database (`campusflow.db`). `psycopg` is installed and the engine accepts a
  PostgreSQL URL, but the checked-in runtime defaults to SQLite.
- Agent layer: synchronous Python agents under `backend/agents/`, with
  Gemini/OpenAI selection and a deterministic heuristic fallback in
  `backend/services/llm_service.py`.
- Orchestration: LangGraph under `backend/graph/`. A supervisor classifies the
  report, selected specialist nodes run, and a synthesizer creates response
  recommendations.
- API: FastAPI routers under `backend/api/`, all using `/api/v1/...` contracts.
- Persistence: SQLAlchemy models under `backend/database/models.py`; startup
  runs `Base.metadata.create_all`, an additive `ensure_schema` migration, and
  idempotent resource/user seeding.
- Frontend: React 18 + TypeScript + Vite + React Router. State is primarily
  React state/context and a realtime reducer; there is no Redux-style store.
- Maps: Leaflet with direct OpenStreetMap, Esri, CARTO, and OpenTopoMap tile
  URLs, plus campus catalog coordinates, resource markers, routes, and live
  transport overlays.
- Realtime: one in-process event engine and one WebSocket endpoint,
  `/api/v1/events/ws`, with role/department/citizen visibility filtering.
- Deployment artifacts: `backend/requirements.txt`, `frontend/package.json`,
  lockfile, Vite config, and runtime `.env.example` exist. No Dockerfile,
  docker-compose file, Render manifest, Procfile, CI workflow, or other
  repository deployment manifest was found.

### Verification performed

The existing tests were run without changing source files:

| Area | Result |
|---|---|
| `python -m pytest backend/tests -q` | 84 passed |
| `python -m pytest tests -q` | 52 passed, 1 skipped, 1 failed |
| `npm.cmd test -- --run` from `frontend` | 92 passed in 8 files |
| `npm.cmd run build` from `frontend` | Succeeds; Vite reports a large-chunk warning |

The legacy failure is `tests/test_supervisor_agent.py::test_api_analyze_incident_by_id`.
The automatic background pipeline can complete before the test's explicit
analysis assertion and populate `injured_count`, while the test expects it to
remain `null`. This is a real timing/contract risk to resolve before migration
changes are introduced. Test runs also produced repeated Gemini/grpc
event-loop and deprecation warnings. The installed `google.generativeai`
package reports that it is deprecated in favor of `google.genai`.

The local `.env` contains credential-shaped API values while `.env.example`
contains blanks. If those local values are real, they must be rotated and must
never be copied into the migration or deployment configuration.

## A. Existing architecture

### A.1 Backend entrypoint and request lifecycle

`backend/main.py` creates the FastAPI app, configures CORS, registers all
routers, and in the lifespan hook creates tables, runs additive migrations,
seeds resources/users, and registers lifecycle notifications. The health check
queries the database and reports the seeded resource count.

`backend/config.py` centralizes application, database, LLM, map/routing,
notification, telephony, dispatch, GPS, authentication, CORS, and webhook
settings. Configuration is loaded from the repository-level `.env` and ignores
unknown variables.

### A.2 Backend modules and ownership

| Existing area | Key files | Current responsibility | Migration disposition |
|---|---|---|---|
| API routers | `backend/api/*.py` | HTTP/WebSocket contracts for incidents, resources, response plans, approvals, auth, departments, notifications, routing, simulation, telemetry, voice, chat | Preserve contracts; add additive prediction/community endpoints |
| Domain models | `backend/models/*.py` | Pydantic enums and request/read/response schemas | Extend with prediction, vulnerability, facility, alert, and rescue schemas |
| ORM/database | `backend/database/database.py`, `models.py`, `migrate.py`, `seed.py` | SQLAlchemy engine, 17 ORM tables, additive schema changes, seed data | Preserve existing tables; add versioned additive migrations/tables |
| LangGraph | `backend/graph/state.py`, `nodes.py`, `workflow.py`, `instrumentation.py` | Supervisor, conditional specialist fan-out, synthesizer, lifecycle events | Retain as response subgraph; add prediction and community-response stages |
| Agents | `backend/agents/*.py` | Supervisor plus security, medical, transport, communication, fire, facilities agents | Preserve response agents; add prediction, vulnerability, alert, and resource-prioritization agents |
| Services | `backend/services/*.py` | Severity, response planning, dispatch, assignment, notification, routing, telemetry, auth, memory, simulation | Reuse stable services; add feature/forecast/risk/queue services |
| MCP | `backend/mcp/` | Deterministic resource lookup tools and registry | Reuse for factual shelter/hospital/service/resource availability; add geospatial and hazard-data tools |
| Cross-cutting | `event_engine.py`, `event_visibility.py`, `audit_service.py`, `performance.py` | Events, scoped delivery, audit records, timings | Preserve; add event types, persistence and replay semantics where needed |

### A.3 Current end-to-end incident flow

The current response workflow is:

```text
POST /incidents
  -> optional in-process background pipeline
  -> supervisor analysis and deterministic severity evaluation
  -> LangGraph specialist nodes
  -> response plan generation
  -> human approval
  -> dispatch and notifications
  -> department assignment / transport tracking
  -> monitoring, resolution, and administrative close
```

The automatic pipeline intentionally does not approve or dispatch physical
resources. Human authorization remains required for medium, high, and critical
plans.

## B. Existing reusable components

The following are directly reusable for the new system:

- `IncidentDB`, `CampusResourceDB`, `ResponsePlanDB`, `AuditLogDB`, `UserDB`,
  `DepartmentUserDB`, and the existing incident/resource identifiers.
- Exact incident latitude/longitude support and the campus location catalog in
  `backend/services/campus_locations.py`.
- `SeverityEngine` as a transparent post-report triage/scoring baseline.
- Incident duplicate/corroboration logic in `duplicate_service.py` as a base
  for multi-source observations, after its current call path is verified.
- The existing supervisor and specialist agents for active emergency response.
- LangGraph state merging, conditional delegation, instrumentation, and the
  structured-output-only realtime contract.
- MCP resource queries, especially `find_nearby_shelters`,
  `find_available_ambulances`, `find_first_aid_units`,
  `find_available_campus_vehicles`, and general resource search.
- `assignment_service.py` for department acknowledgement, team assignment,
  en-route, on-scene, and completion lifecycle.
- `dispatch_service.py` and the provider adapters for optional SMS, push,
  email, voice, and external dispatch integration.
- `notification_service.py` and `NotificationDB` for persisted, targeted
  in-app alerts.
- `road_network.py`, `transport_tracking_service.py`, `telemetry_service.py`,
  `RouteDB`, `RouteReplanDB`, and `TransportTelemetryDB` for resource movement
  and routing.
- The existing RBAC principal resolution and department scoping, with security
  hardening described under potential breaking points.
- Leaflet map lifecycle, marker/routing layers, campus catalog, and the
  transport response map.
- The current command-center shell, department portals, citizen portal,
  notification bell, voice alert controls, lazy Three.js visualization, and
  realtime reducer.
- The existing test fixtures and separate backend test suites.

## C. Existing components that need modification

### Backend

- `backend/config.py` and `.env.example`: rename the public application label;
  add forecast, sensor, geospatial, PWA sync, queue, and alert-policy settings;
  keep old variables during a transition.
- `backend/main.py`: register new routers/services and initialize only additive
  schema/seed work. Do not remove the existing lifespan behavior.
- `backend/database/models.py` and `backend/database/migrate.py`: add the
  prediction/community domain without dropping existing data.
- `backend/models/incident.py`, `resources.py`, `response.py`, `notification.py`,
  `transport.py`: add typed prediction, risk factor, facility, rescue request,
  alert acknowledgement, and offline sync contracts.
- `backend/api/incidents.py`: retain current incident endpoints and add
  optional linkage to observations, predictions, and community reports.
- `backend/api/resources.py` and `campus_locations.py`: expose proper nearby
  and category-aware discovery rather than only location-string relevance.
- `backend/api/events.py` and `event_visibility.py`: add prediction, warning,
  shelter/hospital availability, rescue-priority, and offline-reconciliation
  events without leaking internal reasoning.
- `backend/services/severity_engine.py`: leave the existing incident severity
  behavior stable; extract shared scoring primitives and do not present it as
  a forecast.
- `backend/services/response_service.py`: allow plans to originate from an
  active prediction/warning or a reported incident, while preserving existing
  response-plan fields and approval semantics.
- `backend/services/assignment_service.py` and `dispatch_service.py`: add
  rescue-request priority and urgency inputs while keeping department state
  transitions and approval gates.
- `backend/services/road_network.py`: introduce real distance/proximity and
  GeoJSON-aware helpers for the map and nearby services; retain existing route
  responses.
- `backend/services/llm_service.py`: keep LLM as an explanation/classification
  aid, not the sole source of a safety-critical prediction. Resolve the current
  provider/event-loop warnings in a contained change.
- `backend/services/notification_service.py` and adapters: add alert expiry,
  acknowledgement, deduplication, escalation, and delivery-status semantics.
- `backend/graph/state.py`, `nodes.py`, `workflow.py`, `instrumentation.py`:
  add prediction/community fields and nodes while maintaining the existing
  response graph as a compatible path.
- `backend/mcp/server.py` and `backend/mcp/tools/`: add read-only weather,
  hazard, vulnerability, facility, geospatial, and availability tools.

### Frontend

- `frontend/src/AppRoutes.tsx`, `auth/roles.ts`, and `AuthContext.tsx`: retain
  current routes and roles; add explicit admin/rescue/community capabilities
  and permission predicates rather than trusting UI-only role checks.
- `frontend/src/App.tsx`: rebrand the operator shell, add warning/prediction
  state, and keep the existing command center as an operations view.
- `frontend/src/services/api.ts` and `types/index.ts`: add typed prediction,
  map-layer, nearby facility, alert, rescue-request, and offline sync APIs.
- `frontend/src/components/CampusMap.tsx`: add vulnerability polygons/heat,
  forecast warning layers, shelters, hospitals, public services, and a clear
  distinction between exact, catalog, approximate, and stale coordinates.
- `frontend/src/pages/Dashboard.tsx`, `IncidentsPage.tsx`, `ResourcesPage.tsx`,
  and `ResponsesPage.tsx`: add early-warning and rescue-priority views while
  keeping the existing incident/approval controls.
- `frontend/src/pages/CitizenPortal.tsx`: evolve from incident-only tracking to
  community warning, safe-route, nearby shelter/hospital, and rescue-request
  functionality.
- `frontend/src/pages/DepartmentPortal.tsx`: show prediction context and
  prioritized assignments relevant to the department.
- `frontend/src/components/NotificationBell.tsx`, `PortalHeader.tsx`,
  `DepartmentVoiceAlerts.tsx`, and voice services: support warning severity,
  acknowledgement, expiry, and offline/reconnected delivery.
- `frontend/src/realtime/*`: fold new server events and reconcile missed events
  after reconnect; preserve the one-socket rule.
- `frontend/src/index.css`: rebrand and add accessible warning/risk states;
  avoid replacing the existing styling system.

## D. Components that need to be added

The following are proposed additions, not created by this audit:

### Backend additions

- `backend/agents/prediction.py`: early-warning risk inference from trusted
  observations and historical context.
- `backend/agents/vulnerability.py`: vulnerability/population/infrastructure
  overlay analysis.
- `backend/agents/resource_prioritization.py`: rescue-request ranking using
  severity, vulnerability, distance, time, and resource constraints.
- `backend/agents/alerts.py`: safe public-warning drafting and channel policy.
- `backend/services/observation_service.py`: normalize sensor, weather,
  incident, and community observations with source and freshness metadata.
- `backend/services/prediction_service.py`: model/rule execution, calibration,
  persistence, expiry, and explanation.
- `backend/services/vulnerability_service.py`: zone lookup and geospatial
  intersection.
- `backend/services/rescue_request_service.py`: intake, deduplication, queue
  priority, assignment, SLA, and status history.
- `backend/services/geospatial_service.py`: Haversine/distance, GeoJSON,
  bounding-box queries, and provider fallback.
- `backend/services/offline_sync_service.py`: idempotency keys, replay,
  conflict handling, and safe reconciliation.
- `backend/api/predictions.py`, `map_layers.py`, `facilities.py`,
  `rescue_requests.py`, `alerts.py`, and `sync.py` with additive `/api/v1`
  contracts.
- Versioned migration modules or a migration runner once the new schema is
  approved. The existing `ensure_schema` can remain as a compatibility bridge.

### Frontend additions

- `frontend/src/pages/PredictionDashboard.tsx` for administrators/rescue
  coordinators.
- `frontend/src/pages/CommunitySafetyPage.tsx` or an expanded citizen portal.
- `frontend/src/components/RiskPredictionPanel.tsx`,
  `VulnerabilityLayerLegend.tsx`, `NearbyFacilitiesPanel.tsx`,
  `RescuePriorityQueue.tsx`, `WarningBanner.tsx`, and `OfflineStatus.tsx`.
- `frontend/src/services/offlineStore.ts` using IndexedDB (or a small,
  well-supported wrapper) for cached snapshots and queued submissions.
- `frontend/public/manifest.webmanifest` and a service-worker entry, using a
  Vite-compatible PWA approach only if it can be introduced without changing
  the existing app build.
- Focused frontend tests for the new reducer events, cache/sync semantics,
  map layer visibility, and permission presentation.

## E. Components that should remain unchanged

Keep these stable unless a test demonstrates a necessary compatibility fix:

- The existing `/api/v1` URL namespace and current request/response shapes.
- Incident IDs, resource IDs, plan IDs, and existing lifecycle status values.
- The existing approval rule: high-impact actions require an authenticated
  human decision before physical dispatch.
- Password/token response shape and current authentication flows during the
  migration window.
- Existing department assignment states and transport tracking payloads.
- Provider adapters' no-provider fallback behavior and secrets-free status
  reporting.
- `frontend/package-lock.json` except for explicitly approved additive
  dependencies.
- Existing tests and fixtures; update assertions only when an intentional,
  documented contract changes.
- Existing simulation and digital-twin controls, but label them as simulation
  and never use them as production prediction evidence.
- Existing audit logging and structured realtime output rules. Do not expose
  prompts, chain-of-thought, or hidden model reasoning.

## F. Database migration plan

### F.1 Current schema findings

`backend/database/models.py` defines these 17 tables:

1. `incidents`
2. `campus_resources`
3. `response_plans`
4. `audit_logs`
5. `users`
6. `department_users`
7. `incident_status_history`
8. `agent_runs`
9. `agent_events`
10. `department_responses`
11. `resource_assignments`
12. `routes`
13. `route_replans`
14. `transport_telemetry`
15. `road_conditions`
16. `notifications`
17. `chat_messages`

The first six are core records. Department responses, resource assignments,
routes, route replans, transport telemetry, road conditions, notifications,
and chat are now wired by current services/tests. `incident_status_history`,
`agent_runs`, and `agent_events` are declared but are not currently populated
by application services; they should not be assumed to be historical source of
truth.

There is no dedicated risk prediction, observation, vulnerability-zone,
community rescue request, or alert-subscription table. Approval state is stored
on `response_plans`; dispatch state is represented by assignments/resources.

### F.2 Additive target schema

Prefer new tables to overloading the existing incident contract:

- `hazard_observations`: source, observation type, timestamp, freshness,
  coordinates/zone, value/payload, quality, and provenance.
- `risk_predictions`: prediction ID, hazard/category, score, level, confidence,
  affected geometry/zone, model/version, factor JSON, issued/valid/expired
  timestamps, source observation IDs, and review status.
- `vulnerability_zones`: zone geometry or canonical zone ID, population,
  vulnerable-group indicators, critical infrastructure, shelter capacity, and
  data freshness.
- `response_facilities` or an additive facility classification: hospitals,
  clinics, shelters, fire stations, police/security, and public emergency
  services. Existing campus resources can remain the dispatch inventory.
- `rescue_requests`: reporter/user, coordinates, description, risk context,
  priority score, priority rationale, status, assigned department/resource,
  timestamps, and idempotency key.
- `alert_campaigns` / `alert_deliveries`: warning version, audience/zone,
  channels, expiry, acknowledgement, delivery result, and deduplication key.
- `offline_sync_operations`: client operation ID, actor, operation type,
  payload hash, received/applied/conflict status, and timestamps.

Add foreign-key/index relationships where supported, but keep SQLite-compatible
types initially. Store geometry as validated GeoJSON/text first; migration to a
spatial extension is optional and should not be a framework migration.

### F.3 Migration safety

- Take a verified backup of `campusflow.db` before production migration.
- Keep `Base.metadata.create_all` for new development tables only while adding
  a versioned migration path for production.
- Make every migration additive and idempotent; never drop/rename existing
  columns in the first release.
- Add indexes for timestamps, zone IDs, hazard types, status, priority, and
  latitude/longitude or spatial-provider keys.
- Backfill existing incidents into observations only as `historical_incident`
  records, never as fabricated sensor readings.
- Backfill existing shelters/resources with a verified facility category;
  create hospital records only from an authoritative inventory.
- Record schema version and migration outcome in deployment logs/audit metadata.
- Verify both SQLite and PostgreSQL dialects before switching production.

## G. Agent migration plan

### G.1 Existing agents mapped to the new system

| Existing agent | Reuse in new problem | Required change |
|---|---|---|
| Supervisor | Intake normalization, event correlation, incident triage | Add observation confidence/provenance; stop treating post-incident severity as forecast risk |
| Medical | Triage, nearby medical response, hospital/clinic readiness | Add hospital capacity and vulnerable-person prioritization |
| Security | Perimeter, safety, crowd/security response | Add zone warning and public safety boundary support |
| Transport | Evacuation, safe routes, vehicle movement | Add forecast-aware route closures and community safe-route recommendations |
| Communication | Broadcast drafting and channel selection | Add early-warning templates, audience zones, expiry, acknowledgement, and delivery fallback |
| Fire | Fire/hazard response | Add fire-risk observation interpretation, with deterministic safeguards |
| Facilities | Utility/structural response | Add infrastructure vulnerability and hazard-source context |
| Synthesizer | Unified response plan | Include prediction, vulnerability, nearby facilities, rescue queue, and approval requirements |

### G.2 New agent responsibilities

1. Observation/Signal Agent validates source, timestamp, quality, and duplicate
   status.
2. Risk Prediction Agent produces a calibrated score and level with factors,
   horizon, affected area, confidence, and model version.
3. Vulnerability Agent intersects the predicted area with people, buildings,
   critical services, shelters, and accessibility constraints.
4. Resource Prioritization Agent ranks rescue requests and recommends nearby
   resources using deterministic tie-breakers.
5. Community Alert Agent drafts a plain-language warning that clearly separates
   forecast, uncertainty, protective action, and source time.

LLMs may assist with classification and explanation, but numeric risk scores,
geospatial selection, thresholds, and dispatch authorization must be produced
by deterministic or validated model services. Every prediction must retain its
inputs and model version so it can be audited and evaluated.

## H. LangGraph migration plan

Preserve the current response graph and add a new mode/subgraph rather than
rewriting the working workflow.

### H.1 Proposed graph

```text
START
  -> ingest_observation
  -> normalize_and_validate
  -> deduplicate_and_correlate
  -> predict_risk
  -> overlay_vulnerability
  -> discover_nearby_facilities_and_resources
  -> prioritize_rescue_requests
  -> draft_warning_and_response_options
  -> policy_gate
       -> low/no action: publish advisory + monitor
       -> warning: publish targeted alert + monitor
       -> active emergency: existing emergency response subgraph
       -> physical dispatch: existing human approval gate
  -> monitor/replan
  -> END
```

The `EmergencyGraphState` should gain additive fields for observation IDs,
prediction, risk factors, affected geometry, vulnerability summary, nearby
facilities, prioritized requests, alert drafts, expiry, and data freshness.
Existing fields and specialist result keys remain valid.

The existing `instrument_node` wrapper and event engine should instrument all
new nodes with structured summaries only. Add prediction lifecycle events such
as `prediction_started`, `prediction_completed`, `warning_issued`,
`prediction_expired`, and `rescue_priority_updated` to the existing socket.

The current in-process `BackgroundTasks` pipeline is acceptable for a first
increment, but it is not durable across process restarts and can race explicit
analysis calls. Before production-critical forecasting, isolate jobs with
idempotency and a durable worker/queue only if operational evidence requires
it; do not migrate frameworks solely for naming.

## I. API migration plan

### I.1 Existing contracts to preserve

Current router contracts include:

- Auth: `/api/v1/auth/login`, `/signup`, `/user/register`, `/user/login`,
  `/department/login`, `/department/register`, `/me`.
- Incidents: create/list/get, `/analyze`, `/analyze-raw`, `/orchestrate`,
  `/confirm-response`, `/close`.
- Resources: list, available search, resource-by-ID.
- Response/approval/dispatch: response-plan generation/list/get, pending
  approvals, approval decision, dispatch execution, resolve.
- Department workflow: incident assignments, portal assignments, accept,
  decline, team assignment, en-route, on-scene, completed.
- Realtime: `/api/v1/events/ws`.
- Map/transport: campus locations, route calculation, road conditions,
  telemetry, GPS status, transport tracking.
- Notifications, activity/audit, chat, voice, system status, and simulation.

Do not rename or remove these in the first migration. Add new fields as
optional, and add new endpoints under `/api/v1`.

### I.2 Proposed additive endpoints

- `POST /api/v1/observations` and `GET /api/v1/observations`
- `POST /api/v1/predictions/evaluate`
- `GET /api/v1/predictions`, `GET /api/v1/predictions/{prediction_id}`
- `GET /api/v1/map/layers/vulnerability`
- `GET /api/v1/map/layers/risk`
- `GET /api/v1/facilities/nearby?lat=&lng=&type=&radius_m=`
- `GET /api/v1/resources/nearby?...` (preserve existing resource search)
- `POST /api/v1/rescue-requests`, `GET /api/v1/rescue-requests`,
  `POST /api/v1/rescue-requests/{id}/prioritize`,
  `POST /api/v1/rescue-requests/{id}/assign`
- `GET /api/v1/alerts`, `POST /api/v1/alerts/{id}/acknowledge`
- `POST /api/v1/sync/operations`, `GET /api/v1/sync/status`

All endpoints must enforce server-side scope. Public community endpoints must
return only public-safe warning data; internal prediction factors, personnel,
resource IDs, and audit details remain restricted.

## J. Frontend migration plan

### J.1 Preserve the existing shells

Keep `/command`, `/portal`, `/dept/:department`, login/signup, the shared API
client, auth bootstrap, and existing portal assignment flows. Rebrand visible
labels from CampusFlow AI/Campus Emergency Command Center to the new product
name through centralized constants where practical.

### J.2 New administrator/rescue dashboard

Extend the existing privileged dashboard with:

- current risk level and forecast horizon;
- prediction confidence, freshness, model version, and top contributing
  factors;
- vulnerability impact summary;
- map layer controls;
- nearby shelter/hospital/emergency-service cards;
- rescue request queue sorted by server-provided priority and SLA;
- alert campaign status and acknowledgement/delivery summary;
- existing incident command, approvals, assignments, dispatch, and audit panels.

Do not imply that a simulated vehicle or a stale prediction is live.

### J.3 Community experience

Add to the citizen portal:

- active warnings for the member's current/selected area;
- plain-language protective actions and uncertainty/source time;
- nearby shelters, hospitals, and emergency services with distance, status,
  capacity, accessibility, and directions;
- one-tap rescue request with location, urgency, accessibility/medical needs,
  and offline queue state;
- safe cached information when connectivity is lost.

Keep the existing own-incident scoping. A citizen must never receive another
citizen's incident, internal agent output, or privileged resource assignment.

## K. Map/geospatial plan

The current `CampusMap` is a working Leaflet map with multiple base layers,
incident/resource/catalog markers, route polylines, and live transport markers.
It currently uses exact coordinates when available, campus catalog aliases next,
and approximate hardcoded coordinates as a final fallback. MCP location sorting
is primarily string relevance, not true distance.

Migration steps:

1. Preserve Leaflet, its lifecycle, and existing base-layer controls.
2. Add GeoJSON vulnerability zones with severity/risk coloring and a legend.
3. Add risk forecast footprints, timestamp/freshness, and expiry state.
4. Add explicit shelter, hospital/clinic, fire, police/security, ambulance,
   and public-service layers. Use verified records only.
5. Add Haversine/provider-backed distance and ETA; expose source and accuracy.
6. Keep exact/catalog/approximate coordinate provenance visible.
7. Keep transport route and road-condition overlays compatible with the current
   route event payloads.
8. Design offline map behavior around cached vector summaries and selected tiles;
   do not blindly cache third-party tiles without checking provider/license
   terms. Show a stale-map warning when tiles/data cannot refresh.
9. Add bounds/radius validation so a community user cannot request arbitrary
   server-wide sensitive data.

## L. Risk prediction plan

The current `SeverityEngine` is an auditable incident severity classifier. It
uses incident type, location sensitivity, casualty signals, hazard keywords,
and corroboration. It is valuable, but it is post-report triage and must not be
renamed as a prediction engine.

### L.1 Prediction inputs

Use only available, timestamped, provenance-labeled sources:

- weather/rainfall/heat/wind and other authoritative hazard feeds;
- smoke/fire/water/utility or campus sensor readings when integrated;
- historical incident density and recency;
- community reports and corroboration clusters;
- building occupancy, critical infrastructure, road conditions, and resource
  availability;
- vulnerability zones, accessibility needs, and shelter/hospital capacity.

### L.2 Output requirements

Every prediction should contain:

- hazard type and affected zone/geometry;
- score, level, confidence, forecast horizon, issued time, and expiry;
- source observations and freshness;
- model/rule version;
- human-readable factors and recommended protective actions;
- review/override state and authenticated reviewer when applicable.

Use calibrated thresholds with a conservative `unknown/insufficient data`
state. Never convert missing data to a safe/zero-risk claim. Expire predictions
automatically by data validity, not by a frontend timer. Critical warnings need
policy review/escalation and a clear audit trail.

### L.3 Evaluation

Create historical replay fixtures for fire, flood/waterlogging, extreme heat,
crowd, security, and no-event periods. Track false negatives, false positives,
calibration, lead time, stale-data rate, alert acknowledgement, and rescue
prioritization fairness. Keep model evaluation separate from LLM prose quality.

## M. Offline/low-connectivity plan

The current frontend has polling, WebSocket reconnect, localStorage auth, and
truthful offline UI labels, but no service worker, manifest, IndexedDB cache,
queued writes, or background sync.

Implement in this order:

1. Add a manifest and service worker for the app shell and static assets.
2. Cache the last safe public warning snapshot, risk summary, facility list,
   campus catalog, and selected map/vector data in IndexedDB with timestamps.
3. Add an explicit online/offline/reconnecting indicator and stale-data labels.
4. Queue citizen rescue requests and incident reports with a client-generated
   idempotency key; never show them as server-accepted until acknowledged.
5. On reconnect, replay operations through `/api/v1/sync/operations`, with
   server-side authentication, deduplication, validation, conflict status, and
   audit logging.
6. Preserve the existing WebSocket as the live path; after reconnect, request a
   snapshot/delta from the server so missed events are reconciled.
7. Keep emergency fallback instructions and configurable SMS/voice paths
   visible when the app cannot deliver a network request.
8. Never present cached predictions, shelter availability, GPS, or alerts as
   current. Display age, expiry, and source.

This can be implemented within React/Vite. A PWA plugin or IndexedDB helper is
acceptable only after confirming it does not destabilize the current build.

## N. Testing plan

### N.1 Protect the current baseline

- Keep `backend/tests` isolated from production using its temporary database
  fixture and `ALLOW_ANONYMOUS_ADMIN=false`.
- Keep the root legacy suite separate because its fixtures/configuration use
  compatibility behavior.
- Resolve or explicitly quarantine the current automatic-background-pipeline
  race so the expected incident contract is unambiguous.
- Fix/track the Gemini grpc event-loop warnings and provider deprecation before
  relying on external LLM calls in tests.
- Continue frontend strict TypeScript build and Vitest runs.

### N.2 New backend coverage

- observation validation, source freshness, duplicate/corroboration behavior;
- deterministic risk thresholds, missing data, expiry, calibration metadata,
  and model-version persistence;
- vulnerability/geospatial intersection and radius/distance correctness;
- nearby shelter/hospital/service filtering and scope;
- rescue priority ordering, tie-breakers, reassignment, and audit history;
- alert deduplication, expiry, audience scoping, provider fallback, and
  acknowledgement;
- prediction-to-incident response handoff and existing approval gate;
- WebSocket event ordering, reconnect snapshots, replay/idempotency, and role
  visibility;
- SQLite migration from a representative existing database and PostgreSQL
  migration/queries if PostgreSQL is selected for deployment;
- offline sync duplicate, conflict, expired-warning, unauthorized, and partial
  failure cases.

### N.3 New frontend coverage

- reducer handling for prediction/warning/rescue events;
- risk panel freshness/expiry and uncertainty display;
- map layer toggles, marker provenance, nearby sorting, and no-coordinate states;
- role/department rendering and forbidden data absence;
- IndexedDB queue/replay/conflict UI;
- service-worker app-shell behavior where browser test tooling permits;
- accessibility: keyboard use, contrast, live-region alert behavior, and
  screen-reader warning text;
- end-to-end flow: prediction -> warning -> rescue request -> prioritization ->
  assignment -> approved response -> notification.

## O. Deployment plan

### O.1 Current deployment reality

The repository contains no Docker, Render, Procfile, CI/CD, or hosting
manifests. Local startup is documented in `README.md` as Uvicorn for the
backend and Vite for the frontend. `frontend/dist` exists locally but is an
ignored build output, not a deployment contract.

### O.2 Recommended additive deployment work

After local migration tests pass, add the minimum manifests required by the
chosen existing host, for example:

- `Dockerfile.backend` or a host-specific backend start command;
- `frontend/Dockerfile` or static-host build configuration;
- `render.yaml` only if Render remains the target;
- health/readiness configuration using `/health`;
- production CORS, HTTPS WebSocket (`wss`), trusted origins, and proxy timeout
  settings;
- persistent database storage and backup/restore procedure;
- a durable worker/queue only when prediction/alert volume justifies it;
- CI steps for backend tests, frontend tests, frontend build, migration check,
  secret scanning, and smoke tests.

Do not add these manifests until the deployment target is confirmed. Keep all
credentials in the host secret manager. The local `.env` must not be copied to
images or committed artifacts; rotate any real credential-shaped values found
there.

### O.3 Production rollout

1. Deploy the renamed UI with existing APIs unchanged.
2. Apply additive schema migrations and verify backups.
3. Enable observation ingestion in shadow mode.
4. Run prediction in shadow mode and compare against reviewed incidents.
5. Enable administrator/rescue dashboard and internal alerts.
6. Enable community warnings for one zone/audience, with rate limits and
   rollback controls.
7. Enable rescue-request prioritization with human review and audit.
8. Enable offline queue/replay after sync and conflict monitoring are proven.
9. Measure lead time, delivery, false alerts, stale data, and resource SLAs.

## Requirement verification matrix

| Requirement | Existing coverage | Planned completion criteria |
|---|---|---|
| 1. Risk prediction / early warning | No dedicated prediction model/table/API; current severity is post-incident | Timestamped, expiring, calibrated prediction records with source/factors, admin review, realtime warning events, and public-safe summaries |
| 2. Interactive vulnerability map | Working Leaflet map, campus catalog, incident/resource/route markers; no vulnerability layer | GeoJSON vulnerability/risk layers, legend, filters, provenance, freshness, and offline-safe cached summaries |
| 3. Nearby shelters | Seeded shelter resources and MCP shelter lookup; no true radius API | Verified facility records, distance/capacity/accessibility/status, public and responder-scoped nearby endpoint/UI |
| 4. Nearby hospitals | No clearly seeded hospital inventory; medical center/resource enum exists | Verified hospital/clinic facility catalog, capacity/status/distance, map and community panel |
| 5. Emergency services/resources | Seeded ambulances, security, first aid, vehicles, fire/facility teams; assignment/dispatch wired | Unified typed service catalog and true geospatial availability, preserving existing dispatch resource contracts |
| 6. Realtime notifications and alerts | Event engine, scoped WebSocket, persisted notifications, optional provider adapters, browser voice | Prediction/warning/rescue events, alert campaigns, acknowledgement/expiry, reconnect reconciliation, and provider delivery status |
| 7. Administrator/rescue dashboard | Privileged command center and department portals; admin/operator share `/command` | Explicit capability-based admin/rescue dashboard with prediction, vulnerability, facilities, alert, and queue views plus existing operations |
| 8. Rescue request prioritization | Incident intake and department assignments exist; no dedicated community rescue queue/priority model | Server-owned priority score/rationale, vulnerability/SLA factors, queue, assignment, requeue, audit, and human override |
| 9. Offline/low-connectivity functionality | Polling/reconnect/localStorage only; no PWA/offline write queue | Installable app shell, cached safe data with age/expiry, queued idempotent reports/rescue requests, reconnect sync, and truthful stale/offline UX |

## Component mapping to the new problem statement

| Existing component | New role | Keep/modify/add |
|---|---|---|
| `IncidentDB` and incident APIs | Confirmed community reports and active emergencies | Keep contract; add optional prediction/observation links |
| `CampusResourceDB` + MCP tools | Shelters, hospitals/clinics when verified, ambulances, security, transport, fire/facilities | Keep; add facility classification and geospatial discovery |
| `SeverityEngine` | Transparent active-incident triage | Keep as a separate post-report signal |
| LangGraph supervisor/specialists | Response coordination after a warning/report | Keep as subgraph; add prediction/alert/prioritization stages |
| `EventEngine` + WebSocket | Live risk, alert, assignment, dispatch, and status updates | Keep one bus/socket; add event types and replay/snapshot support |
| `NotificationDB` + adapters | Public-safe warnings and responder/admin notifications | Extend with campaign/delivery/expiry semantics |
| `DepartmentResponseDB` | Rescue/responder handoff lifecycle | Reuse; add priority/SLA context |
| `ResourceAssignmentDB` | Physical resource assignment | Reuse; retain approval/dispatch constraints |
| `RoadNetwork`/Leaflet | Vulnerability, risk, services, safe-route, and response map | Extend; preserve existing routes and coordinate provenance |
| `Telemetry`/transport tracking | Responder/resource live location | Keep; never use stale GPS as current community location |
| RBAC/auth | Admin, rescue, department, citizen, and public-safe access | Keep token shape; harden default authorization and scopes |
| React command center | Administrator/rescue operations dashboard | Extend/rebrand |
| React citizen portal | Community warning and assistance experience | Extend with nearby services, rescue request, and offline support |
| Three.js command center | Optional internal agent/workflow visualization | Preserve as internal enhancement; do not make prediction depend on it |
| Simulation endpoints/UI | Testing/training only | Preserve but label and isolate from production prediction evidence |

## Files to modify in the implementation phase

This is a future change list; none of these files were modified by this audit.

### Existing backend files

`backend/config.py`, `backend/main.py`, `backend/database/models.py`,
`backend/database/migrate.py`, `backend/database/seed.py`,
`backend/models/incident.py`, `backend/models/resources.py`,
`backend/models/response.py`, `backend/models/notification.py`,
`backend/models/transport.py`, `backend/api/incidents.py`,
`backend/api/resources.py`, `backend/api/events.py`,
`backend/services/event_visibility.py`, `backend/api/responses.py`,
`backend/api/dispatch.py`, `backend/api/notifications.py`,
`backend/api/assignments.py`, `backend/api/system.py`,
`backend/services/llm_service.py`, `backend/services/severity_engine.py`,
`backend/services/response_service.py`, `backend/services/assignment_service.py`,
`backend/services/dispatch_service.py`, `backend/services/notification_service.py`,
`backend/services/road_network.py`, `backend/services/transport_tracking_service.py`,
`backend/graph/state.py`, `backend/graph/nodes.py`,
`backend/graph/workflow.py`, `backend/graph/instrumentation.py`,
`backend/mcp/server.py`, and relevant `backend/mcp/tools/*.py`.

### Existing frontend files

`frontend/src/App.tsx`, `frontend/src/AppRoutes.tsx`,
`frontend/src/auth/AuthContext.tsx`, `frontend/src/auth/roles.ts`,
`frontend/src/services/api.ts`, `frontend/src/types/index.ts`,
`frontend/src/realtime/RealtimeWorkflowProvider.tsx`,
`frontend/src/realtime/workflowReducer.ts`,
`frontend/src/components/CampusMap.tsx`, `LocationPicker.tsx`,
`NotificationBell.tsx`, `PortalHeader.tsx`, `DepartmentVoiceAlerts.tsx`,
`RealOperationsControls.tsx`, `IncidentCommandView.tsx`,
`frontend/src/pages/Dashboard.tsx`, `IncidentsPage.tsx`, `ResourcesPage.tsx`,
`ResponsesPage.tsx`, `CitizenPortal.tsx`, `DepartmentPortal.tsx`,
`DepartmentManagementPage.tsx`, and `frontend/src/index.css`.

### Configuration/deployment files, when the target is confirmed

`.env.example`, `backend/requirements.txt`, `frontend/package.json`,
`frontend/package-lock.json`, `frontend/vite.config.ts`, plus the selected
host/Docker/CI manifests that do not currently exist.

## Files to create in the implementation phase

Proposed additions are:

- Backend prediction/observation/vulnerability/geospatial/alert/rescue/sync
  services and agents listed in sections D and G.
- New additive API routers: `predictions.py`, `map_layers.py`, `facilities.py`,
  `rescue_requests.py`, `alerts.py`, and `sync.py`.
- New Pydantic models for prediction, observations, facilities, alerts, rescue
  requests, and synchronization.
- Versioned additive database migration files and migration tests.
- Frontend prediction/risk/map-layer/facility/queue/warning/offline components,
  `offlineStore.ts`, service-worker entry, and web manifest.
- New backend and frontend tests described in section N.
- Deployment manifests only after the hosting target is explicitly selected.

## Files/directories to preserve

Preserve the working implementation and contracts in:

- `backend/agents/` existing response agents;
- `backend/api/` existing routers and route paths;
- `backend/database/` existing records, IDs, and additive migration behavior;
- `backend/graph/` existing response graph and instrumentation;
- `backend/mcp/` existing factual resource tools;
- `backend/services/` existing auth, response, dispatch, assignment,
  notification, routing, telemetry, and provider adapters;
- `backend/tests/` and `tests/` existing suites and fixtures;
- `frontend/src/auth/`, current route shells, current command center, citizen
  and department portals, Leaflet/transport map, realtime reducer, voice
  controls, and existing UI tests;
- `frontend/package.json`, lockfile, Vite/TypeScript configuration, and the
  current build approach;
- existing optional simulation functionality, clearly separated from live
  prediction and operations.

## Potential breaking points

1. The current root legacy suite has one timing-sensitive failure caused by the
   automatic background pipeline. Changing pipeline timing can affect deployed
   behavior and must be isolated/tested.
2. `ALLOW_ANONYMOUS_ADMIN` defaults to `True`, so command endpoints are open to
   unauthenticated callers unless deployment overrides it. Turning it off is
   the correct production posture but will break the legacy no-login console.
3. Approval pending and activity endpoints are not uniformly protected like
   command mutation endpoints. Audit their read scopes before exposing
   prediction/rescue data.
4. WebSocket tokens are passed in a query string, which can appear in proxy
   logs. Preserve compatibility initially, then evaluate a safer handshake or
   short-lived socket token.
5. `CampusMap.tsx` and some portals construct WebSocket URLs differently from
   the shared `VITE_API_BASE_URL` helper. This can break deployments not using
   port 8000.
6. Leaflet currently depends on external tile providers; offline support and
   provider licensing/caching need an explicit strategy.
7. Approximate coordinates and string-based resource relevance can mislead
   nearby-service decisions. True distance and coordinate provenance are
   required before community navigation is enabled.
8. Hospitals are not clearly represented in the seeded resource inventory.
   Do not infer a hospital from an ambulance or generic medical center.
9. LLM-backed agent paths can return before MCP resource lookup, so configured
   provider paths may lack factual resource grounding. Resource discovery must
   be deterministic and independent of LLM availability.
10. In-process background tasks and in-memory event/traces do not survive a
    process restart or multiple replicas. Durable jobs/event replay are needed
    when early warnings become production-critical.
11. Existing agent lifecycle events are broadcast-only and agent execution
    tables are not populated. Historical prediction/agent reconstruction needs
    explicit persistence.
12. The custom token/password implementation and default secrets are legacy
    compatibility concerns. Harden them in a separately tested security change,
    not inside a broad feature rewrite.
13. Direct external provider integrations can produce side effects. Keep test
    destinations, feature flags, rate limits, and explicit operator controls.
14. `frontend/dist` is ignored build output and is not a deployment guarantee.
    A host-specific build/start contract must be added only after target
    selection.

## Recommended implementation order

1. Freeze current API/schema contracts and resolve the existing legacy test
   race; record the four baseline commands and warning inventory.
2. Decide security posture, deployment target, authoritative hazard/facility
   data sources, prediction ownership, and public warning policy.
3. Add additive schema/versioning, observation provenance, facility catalog,
   prediction records, and migration/backup tests.
4. Implement deterministic geospatial distance, vulnerability zones, nearby
   shelters/hospitals/services, and coordinate provenance.
5. Add prediction service/agent in shadow mode with model/version/freshness,
   explainability, expiry, and evaluation fixtures.
6. Extend LangGraph with prediction, vulnerability, resource-prioritization,
   and alert nodes while retaining the existing response subgraph and approval
   gate.
7. Add additive APIs and scoped realtime event contracts; persist lifecycle,
   alert, and rescue audit/state as needed for restart/replay.
8. Extend the privileged administrator/rescue dashboard and map layers.
9. Extend the community portal with warnings, nearby facilities, rescue
   requests, and safe public data boundaries.
10. Add PWA shell/cache, stale-data indicators, offline queue, idempotent sync,
    reconnect snapshot/delta reconciliation, and tests.
11. Add deployment/CI manifests for the selected host, secret management,
    backups, readiness checks, observability, and rollback.
12. Roll out shadow -> internal -> one-zone community warnings -> broader
    community response, with measurable rollback gates at every stage.

The migration is complete only when all nine requirements in the matrix are
demonstrated through authenticated API tests, frontend tests/build, map and
offline browser checks, and a staged deployment smoke test. 
