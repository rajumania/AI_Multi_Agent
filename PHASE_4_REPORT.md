# Phase 4 Report — Advanced Interactive Disaster-Risk Map

## Status and scope

Phase 4 adds a backend-driven Leaflet geographic command center on top of the existing Phase 3 application. The original `CampusMap` remains available to the detailed legacy incident command view; the new `DisasterRiskMap` replaces the dashboard map and is also available from the Disaster Map navigation item. No second routing or WebSocket system was introduced.

## GIS architecture

`backend/services/map_overview.py` assembles a single normalized snapshot from persisted `RiskPredictionDB`, `ZoneDB`, `SensorObservationDB`, `IncidentDB`, `RescueRequestDB`, `CampusResourceDB`, `RouteDB` and `NotificationDB` records. `backend/api/map.py` exposes `/api/v1/map/overview` plus compatible layer endpoints. Backend filters support disaster type, risk level, region, zone, resource status, sensor status and alert status.

Leaflet was already an installed project dependency and its existing CSS/import conventions were reused. `DisasterRiskMap` keeps independent layer groups and updates their contents without reinitializing the map.

## Layers

The map provides toggles for Disaster Risk, Vulnerable Zones, Hazard Zones, Sensors, Incidents, Rescue Requests, Emergency Resources, and Safe/Blocked Routes plus geographic Tourist/Alert areas. Risk polygons use the actual Phase 2 risk score, level, confidence, freshness, evidence and data status. Vulnerability and hazard polygons use deterministic zone geometry when a trusted GIS polygon is not available and are labelled `DEMO/SIMULATION`.

Markers include persisted sensors, active incidents, rescue requests, shelters, hospitals, rescue teams, ambulances, vehicles and other emergency resources. Popups show the backend values, including sensor previous value/trend, resource status/capacity/assignment, incident status, and request priority.

## GeoJSON and safety

Zone, hazard and alert areas are serialized as validated GeoJSON polygons. Route rows are converted to GeoJSON LineStrings only when their persisted path contains valid coordinates or known existing road-graph nodes. The frontend has a DOM-free geometry validator and skips invalid geometry rather than crashing. Individual community records are not exposed as a separate exact-private layer; the map uses the existing zone-scoped alert model and operator-visible incident/resource data.

## Routes and affected areas

Routes are rendered from backend `RouteDB` results and retain `active`/safe versus `blocked` styling, distance, ETA, version and geometry source. The Nepal demo seeds clearly labelled safe and blocked demonstration route records so the flagship scenario can show both states without inventing frontend geometry. Critical risk and community alert records produce affected-area polygons and affected population totals from backend zone population.

## Realtime and geolocation

The App’s existing WebSocket is passed into the map through `liveEvents`. Sensor, anomaly, disaster, risk, resource, alert, travel and re-plan events trigger a consolidated map snapshot refresh; the map does not open another socket. The consent-based “Use my location” control uses one browser position request and displays a local marker. It does not continuously track a user.

## Nepal demonstration

After `POST /api/v1/sensor-simulations` with `nepal_mountain`, the map can focus on N-14 and show the backend-created critical flood/landslide risk, sensor markers for rainfall/river/soil/ground movement, high terrain vulnerability, a DEMO rescue team, mountain shelter, district emergency hospital, safe route, blocked route, community alert polygon and affected population. All seeded Nepal resources/routes and geometry are explicitly marked demo/simulation.

## Tests and validation

- Backend: **110 passed**.
- New Phase 4 backend tests: **3 passed**.
- Frontend: **94 passed**.
- New GeoJSON validator tests: **2 passed**.
- Frontend production build: **successful**.
- Python compilation: successful.
- FastAPI import and LangGraph initialization: successful.
- Existing legacy result remains **52 passed, 1 skipped, 1 known timing-related failure** in `test_api_analyze_incident_by_id`; no test was deleted or weakened.

## Known limitations

- Geometry outside the seeded/demo regions and the existing verified local road graph is not inferred. When no trusted route geometry exists, the backend returns no route.
- The base map uses public OpenStreetMap tiles and requires network connectivity; complete offline/PWA caching remains deferred.
- The map currently refreshes a consolidated snapshot after relevant realtime events rather than applying a server-side patch stream.
- Advanced GIS datasets, clustering for very large datasets, physical IoT integration and final production deployment changes remain later-phase work.
- Existing Google Generative AI deprecation and Vite large-chunk warnings remain unchanged.
