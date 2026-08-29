# Phase 11.7A-FIX — Live External Provider Verification

Date: 2026-08-29  
Status: **COMPLETE**

This fix preserved the existing provider, normalized intelligence, deterministic
risk, LangGraph, department, approval, WebSocket, GIS, and database
architecture. No provider response was mocked or promoted to LIVE without a
validated external response.

## Root cause of WinError 10013

The original failure was below the application transport layer:

- DNS resolved all configured provider hosts.
- Windows WinHTTP reported direct access with no proxy configured.
- Raw `socket.create_connection`, `httpx` with `trust_env=True`, `httpx` with
  `trust_env=False`, and `curl` all failed before receiving an HTTP response.
- The failure was `PermissionError [WinError 10013]`, with curl status `000`.
- The configured URLs, DNS, and TLS validation were not the cause.
- The restricted process execution context blocked outbound sockets. Running
  the same existing application in the approved network-enabled context
  succeeded. No firewall or security control was disabled or bypassed.

## Changes made

Only two provider-contract corrections were required:

1. `backend/services/environmental_providers.py` now records ENVIRONMENT
   provider success/failure, latency, source, and freshness when it delegates
   to the live Open-Meteo adapter.
2. `backend/services/weather_providers.py` accepts valid high-altitude surface
   pressure down to 100 hPa. The previous 800 hPa lower bound rejected the
   real Himalayan response and incorrectly caused fallback data.

No database schema or workflow changes were made.

## Provider URLs and real HTTP verification

All requests below were unmocked requests made by the network-enabled AITAM
application or its existing adapters. HTTP 200 means the payload also passed
the provider-specific structural validation.

| Provider | Configured URL | HTTP result | App/adapter result | Latency observed |
|---|---|---:|---|---:|
| Open-Meteo | `https://api.open-meteo.com/v1/forecast` | 200 | `LIVE`, validated JSON/current block | ~1,285 ms |
| USGS | `https://earthquake.usgs.gov/fdsnws/event/1/query` | 200 | `NO_QUALIFYING_EVENT`, validated GeoJSON | ~1,207 ms |
| IMD CAP | `https://cap-sources.s3.amazonaws.com/in-imd-en/rss.xml` | 200 | `NO_ACTIVE_WARNING`, validated XML/CAP entries | ~1,000 ms |
| Nominatim | `https://nominatim.openstreetmap.org/reverse` | 200 | `LIVE`, validated JSON label | ~498 ms |
| OSRM | `http://router.project-osrm.org` | 200 | `LIVE`, validated route geometry/steps | ~787 ms |

Provider health after verification reported `HEALTHY` for OPEN_METEO,
ENVIRONMENT, USGS, IMD_CAP, NOMINATIM, and OSRM, with last-success timestamps,
latency, source, and freshness metadata. No credentials, authorization headers,
URLs containing secrets, or provider response bodies are exposed by the health
endpoint.

## AITAM weather and environment

Request coordinates: `18.56517, 84.19587`.

- Temperature: **26.4 °C**
- Relative humidity: **89%**
- Precipitation/rain: **0.0 mm**
- Wind: **10.9 kph**, direction **243°**
- Surface pressure: **998.4 hPa**
- Condition: **cloudy**
- Provider observation: `2026-08-28T22:30:00Z`
- Source: `OPEN_METEO`
- Status: `LIVE`
- Freshness during verification: approximately **294 seconds**

The environmental adapter returned four normalized live indicators from the
same exact coordinates: rainfall, humidity, wind speed, and pressure. They were
marked `OPEN_METEO`/`LIVE` with observation, receipt, and freshness metadata.

## USGS earthquake result

The AITAM query used the configured 500 km radius, 24-hour window, and minimum
magnitude 4.5. The real USGS response was valid GeoJSON with zero qualifying
features. The application returned:

`No qualifying earthquake detected in the configured window.`

Status: `NO_QUALIFYING_EVENT`. No earthquake was fabricated.

## IMD CAP severe-weather result

The configured official IMD CAP feed returned HTTP 200 XML. The existing parser
validated the feed, checked expiry, parsed alert geometry, and filtered for
geographic applicability against the selected coordinates. No active applicable
warning was present for AITAM, so the application returned:

`NO_ACTIVE_WARNING` — `No active severe-weather warning found for the selected coordinates.`

Community text or photographs do not create an IMD warning or cyclone finding.

## Nominatim reverse geocoding

The configured User-Agent was sent and exact coordinates remained authoritative.

- AITAM `18.56517,84.19587` → Aditya Institute of Technology and Management,
  Tekkali, Srikakulam, Andhra Pradesh, India.
- Hyderabad `17.385,78.4867` → Koti Women's College Road, Hyderabad,
  Telangana, India.

Both responses were HTTP 200 and returned `LIVE`. Returned labels were not used
to replace the supplied coordinates.

## OSRM routing

The real route request used AITAM coordinates and a Tekkali destination. The
validated result contained:

- Source: `OSRM`
- Status: `LIVE`
- Distance: **6,516 m**
- Duration: **493 s / 8.2 minutes**
- Geometry: **101 points**
- Turn-by-turn steps: **11**

