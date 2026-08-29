# Phase 2 Report — Environmental Ingestion, Risk Prediction & Early Warning

## Status

Phase 2 is complete. The implementation is additive and preserves the existing FastAPI, SQLAlchemy, authentication/RBAC, LangGraph incident workflow, notification table, WebSocket endpoint, frontend design system, and deployment configuration.

This prototype provides decision-support risk estimation and is not an authoritative disaster forecasting system.

## 1. Weather provider architecture

`backend/services/weather_providers.py` defines a normalized `WeatherProvider` contract and two implementations:

- `ExternalWeatherProvider`: OpenWeather-compatible HTTP adapter selected only when `WEATHER_PROVIDER` is `external`, `openweather`, or `live` and both backend-only URL/key settings exist.
- `DemoWeatherProvider`: deterministic, clearly labelled demo observations for reliable development and demonstrations.
- `fetch_with_fallback`: handles provider configuration errors, HTTP failures, timeouts, and invalid provider payloads by returning `DEMO_FALLBACK` data and a structured error string. Secrets never enter response payloads.

Normalized weather includes coordinates, condition, temperature, humidity, rainfall, intensity, wind, pressure, precipitation probability, observation time, receipt time, and source.

## 2. Environmental data architecture

`EnvironmentalObservationDB` stores normalized indicator/value records with zone, coordinates, observation time, receipt time, unit, and source. `DemoEnvironmentalProvider` supplies explicitly demo-labelled water level, soil moisture, and drainage signals when no environmental records exist. The weather API exposes environmental ingestion and history under `/api/v1/weather/environment`.

## 3. Risk feature engine

`RiskFeatureEngine` combines weather, environmental, zone geography, historical metadata, population exposure, and recent community rescue reports. All feature values are bounded to 0–100. Missing values remain absent; the scoring engine renormalizes weights over available factors rather than treating missing evidence as high risk.

Supported features include rainfall, intensity, water level, low-elevation vulnerability, slope, soil moisture, terrain, drainage, historical risk, community signal, population exposure, wind, pressure, temperature, humidity, weather severity, coastal vulnerability, and heat duration.

## 4. Risk formula

For each disaster type:

`risk_score = sum(feature_score × configured_weight) / sum(weights for available features)`

The result is clamped to 0–100 and classified as:

- 0–24 LOW
- 25–49 MEDIUM
- 50–74 HIGH
- 75–100 CRITICAL

Default weights are centralized in `risk_engine.py` and can be overridden with `RISK_WEIGHTS_JSON`. The defaults are disaster-specific: flood and urban flood emphasize rainfall/water/drainage; landslide emphasizes rainfall, slope, soil moisture and terrain; cyclone emphasizes wind, pressure and coastal vulnerability; heatwave emphasizes temperature, humidity and duration; severe weather emphasizes wind, rainfall and weather severity.

## 5. Confidence and freshness

Confidence is calculated independently from risk using evidence coverage, source coverage, feature completeness, and freshness. It is not a probability of disaster. Observations include `timestamp`/`observed_at`, `received_at`, and `source`. Data older than `WEATHER_STALE_AFTER_MINUTES` is marked stale and confidence is reduced. API and UI status labels distinguish LIVE, DEMO, MIXED, MANUAL, and STALE DATA.

## 6. Explanation and LangGraph integration

`backend/graph/risk_workflow.py` is a dedicated LangGraph workflow with two stages:

1. deterministic risk engine produces score, level, confidence, features;
2. `RiskPredictionAgent` turns those structured results into a briefing, factors, and recommendations.

The agent cannot invent or override numerical risk. Existing incident LangGraph topology and all existing agents remain unchanged. Existing agents remain available for future mapping: Medical → hospital/medical coordination; Transport → emergency vehicles; Communication → alerts; Facilities → infrastructure/resources; Security → emergency services/rescue coordination; Supervisor → response orchestration.

