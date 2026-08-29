# Phase 11.7 — Real External Disaster Intelligence

Date: 2026-08-29  
Status: **PARTIAL**

Phase 11.7 extends the existing LangGraph, deterministic risk, WebSocket,
GIS, routing, RBAC, approval, monitoring, and 3D command-center architecture.
No second runtime database or replacement architecture was introduced.

## Providers and configuration

| Capability | Provider / URL | Runtime result |
|---|---|---|
| Weather | Open-Meteo: `https://api.open-meteo.com/v1/forecast` | Adapter integrated; this environment returned `FALLBACK/DEMO_FALLBACK` because the external request was unavailable |
| Earthquakes | USGS: `https://earthquake.usgs.gov/fdsnws/event/1/query` | Adapter integrated with exact-point radius, lookback, minimum magnitude, distance, freshness, event ID, and explicit no-event message; runtime request returned `OFFLINE` here |
| Severe weather / cyclone warnings | IMD CAP RSS: `https://cap-sources.s3.amazonaws.com/in-imd-en/rss.xml` | Authoritative CAP boundary integrated; exact-point geometry/radius filtering and warning expiry implemented; runtime feed returned `OFFLINE` here |
| Reverse geocoding | Nominatim: `https://nominatim.openstreetmap.org/reverse` | Best-effort label boundary integrated; coordinate label is retained when unavailable |
| Routing | Existing OSRM: `http://router.project-osrm.org` | Existing adapter reused; preview tries OSRM first, then existing verified campus/fallback geometry, always status-labelled |
| Environment | Existing Open-Meteo environmental adapter | Reused; normalized observations and provider status are carried into risk |

