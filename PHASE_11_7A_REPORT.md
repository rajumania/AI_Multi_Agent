# Phase 11.7A — Live External Provider Verification

Date: 2026-08-29  
Status: **PARTIAL**

This verification used the existing Phase 11.7 provider adapters and running
AITAM APIs. No architecture, LangGraph, risk, department, approval, 3D,
offline/PWA, or database structure changes were made.

## Network result

Outbound HTTPS was tested from the current machine before provider calls. The
probe failed with `Unable to connect to the remote server`. A direct unmocked
provider sweep then failed for every provider with:

`httpx.ConnectError: [WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions`

Therefore every direct provider request had HTTP status `none`, zero response
bytes, and failed payload validation. No provider is claimed LIVE.

## Provider verification

| Provider | URL | Direct HTTP result | Adapter/API result |
|---|---|---|---|
| OPEN-METEO | `https://api.open-meteo.com/v1/forecast` | No HTTP response; `ConnectError`; approximately 2.15–2.33 s per coordinate | `FALLBACK/DEMO_FALLBACK`, validated fallback contract |
| USGS | `https://earthquake.usgs.gov/fdsnws/event/1/query` | No HTTP response; `ConnectError`; approximately 2.20–2.33 s per coordinate | API returned HTTP 503/provider unavailable; no earthquake fabricated |
| IMD CAP | `https://cap-sources.s3.amazonaws.com/in-imd-en/rss.xml` | No HTTP response; `ConnectError`; approximately 2.19–2.34 s per coordinate | `OFFLINE`; no warning/cyclone fabricated |
| NOMINATIM | `https://nominatim.openstreetmap.org/reverse` | No HTTP response; `ConnectError`; approximately 2.23–2.34 s per coordinate | `OFFLINE/COORDINATES`, exact coordinates retained |
| OSRM | `http://router.project-osrm.org/route/v1/driving/...` | No HTTP response; `ConnectError`; approximately 0.51 s for the direct route probe | Existing campus route fallback used where verified geometry existed; labelled `FALLBACK` |

The direct requests used the configured URLs, exact coordinates, bounded
timeouts, and provider-specific structural validation. They were not mocked.

## Exact coordinate tests

| Test point | Coordinates | Weather | Severe weather | Reverse geocode |
|---|---:|---|---|---|
| AITAM | `18.56517, 84.19587` | `FALLBACK/DEMO_FALLBACK` | `OFFLINE` | `OFFLINE/COORDINATES` |
| Second real location | `17.385000, 78.486700` | `FALLBACK/DEMO_FALLBACK` | `OFFLINE` | `OFFLINE/COORDINATES` |
| Himalayan location | `27.988100, 86.925000` | `FALLBACK/DEMO_FALLBACK` | `OFFLINE` | `OFFLINE/COORDINATES` |
| No-hazard verification point | `-33.868800, 151.209300` | `FALLBACK/DEMO_FALLBACK` | `OFFLINE` | `OFFLINE/COORDINATES` |

The local API returned the supplied latitude/longitude unchanged for all four
points. No Guntur, Nepal, N-14, or hidden AITAM coordinate substituted for a
request coordinate.

USGS was queried through the authenticated API for all four points with a
500-km radius, 24-hour window, and minimum magnitude 4.5. Because the real
provider request failed, the result was `OFFLINE`, not
`NO_QUALIFYING_EVENT`; the latter is returned only after a validated USGS
response with no qualifying features.

## Risk and routing

The AITAM live preview completed through `POST /api/v1/intelligence/preview`
and returned:

- exact coordinates `18.56517,84.19587`
- weather `FALLBACK/DEMO_FALLBACK`
- environment `FALLBACK`
- USGS `OFFLINE`
- IMD CAP `OFFLINE`
- deterministic risk `MEDIUM`, score `35.0`, status `FALLBACK`
- five existing resource route evaluations
- route fallback geometry where verified campus geometry existed

No live provider observations were available to validate a LIVE risk score.
The existing normalized/risk path preserved score, severity, confidence,
factors, source/status, and freshness fields without hardcoded live data.

## Provider health

`GET /api/v1/system/providers` returned non-secret metadata only. After the
real failed requests, relevant providers reported `FAILED` with last failure,
latency, source, failure type, and failure count. No API keys, authorization
headers, response bodies, or secrets were exposed.

## Database safety

No temporary incident or permanent test record was inserted for Phase 11.7A.
The runtime database remains `campusflow.db`; `aitam.db` does not exist.

A read-only verification backup was created:

`campusflow_pre_phase11_7a_20260829_035001.db`

Current counts remained at the Phase 11.7 baseline:

```text
users 11; department_users 14; organizations 1; organization_departments 8;
regions 2; zones 3; communities 1; incidents 56;
sensor_observations 28; sensor_events 28; risk_predictions 18;
campus_resources 24; rescue_requests 1; routes 2; notifications 178;
response_plans 84; agent_runs 15; department_responses 24; audit_logs 858
```

`PRAGMA foreign_key_check` returned no violations.

## Tests and local application

- Backend regression tests: **130 passed**
- Phase 11.7A/provider tests: **12 passed** provider suite; **3 passed** focused real-intelligence tests
- Frontend tests: **96 passed**
- `python -m compileall -q backend`: passed
- `git diff --check`: passed with existing line-ending warnings only
- Production frontend build: passed; existing large-chunk warning remains
- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`
- Local backend health: HTTP 200, database connected
- Local frontend: HTTP 200
- Local exact-location preview, weather, environment, severe-weather, reverse-geocoding, routing fallback, risk, and provider-health paths exercised

## Remaining limitations

The current machine cannot establish outbound sockets, so no provider can be
genuinely promoted to LIVE in this run. When outbound HTTPS/HTTP access is
enabled, rerun the same verification to obtain real Open-Meteo, USGS, IMD CAP,
Nominatim, and OSRM statuses. Public Open-Meteo, USGS, IMD CAP, Nominatim, and
OSRM configuration requires no invented API key. Production still requires a
strong backend-only `AUTH_SECRET_KEY`; optional paid weather, IoT, dispatch,
messaging, and image-analysis services require their own real credentials or
hardware.

**PHASE 11.7A STATUS: PARTIAL**

Genuinely LIVE providers in this run: **none**.  
Verified but unavailable: Open-Meteo `FALLBACK`, USGS `OFFLINE`, IMD CAP
`OFFLINE`, Nominatim `OFFLINE`, and OSRM `FALLBACK` where existing geometry
was available.