## 7. Early warning and alert deduplication

`EarlyWarningService` maps LOW/MEDIUM to monitoring guidance, HIGH to a warning recommendation, and CRITICAL to a critical warning recommendation. HIGH and CRITICAL predictions create records in the existing `NotificationDB` alert system. A zone-level cooldown prevents repeated alert spam; a HIGH → CRITICAL escalation is allowed through the cooldown. No dangerous real-world action is automatically executed.

## 8. API endpoints

- `POST /api/v1/risk/predict`
- `GET /api/v1/risk`
- `GET /api/v1/risk/{prediction_id}`
- `GET /api/v1/risk/zones`
- `GET /api/v1/risk/summary`
- `GET /api/v1/risk/early-warnings`
- `GET /api/v1/weather/current`
- `GET /api/v1/weather/history`
- `GET /api/v1/weather/zone/{zone_id}`
- `POST /api/v1/weather/ingest`
- `POST /api/v1/weather/environment`
- `GET /api/v1/weather/environment`
- `POST /api/v1/demo/scenarios/flood-critical`

Prediction and ingestion mutations use the existing command-principal dependency. Existing routes remain registered.

## 9. Demo mode

`POST /api/v1/demo/scenarios/flood-critical` writes severe rainfall, rising water, drainage, soil moisture, and 17 community-report signals for `DEMO-ZONE-A`, then runs the normal ingestion → feature → risk → LangGraph → warning → persistence path. The final score is not hard-coded. Every record is labelled `DEMO_SCENARIO`, and the UI displays DEMO DATA.

## 10. Failure handling

External provider credentials are read only by the backend. Provider timeout/failure and invalid values fall back to deterministic demo data with warning logging. Incoming API measurements reject non-finite values, impossible coordinates, and bounded outliers through Pydantic validation. Existing event handling continues even when no WebSocket client is connected.

## 11. Realtime integration

The existing `/api/v1/events/ws` endpoint now broadcasts `risk_updated`, `early_warning_created`, `weather_updated`, and `environment_updated`. The dashboard reuses its current WebSocket and refreshes the risk summary when these events arrive; no parallel realtime system was introduced.

## 12. Frontend

`RiskPanel` is a functional backend-driven dashboard panel showing score, level, confidence, factors, recommendations, freshness/data status, warning status, and a compact history trend. The Risk & Early Warning navigation view uses the same component. It shows an honest empty state when no prediction exists and never embeds demo risk values in React.

## 13. Database changes

Additive fields were added to zones, weather observations, environmental observations, and risk predictions. Existing legacy observation rows are backfilled with `received_at = observed_at` where possible. Existing rows and tables are preserved; no database drop or destructive migration was used.

## 14. Tests and validation

- Phase 2 backend tests: 14 passed.
- Full backend suite: 102 passed (88 Phase 1 baseline + 14 Phase 2 tests).
- Frontend tests: 92 passed.
- Frontend production build: successful; existing large-chunk warning remains.
- End-to-end smoke: demo prediction persisted and returned through `/risk`; repeated demo execution produced one alert within cooldown.
- Backend application import and route registration: successful.

The Phase 1 baseline was backend 88 passed, frontend 92 passed, legacy 52 passed/1 skipped with the known timing-related failure. After Phase 2, frontend remains 92 passed; legacy remains 52 passed/1 skipped with that same known timing-related failure. The legacy timing failure is not hidden or deleted.

## 15. Known limitations before Phase 3

- External provider adapters are intentionally OpenWeather-compatible rather than a broad multi-provider catalog.
- Environmental live sensor connectors, advanced scientific forecasting, geospatial vulnerability layers, offline/PWA support, and rescue-request prioritization remain later phases.
- The existing local environment may still show the previously documented Vite dev-server/node_modules permission issue; the production build succeeds.
- Risk is decision support only and requires qualified emergency-management review before operational use.
