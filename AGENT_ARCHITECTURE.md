# Phase 3 Agent Architecture

The active AITAM LangGraph application combines typed disaster intelligence
with the existing incident workflow for backward compatibility. Community
reports and sensor anomalies enter the same Phase 3 workflow after
normalization.

```text
Human report / community request       Sensor observation / anomaly
              \                              /
               +---- Event Ingestion -------+
                         |
                    Supervisor
             Incident Commander / router
                         |
       conditional LangGraph Send fan-out (parallel)
     +---------+---------+---------+---------+---------+
     | Weather | Geo     | Risk    | Hydro   | Medical |
     | Analysis| Vuln.  | Analysis| Env.    | Triage  |
     +---------+---------+---------+---------+---------+
     | Rescue  | Security | Infrastructure | Shelter |
     | Search  | Safety    |                | Hospital|
     +---------+---------+---------+---------+---------+
                         |
                  Situation State
                         |
       Resource coordination -> Priority scoring
                         |
              Deterministic safe routing
                         |
                  Response Planner
                         |
                   Human Approval
                         |
             Approved alert / dispatch path
                         |
                 Monitoring + Recovery
                         |
                 Re-planning when state changes
```

## Execution model

The Supervisor selects specialists by disaster type. Independent specialists are fanned out with LangGraph `Send` and converge at `situation_state`; the operational stages then run in a deliberate order because resource selection, priority, routing and planning consume earlier outputs. The approval gate never dispatches a real-world action by itself.

The shared `DisasterIntelligenceState` carries event source, disaster context, weather/environment/sensor/geographic evidence, community reports, risk, resources, rescue requests, priorities, routes, plan, alerts, approval status, travel safety, agent results/errors and audit events. Each specialist returns only its evidence-bound section; numerical risk and rescue priority remain deterministic services.

## Agent responsibilities

| Component | Responsibility |
|---|---|
| Supervisor / Incident Commander | Classifies context and conditionally selects specialists |
| Disaster Analysis | Summarizes normalized hazard evidence |
| Weather Analysis | Interprets latest weather observations |
| Risk Prediction | Carries Phase 2 deterministic score and evidence |
| Geo-Vulnerability | Interprets elevation, slope, exposure and hazard class |
| Hydrology / Environmental | Interprets water, soil, drainage and ground signals |
| Medical / Triage | Identifies medical response needs from requests |
| Search & Rescue | Assesses rescue urgency and access needs |
| Security / Public Safety | Recommends safety/access-control considerations |
| Infrastructure | Flags infrastructure and route concerns |
| Resource | Queries database-backed resources, shelters and hospitals |
| Rescue Priority | Applies deterministic priority engine to open requests |
| Routing | Applies existing road graph only where verified geometry exists |
| Shelter / Hospital | Consumes database capacity results |
| Response Planner | Creates an existing approval-gated response plan |
| Communication | Drafts evidence-bound warning/communication recommendations |
| Monitoring | Records continued observation readiness |
| Recovery | Records post-threat recovery readiness |
| Travel Safety | Produces destination guidance from risk/alert/weather evidence |

Existing Medical, Security, Transport, Facilities and Communication agents were preserved. Phase 3 specialist outputs are additive and do not replace the existing incident graph.

## Geographic command-center connection

The Phase 4 map consumes the consolidated backend snapshot produced from agent and operational state:

```text
Agents -> persisted risk / geo evidence -> map overview
      -> database resources / rescue priorities -> resource layers
      -> deterministic routing -> safe and blocked route layers
      -> approved alerts -> geographic alert areas
      -> existing WebSocket event stream -> incremental map refresh
```

The map does not calculate risk, priority, distance or routes. It renders backend results and rejects malformed GeoJSON before handing geometry to Leaflet.
