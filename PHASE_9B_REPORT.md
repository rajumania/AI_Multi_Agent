# Phase 9B — Live Provider Configuration + Real Data Verification

## Status

Phase 9B is complete for live-provider configuration and verification. No
new architecture, UI redesign, database, risk engine, or deployment was
introduced.

## 1. Providers configured

The ignored local `.env` now selects the existing live provider boundaries:

- `WEATHER_PROVIDER=open_meteo`
- `ENVIRONMENT_PROVIDER=open_meteo`
- `EARTHQUAKE_PROVIDER=usgs`
- `ROUTING_PROVIDER=osrm`
- `SENSOR_PROVIDER=demo` because no physical gateway is connected
- `ALLOW_DETERMINISTIC_FALLBACK=true`

The `.env.example` remains the shareable configuration template. No
credentials were copied into source control, React, logs, or API responses.

## 2. Real URLs and credentials

| Provider | URL | Credential required by current adapter |
|---|---|---|
| Open-Meteo | `https://api.open-meteo.com/v1/forecast` | No key for the selected public endpoint |
| USGS | `https://earthquake.usgs.gov/fdsnws/event/1/query` | No key |
| OSRM | `http://router.project-osrm.org` | No key for the configured public endpoint; production use must respect service limits or use an approved instance |
| HTTP/IoT sensor gateway | `SENSOR_API_URL` | Optional `SENSOR_API_KEY` bearer token |

Production variables are documented in `.env.example` and include auth,
CORS/frontend URL, API URL, provider URLs, fallback, timeout, retry, and
sensor-gateway settings. The existing frontend derives its WebSocket origin
from `VITE_API_BASE_URL`.

## 3. Live verification matrix

| Provider | Request | Response | Freshness | Status |
|---|---|---|---:|---|
| Open-Meteo | N-14 `(28.21, 84.02)` current weather | HTTP success; 23°C, 96% humidity, 0.1 mm precipitation, 1.8 kph wind, 914.7 hPa, rain | ~9.4 minutes | `LIVE` |
| Open-Meteo environment | Same coordinates through existing environmental adapter | 4 normalized indicators: rainfall, humidity, wind, pressure | `LIVE` on all returned indicators | `LIVE` |
| USGS | Nepal-region query, configured 24h / magnitude 4.5+ / 500 km | HTTP success; zero qualifying events in the window | Provider response current | `HEALTHY`, no qualifying event |
| OSRM | `(28.21,84.02)` to `(28.22,84.03)` | 109 geometry points, 2,182 m, 325 s, 10 steps | Route response live | `LIVE` |
| HTTP/IoT boundary | Validated gateway-shaped observation through existing sensor API | Normalized IOT observation, critical anomaly, event correlation | Timestamp validated | `IOT` / explicit sensor status |

Open-Meteo, USGS, and OSRM calls were made over the network. All test
requests used the existing provider adapters and no runtime database writes.

## 4. Real data to risk and LangGraph

The live Open-Meteo observation was passed to the existing
`RiskFeatureEngine` and risk graph. It produced a backend-derived `LIVE`
result: score **25.92**, level **medium**, confidence **92.14**, with
freshness of approximately 10 minutes. A separate isolated temporary-database
API flow returned `201` for `/api/v1/risk/predict` with `LIVE` data and `201`
for `/api/v1/events` with a `LIVE` prediction, pending approval, and 20 agent
results.

No deterministic Nepal reference score was hardcoded or used as a live result.
The existing event-fusion boundary, LangGraph supervisor, specialist fan-out,
merge, resource/rescue/routing stages, response plan, approval gate, and
monitoring path were reused.

## 5. Tourist safety

The isolated real-data flow also called the existing tourist-safety endpoint
for `DEMO-N14`. It returned HTTP 200 with backend-derived risk score **26.66**,
real weather text (`source OPEN_METEO`), and recommendation **CAUTION**. The
service did not hardcode a Nepal travel warning.

