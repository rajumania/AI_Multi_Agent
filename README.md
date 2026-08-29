# AITAM Disaster Response AI

### Disaster Prediction & Community Response System

AITAM Disaster Response AI is a FastAPI, React, SQLite, and LangGraph
platform for disaster intelligence and coordinated emergency response. It
combines community reports, environmental observations, weather, sensors,
deterministic risk scoring, geospatial layers, resource coordination, rescue
priorities, safe routing, alerts, human approval, monitoring, and re-planning.

## Active workflow

```text
Community report / sensor observation
        -> event fusion and anomaly detection
        -> Incident Commander / Supervisor
        -> parallel specialist agents
        -> deterministic risk and rescue priority
        -> resources, shelters, hospitals, and routing
        -> response plan
        -> human approval
        -> alerts, monitoring, and re-planning
```

The Nepal Mountain Region / N-14 deterministic scenario is included as a
clearly labelled demo. Demo records are not live emergency data.

## Main capabilities

- Community and Department authentication flows.
- Disaster incident and rescue-request intake with offline queue/sync support.
- Weather and environmental ingestion with early warnings and deterministic
  risk predictions.
- LangGraph supervisor orchestration with parallel specialist agents and
  bounded failure handling.
- Interactive risk map with vulnerability, sensor, incident, resource,
  hospital, shelter, route, and alert layers.
- Database-backed resource assignment, dispatch, approval, notifications,
  monitoring, travel safety, and WebSocket updates.

## Local setup

From the repository root:

```powershell
python -m uvicorn backend.main:app --reload --port 8000
```

In another terminal:

```powershell
cd frontend
npm run dev
```

The API documentation is available at `http://localhost:8000/docs`. The
frontend uses `VITE_API_BASE_URL` when supplied and otherwise targets the
local backend at `http://127.0.0.1:8000`.

## Verification

```powershell
python -m pytest -q
cd frontend
npm test -- --run
npm run build
```

The test suites use disposable databases where configured. Do not reset or
drop the local/deployed database to run verification.

## Project documentation

- `AGENT_ARCHITECTURE.md` — active LangGraph and specialist-agent design.
- `MIGRATION_PLAN.md` — migration history and remaining implementation notes.
- `PHASE_1_REPORT.md` through `PHASE_5_REPORT.md` — phase reports, including
  historical migration context where applicable.
- `LEGACY_CLEANUP_PLAN.md` and `LEGACY_CLEANUP_REPORT.md` — legacy audit and
  cleanup record.
