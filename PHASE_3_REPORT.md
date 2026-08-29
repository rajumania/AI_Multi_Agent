# Phase 3 Report — Multi-Agent Disaster Intelligence and Continuous Monitoring

## Scope and status

Phase 3 is implemented on top of the existing FastAPI, SQLAlchemy, React, authentication/RBAC, WebSocket and LangGraph architecture. Phase 2 risk prediction remains the source of numerical risk scores. This phase adds converging human and sensor triggers, conditional specialist fan-out, operational coordination, travel safety, monitoring/re-planning and audit coverage.

This prototype provides decision-support risk estimation and is not an authoritative disaster forecasting system.

## Agent architecture

`backend/graph/disaster_workflow.py` defines a strongly typed `DisasterIntelligenceState`. The Supervisor conditionally selects specialists and uses LangGraph `Send` for parallel independent analysis. Resource coordination, deterministic priority calculation, safe routing, response planning, approval, monitoring and recovery then run sequentially because each stage consumes the previous stage's state.

The existing incident workflow and agents are preserved. Phase 3 maps them as follows:

- Medical → medical emergency and hospital coordination
- Security → public safety and access-control recommendations
- Transport → emergency transport context
- Facilities → infrastructure and utilities context
- Communication → approved disaster/community communications
- Supervisor/orchestrator → Incident Commander and conditional specialist router

The complete diagram is in [AGENT_ARCHITECTURE.md](AGENT_ARCHITECTURE.md).

## Sensor and event architecture

`SensorMonitoringService` normalizes rainfall, river/water level, soil moisture, ground movement/tilt, temperature and wind readings. `SensorAnomalyDetector` applies validated thresholds and rise detection. Observations are stored in `sensor_observations`; anomalies are stored in `sensor_events`, mirrored into the Phase 2 weather/environment observations where applicable, published through the existing WebSocket event engine, and audited.

`DEMO_SIMULATION` is the deterministic provider/source label. No simulated hardware reading is presented as live data. Sensor anomalies and human/community reports both converge through `trigger_disaster_intelligence()` into the same risk prediction and LangGraph workflow.

## Deterministic tools and coordination

- `priority_engine.py` calculates bounded rescue priority from people count, injuries, children, elderly people, medical emergency, hazard/risk, waiting time and accessibility.
- `resource_coordination.py` queries real database resources, shelters and hospitals; agents do not hard-code availability.
- `safe_routing.py` uses the existing verified road graph only for known geometry and explicitly returns `route_unavailable` where geometry is not available.
- `travel_safety.py` combines the latest persisted risk, weather and active alerts and returns `SAFE`, `CAUTION`, `NOT_RECOMMENDED` or `CRITICAL` with reasons.
- Response plans use the existing `ResponsePlanDB` and remain `pending` until the existing human approval workflow authorizes high-impact actions.

## Nepal Mountain demonstration

`POST /api/v1/sensor-simulations` with `{"scenario":"nepal_mountain"}` inserts clearly labelled simulated readings for DEMO N-14: 3,400 m elevation, high slope/terrain vulnerability, 180 mm rainfall, 92% soil moisture, rising river level and ground movement. The same Phase 2 engine evaluates both flood and landslide hazards; the final score is not hard-coded. The critical path creates an administrative early-warning recommendation, a community-targeted warning with cooldown protection, an approval-gated response plan and an auditable agent run. Re-planning creates a new approval-gated plan after conditions change.

Other deterministic scenarios: `urban_flood`, `cyclone` and `heatwave`.

## Workflows

### Administrative

The admin/operator can submit a disaster event or sensor reading, inspect risk and agent results, view the trace, review resources and the pending response plan, and use the existing approval controls before dispatch. Critical conditions are represented as queued/simulated administrative/community notifications; no external department is claimed to have been contacted.

### Community

Community text and rescue reports create an existing-compatible incident and rescue request, add validated community signals to environmental observations, run the same deterministic risk pipeline, and create a geographic zone-targeted notification for critical conditions. Nearby alerts are exposed only for the requested zone/location.

### Tourist

The new Travel Safety page calls the backend safety-check endpoint. It presents current risk, hazards, active warnings, weather summary, route status, recommendation and reasons. It uses cautious language and does not claim certainty about future conditions.

## Approval, monitoring and audit

High-impact actions—public warnings, evacuation recommendations, dispatch, resource deployment and access restrictions—remain approval-gated. Monitoring records that weather, sensors, resources, routes, shelters, hospitals and reports should be observed; the re-plan endpoint reruns the same pipeline with `replan=true` and produces a new approval-gated plan. Sensor ingestion, agent execution, resource/priority calculations, plans, approval-required events, alerts and re-planning are recorded through the existing audit/event systems.

## APIs

All routes use the existing `/api/v1` namespace:

- `POST /events`
- `POST /sensor-events`, `GET /sensors`, `GET /sensors/status`, `GET /sensor-events`
- `POST /sensor-simulations`
- `GET /departments`, `GET /departments/{id}`
- `GET /agent-runs/{id}`, `GET /agent-runs/{id}/trace`
- `GET /alerts/nearby`
- `POST /monitoring/replan/{event_id}`
- `POST/GET /travel/safety-check`

Existing Phase 2 risk and weather/environment endpoints remain available. Existing WebSocket infrastructure now carries `SENSOR_UPDATE`, `ENVIRONMENT_ANOMALY`, `DISASTER_DETECTED`, `COMMUNITY_ALERT`, `RESPONSE_PLAN_UPDATED`, `APPROVAL_REQUIRED`, `REPLAN_TRIGGERED`, and related risk/resource/travel events.

## Tests and validation

- Backend: **107 passed** (`backend/tests`), including Phase 3 sensor, convergence, Nepal, travel, priority, resource, routing and API coverage.
- Frontend: **92 passed**.
- Frontend production build: **successful**.
- Legacy suite: **52 passed, 1 skipped, 1 known timing-related failure**, unchanged in `tests/test_supervisor_agent.py::test_api_analyze_incident_by_id`; it is caused by existing background/async Gemini cleanup timing and was not hidden or weakened.
- Python backend compilation: successful.
- Application import and graph initialization: successful; existing and Phase 3 graphs both initialize.

## Known limitations and next phase

- External IoT hardware, advanced GIS layers, route geometry outside the existing verified local graph, complete PWA/offline caching and production notification integrations are not implemented in Phase 3.
- The current demo/provider fallback remains explicitly labelled and should be replaced or supplemented with configured trusted providers before operational use.
- The existing Google Generative AI package emits a deprecation warning; it was not changed because framework/provider migration is outside this phase.
- The Vite bundle retains the existing large-chunk warning; the build is successful.

Phase 4 should consume the persisted risk, sensor, event, resource and alert interfaces to implement the complete interactive vulnerability map. Offline/PWA and final deployment changes remain later-phase work.