## 6. Sensor gateway verification

No physical sensor or MQTT broker is connected. A controlled gateway-shaped
payload was sent through the existing `/api/v1/sensor-events` API in the
isolated backend test database. The response contained:

- normalized source `IOT`
- validated N-14 coordinates and timestamp
- critical river-level anomaly
- sensor event and event-fusion correlation
- existing AI analysis and agent results

This verifies the production boundary without claiming physical IoT
connectivity.

## 7. Provider health, freshness, and failure handling

`GET /api/v1/system/providers` was verified. After real calls, Open-Meteo,
USGS, and OSRM reported successful health telemetry with latency and last
success timestamps. Provider metadata contains no credentials or request
headers.

The failure path was verified with an invalid weather endpoint: the adapter
recorded failure and returned `DEMO_FALLBACK` with status `FALLBACK`. Mocked
tests also cover invalid responses, HTTP failure, stale timestamps, and route
hazard blocking. Stale observations remain `STALE`; they are never presented
as live.

Retry counts and exponential backoff are bounded by the existing settings:
weather, routing, and sensor retries default to 2 with 0.25 seconds initial
backoff; USGS uses its documented 2-retry configuration. No aggressive polling
was added.

## 8. Community and offline behavior

Community reporting remains independent of external providers. The isolated
real-data event flow accepted a community event and reached a pending
approval response plan. Existing offline/PWA behavior remains unchanged;
provider failure uses fallback or stale state and does not block local
community reporting.

## 9. Database safety

`campusflow.db` remained authoritative and unchanged. Final read-only counts
remain incidents 55, response plans 84, sensor observations/events 28/28,
risk predictions 18, resources 24, rescue requests 1, routes 2,
notifications 176, agent runs 15, and department responses 24. The live API
workflow used a temporary database that was disposed and removed. No duplicate
demo rows were added to the runtime database.

## 10. Security

`.env` is ignored and is not tracked. Provider secrets were not printed,
copied, committed, returned by APIs, or placed in frontend configuration.
Open-Meteo, USGS, and the selected public OSRM request do not require keys.
Production still requires a unique `AUTH_SECRET_KEY`,
`ALLOW_ANONYMOUS_ADMIN=false`, correct `FRONTEND_URL`, and credentials for
any selected notification, LLM, dispatch, or private sensor services. The
pre-existing local `.env` contains unrelated credentials and should be
rotated if it has ever been shared.

## 11. Tests and build

- Phase 9A/9B provider and gateway tests: **9 passed**.
- Backend isolated suite: **127 passed, 4 warnings**.
- Frontend suite: **96 passed**.
- `python -m compileall -q backend`: passed.
- `git diff --check`: passed; only existing line-ending warnings were emitted.
- Frontend production build: passed.
- Root legacy suite was not rerun because it writes into `campusflow.db`; its
  known baseline remains 52 passed, 1 skipped, and one unrelated async timing
  failure documented in `PHASE_8_REPORT.md`.

## 12. Remaining limitations

1. USGS returned no Nepal events meeting the configured 24-hour/magnitude
   threshold, so live event field normalization remains covered by mocked
   GeoJSON fixtures.
2. No physical IoT/MQTT device is connected; only the validated HTTP boundary
   and actual ingestion endpoint were exercised.
3. Public OSRM use is suitable for verification, not an SLA-backed production
   deployment without an approved provider or self-hosted instance.
4. Browser-level live-provider automation was not available in this shell.
5. Existing frontend bundle-size warnings remain.
6. Deployment was not performed.

## 13. Files

### Created

- `PHASE_9B_REPORT.md`

### Modified

- `.env` (ignored local runtime configuration only)
- `backend/tests/conftest.py` (keeps regression tests network-free)
- `backend/tests/test_phase9a_providers.py` (adds live-boundary/API contract coverage)

### Not modified or deleted

- `campusflow.db` was not modified.
- No files were deleted.
- No Phase 10 work was started.