The IMD feed choice is based on the official [IMD API reference](https://api.imd.gov.in/public/api_reference.html) and the [WMO-listed IMD CAP source](https://alertingauthority.wmo.int/authorities.php?recId=182). No cyclone API was invented, and a community photograph cannot create a cyclone warning.

No provider API key is required for the configured public Open-Meteo, USGS,
OSRM, IMD CAP, or Nominatim endpoints. Production still requires a strong
backend-only `AUTH_SECRET_KEY`; optional OpenWeather, IoT, SMS, dispatch,
telephony, push, email, and LLM credentials remain backend `.env` settings.
Credentials and authorization headers are not returned by provider health.

## Exact-location flow

Community reporting now supports browser GPS, map click/drag, and manual
latitude/longitude entry. The selected point is displayed to six decimals and
is sent as the authoritative coordinate to preview, weather, hazard, routing,
and incident APIs. The AITAM institutional reference remains `18.56517,
84.19587`; it is not used as a hidden default for arbitrary investigations.
Reverse geocoding is best effort and never replaces the coordinates.

The new non-persisting endpoint is:

`POST /api/v1/intelligence/preview`

It returns one normalized intelligence object containing location, text/photo
evidence state, weather, environmental indicators, USGS events, IMD warnings,
geographic context, routes, risk, targeted departments, and provider health.

## Evidence, risk, and workflow

The existing deterministic risk engine remains authoritative. New normalized
`weather_warning_score` and `earthquake_magnitude_score` indicators are fed
into the existing engine; scores are not hardcoded and a location alone does
not cause a high-risk result. Each result includes score, severity, confidence,
factors, explanation, timestamp, freshness, and status.

USGS output includes magnitude, depth, coordinates, event timestamp, distance,
event identifier, source, freshness, and status. When appropriate, the API
returns exactly: “No qualifying earthquake detected in the configured window.”

Photo selection remains a truthful `REFERENCE_ONLY` evidence reference because
binary permanent storage and an image-analysis model are not configured. The
UI explicitly says the image is supporting evidence. No image path can declare
`CYCLONE CONFIRMED`.

The incident trigger passes exact coordinates and external hazard evidence into
the existing Supervisor → parallel specialists → merge → resources → rescue
priority → hazard-aware routing → response plan → human approval → monitoring
→ recovery/re-planning graph. A runtime test completed this flow with a real
pending response plan, real agent records/events, exact coordinates, fallback
route geometry, and `approval_status=pending`; it did not dispatch anything.

Department recommendations include evidence-based reasons. Existing legacy
department routing/scoping mappings were preserved to avoid regressions; the
new preview and incident evidence boundary does not grant approval or dispatch
authority to community users.

## APIs and UI

Added/extended:

- `GET /api/v1/weather/current-exact`
- `GET /api/v1/earthquakes/recent` query controls and explicit no-event status
- `GET /api/v1/intelligence/reverse-geocode`
- `GET /api/v1/intelligence/severe-weather/alerts`
- `GET /api/v1/location/reverse-geocode`
- `POST /api/v1/intelligence/preview`
- `GET /api/v1/system/providers` IMD CAP and Nominatim health entries
- `POST /api/v1/events` exact latitude/longitude support
- travel safety now includes USGS/IMD warning evidence, provider statuses,
  hazards, freshness, and route status for selected coordinates

The community form now presents exact-coordinate controls, manual coordinate
inputs, an **Analyze Incident** step, weather/hazard/risk/evidence/department
preview, and then **Submit Emergency**. Existing approval-gated operational
notifications and WebSocket lifecycle events remain in place.

## Failure handling

All new external calls use bounded timeout/retry behavior, response validation,
provider health recording, explicit `LIVE`, `STALE`, `FALLBACK`, `OFFLINE`,
`NO_QUALIFYING_EVENT`, or `NO_ACTIVE_WARNING` states, and configured fallback
behavior. During runtime verification in this environment, external network
access was unavailable; observed results were:

- Open-Meteo: `FALLBACK/DEMO_FALLBACK`
- USGS: `OFFLINE`
- IMD CAP: `OFFLINE`
- Nominatim: coordinate fallback with `OFFLINE`
- OSRM: existing fallback route where verified campus geometry existed

None of these failures were presented as live observations.

## Database safety

Runtime database: `campusflow.db` only. No `aitam.db` was created. Before the
runtime mutation test, a timestamped backup was created:

`campusflow_pre_phase11_7_20260829_032853.db`

The temporary exact-coordinate incident and its generated child records were
removed after verification. Foreign-key validation is clean. Counts before
and after cleanup are identical:

```text
users 11; department_users 14; organizations 1; organization_departments 8;
regions 2; zones 3; communities 1; incidents 56;
sensor_observations 28; sensor_events 28; risk_predictions 18;
campus_resources 24; rescue_requests 1; routes 2; notifications 178;
response_plans 84; agent_runs 15; department_responses 24; audit_logs 858
```

## Verification

- Backend regression suite: **130 passed**
- Phase 11.7 provider/preview tests: **3 passed**
- Frontend tests: **96 passed**
- Provider regression tests: **12 passed**
- `python -m compileall -q backend`: passed
- `git diff --check`: passed; only existing line-ending warnings
- Production frontend build: passed; existing large-chunk warning remains
- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`
- Runtime health: backend and frontend returned successfully
- Runtime provider health: new IMD CAP and Nominatim entries visible
- Runtime exact AITAM preview: exact coordinates, fallback weather, offline
  hazard providers, deterministic risk, five route evaluations, and
  reference-only photo state returned successfully
- Runtime LangGraph incident: exact coordinate, specialist/operational agent
  results, pending approval, WebSocket-compatible lifecycle events, and
  fallback route returned successfully

Full manual browser execution of every admin/community/department interaction
was not claimed because the available Chrome environment could not complete
its GPU/encryption startup path. The local HTTP/API and automated suites are
the verified evidence for this checkpoint.

## Genuine limitations

This phase is partial rather than fully real-world complete because the current
runtime environment could not reach the external providers, so no live weather,
USGS event, IMD warning, Nominatim label, or OSRM route can be claimed from the
runtime smoke test. Public feeds become live when network egress is available;
the status handling is already explicit. Permanent binary image storage and a
configured backend-only image model are still required for actual image
analysis. Physical IoT observations and production dispatch channels still
require their external credentials/devices. Community users remain unable to
approve or dispatch response plans.

**PHASE 11.7 STATUS: PARTIAL**

The real provider boundaries, exact-location flow, normalized evidence, risk
integration, LangGraph integration, routing fallback labels, provider health,
RBAC/approval behavior, UI flow, tests, and database safety are implemented.
Live external observations and production image/IoT/dispatch capabilities
remain dependent on external network access, credentials, or hardware.
