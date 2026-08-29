# Phase 9A — Real External Data Providers

## Status

Phase 9A is complete for the provider-integration scope. The existing
FastAPI, React/Vite, LangGraph, SQLite, deterministic risk, GIS, WebSocket,
offline, and PWA architecture was retained.

## 1. Providers integrated

- **Weather:** Open-Meteo current weather adapter using latitude/longitude.
  The adapter normalizes temperature, humidity, precipitation/rain, wind,
  pressure, weather code, timestamps, source, status, and freshness. The
  boundary follows the Open-Meteo forecast API contract: [Open-Meteo API documentation](https://open-meteo.com/en/docs).
- **Environment:** Open-Meteo values are exposed as the existing normalized
  environmental indicators; the deterministic environmental provider remains
  the explicit fallback.
- **Routing:** OSRM route adapter using GeoJSON geometry and turn steps. Its
  output is passed through the existing hazard-aware safe-routing service;
  provider geometry alone cannot make a route safe. Reference: [OSRM API](https://project-osrm.org/docs/v5.24.0/api/).
- **Earthquakes:** USGS FDSN GeoJSON adapter with magnitude, time, radius,
  lookback, and event-type filtering. Events are normalized and can be
  assessed through the existing disaster-intelligence pipeline; they do not
  automatically create disasters. Reference: [USGS FDSN event service](https://earthquake.usgs.gov/fdsnws/event/1/wsdl).
- **Sensors:** A normalized HTTP/IoT gateway boundary was added. No physical
  IoT device is claimed or connected; the existing demo provider remains the
  controlled development scenario.

## 2. Provider contract and failure handling

All external adapters have bounded timeouts, configurable retries with
backoff, response validation, structured provider logging, and provider
health telemetry. Health records contain provider, status, last success/failure,
latency, failure count, freshness, and source only; credentials and response
bodies are never recorded.

Observation source/status values are explicit: `OPEN_METEO`, `USGS`, `OSRM`,
`IOT`, `DEMO`, `DEMO_FALLBACK`, and `LIVE`, `STALE`, `FALLBACK`, or `OFFLINE`.
Stale data is not presented as live. When enabled, deterministic fallback is
used only after a provider failure and is marked as fallback. When disabled,
the provider error is returned. Last valid weather data is preserved on a
failed refresh rather than replaced with fabricated fresh data.

Provider health is available through `GET /api/v1/system/providers` and is
also included in the system status response. The existing map, risk, sensor,
and monitoring contracts continue to carry source/status metadata.

## 3. Risk, event fusion, and LangGraph

Real observations enter the existing normalized weather/environment/sensor
boundaries and then the existing deterministic risk engine. No second risk
engine was added. Freshness and provider source affect risk data status and
explainability.

USGS assessment uses the existing event-fusion/disaster-intelligence entry
point, followed by supervisor, specialist fan-out, merge, resources, rescue
priority, routing, response planning, approval, monitoring, and re-planning.
Community reports remain independent of external providers.

## 4. GIS, routing, and tourist safety

Leaflet and the current GIS map were preserved. OSRM is an additive provider
adapter only; the existing route safety layer still rejects flagged hazard
zones and retains the local verified graph fallback. Tourist safety continues
to consume backend risk, hazard, alert, route, and environmental data rather
than hardcoded Nepal results.

## 5. Configuration and security

`.env.example` now documents weather, environment, USGS, routing, sensor
gateway, timeout, retry, fallback, and authentication settings. The example
contains placeholders only; external keys remain backend-only. Production
must provide a unique `AUTH_SECRET_KEY`, set `ALLOW_ANONYMOUS_ADMIN=false`,
configure `FRONTEND_URL`, and choose real providers explicitly. The runtime
defaults remain safe for local deterministic development (`demo` providers,
fallback enabled); `.env.example` recommends Open-Meteo for real weather and
environment data.

## 6. Database and demo data

`campusflow.db` remains the sole authoritative runtime database. No migration,
reset, drop, rename, or seed recreation was performed. The read-only final
check found:

- incidents 55; response plans 84
- sensor observations/events 28/28
- risk predictions 18
- resources 24; rescue requests 1; routes 2
- notifications 176; agent runs 15; department responses 24
- Nepal region `DEMO-NEPAL-MOUNTAIN`
- zone `DEMO-N14` / `N-14 (DEMO/SIMULATION)`
- no `aitam.db`

The database file timestamp and size were unchanged by the Phase 9A
validation. No physical IoT data was inserted.

## 7. Tests and validation

- Phase 9A mocked provider tests: **8 passed**.
- Backend isolated suite: **126 passed, 4 warnings**.
- Frontend Vitest suite: **96 passed**.
- Frontend production build: **passed** with the existing large-chunk warning
  for the command-center/application bundles.
- `python -m compileall -q backend`: passed.
- `git diff --check`: passed; Git emitted only existing line-ending warnings.
- External calls were not made by tests; provider HTTP behavior was mocked.
- Root legacy suite was not rerun because the established root tests write into
  `campusflow.db`. Its known baseline remains 52 passed, 1 skipped, and one
  unrelated async timing failure documented in `PHASE_8_REPORT.md`.

## 8. Remaining limitations

1. A real weather/routing feed requires deployment configuration and network
   access; deterministic fallback remains available for offline demos.
2. No physical MQTT/HTTP sensor device is connected. The HTTP sensor boundary
   is ready for a validated gateway endpoint.
3. Browser-level live-provider verification was not performed in this shell;
   mocked provider contracts, frontend tests, build, compile, and read-only
   database checks were completed.
4. The existing frontend bundle-size warning remains and was not hidden.
5. Deployment was not performed.

## 9. Phase 9A files

### Created

- `PHASE_9A_REPORT.md`
- `backend/api/earthquakes.py`
- `backend/models/domain.py`
- `backend/services/earthquake_providers.py`
- `backend/services/environmental_providers.py`
- `backend/services/provider_health.py`
- `backend/services/risk_engine.py`
- `backend/services/risk_service.py`
- `backend/services/routing_providers.py`
- `backend/services/safe_routing.py`
- `backend/services/sensor_monitoring.py`
- `backend/services/weather_providers.py`
- `backend/tests/test_phase9a_providers.py`
- `frontend/.env.example`

### Modified

- `.env.example`
- `backend/api/system.py`
- `backend/config.py`
- `backend/main.py`
- `backend/models/incident.py`
- `backend/services/road_network.py`
- `frontend/src/services/api.ts`

### Deleted

- None in Phase 9A.