The result passed through the existing safe-routing layer. A geometrically
valid OSRM route is not independently treated as safe; hazard/blocked-route
validation remains authoritative. The AITAM intelligence preview produced five
live OSRM resource-route evaluations.

## Exact-location tests

| Test | Coordinates | Weather | Reverse geocode / hazard result |
|---|---:|---|---|
| AITAM | `18.56517,84.19587` | `LIVE`, Open-Meteo | `LIVE`; `NO_ACTIVE_WARNING`; `NO_QUALIFYING_EVENT` |
| Hyderabad | `17.385,78.4867` | `LIVE`, Open-Meteo | `LIVE` Nominatim label |
| Himalayan | `27.9881,86.925` | `LIVE`, Open-Meteo; pressure 352.9 hPa | Real Nominatim label; no fabricated hazard |
| Sydney | `-33.8688,151.2093` | `LIVE`, Open-Meteo | Real Nominatim label; no fabricated hazard |

The previous Himalayan fallback was eliminated by the pressure validation fix.
No Guntur, Nepal, N-14, or fixed AITAM coordinates were substituted for user
coordinates.

## Unified intelligence and risk

`POST /api/v1/intelligence/preview` was exercised for the exact AITAM point.
It returned `data_status=LIVE` with live weather, four live environmental
observations, `NO_QUALIFYING_EVENT` for USGS, `NO_ACTIVE_WARNING` for IMD CAP,
live reverse geocoding, and five live OSRM routes.

The existing deterministic risk engine returned:

- Score: **12.73**
- Severity: **low**
- Confidence: **47.0**
- Data status: **LIVE**
- Freshness: approximately **286 seconds**

The score was calculated from normalized provider evidence and existing
geographic/risk features; no risk or weather value was hardcoded. The response
retained score, severity, confidence, contributing factors, source/status, and
freshness fields.

## LangGraph, departments, approval, and WebSocket

The existing workflow and lifecycle implementation was preserved. The live
preview exercised the same normalized intelligence boundary used before the
existing LangGraph workflow. Existing backend regression coverage passed for
the supervisor/specialist workflow, risk, resource coordination, approval, and
department assignment paths.

For the neutral AITAM preview evidence, targeting returned only:

- `SECURITY` — protect the scene, public access, and responder safety.

No department-wide broadcast was generated. The existing WebSocket endpoint
accepted a real frontend connection during the network-enabled backend run;
the 3D Command Center and map continue to consume backend lifecycle events.
No temporary incident was submitted merely to create database or dispatch
traffic during provider verification.

## Tourist safety

The exact-coordinate AITAM safety check returned HTTP 200 with:

- Risk: **8.55 / low**
- Recommendation: **SAFE**
- Data status: **LIVE**
- Weather/environment: `LIVE`
- Earthquake: `NO_QUALIFYING_EVENT`
- Severe weather: `NO_ACTIVE_WARNING`
- Active alerts: none

The check used the selected coordinates and did not use a fixed destination.

## Database safety

Runtime database: `campusflow.db` only. `aitam.db` does not exist.

Timestamped backups created before application restarts:

- `campusflow_pre_phase11_7a_fix_20260829_035808.db`
- `campusflow_pre_phase11_7a_fix_restart_20260829_040157.db`
- `campusflow_pre_phase11_7a_fix_pressure_20260829_040342.db`

No temporary incident or permanent verification record was inserted. Counts
before and after remained identical:

```text
users 11; department_users 14; organizations 1; organization_departments 8;
regions 2; zones 3; communities 1; incidents 56;
sensor_observations 28; sensor_events 28; risk_predictions 18;
campus_resources 24; rescue_requests 1; routes 2; notifications 178;
response_plans 84; agent_runs 15; department_responses 24; audit_logs 858
```

`PRAGMA foreign_key_check` returned no violations.

## Tests and build

- Backend tests: **130 passed**, 4 pre-existing warnings
- Frontend tests: **96 passed**
- Provider tests are included in the backend suite and passed
- `python -m compileall -q backend`: passed
- `git diff --check`: passed; existing line-ending warnings only
- Production frontend build: passed; existing large-chunk warning remains

## Local application

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`
- Backend health: HTTP 200, database connected
- Frontend root: HTTP 200
- Provider health: `GET /api/v1/system/providers` returned non-secret health
  metadata and all six verified entries were healthy after the live calls.

## Remaining limitations

- The ordinary restricted shell context still blocks outbound sockets with
  WinError 10013. The backend must run in a network-permitted process context
  on this machine for providers to remain LIVE.
- IMD returned no active AITAM warning during this verification; this is a
  real no-warning result, not a fabricated cyclone state.
- No physical IoT sensor gateway, paid dispatch/messaging service, or image
  analysis model was configured or claimed.
- Production still requires a strong backend-only `AUTH_SECRET_KEY` and the
  deployment's actual network/security policy to permit the configured
  provider endpoints.

**PHASE 11.7A STATUS: COMPLETE**

Genuinely LIVE in this verification: **Open-Meteo, environmental Open-Meteo,
USGS, IMD CAP feed, Nominatim, and OSRM**. The valid no-event/no-warning
outcomes remain explicitly represented as `NO_QUALIFYING_EVENT` and
`NO_ACTIVE_WARNING`.
