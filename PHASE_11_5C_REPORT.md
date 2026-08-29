# Phase 11.5C — Production Organization + Real Emergency Operations

Date: 2026-08-29  
Status: **PARTIAL — locally runnable and verified, not production-ready**

This phase did not reset or replace the authoritative database. `campusflow.db`
remains authoritative. No `aitam.db` was created.

## Local application

- Backend: `http://127.0.0.1:8000` — running FastAPI/Uvicorn; `/health` and
  `/api/v1/system/status` returned HTTP 200.
- Frontend: `http://127.0.0.1:5173` — running Vite development server.
- Browser: visible local Chrome controlled through its normal browser CDP
  interface. The rendered application was checked at `/command`,
  `/command/departments`, `/portal`, `/dept/SECURITY`, `/dept/MEDICAL`, and
  `/dept/SEARCH_AND_RESCUE`.
- Browser console: no `Runtime.exceptionThrown` or `Log.entryAdded` errors were
  observed during the route checks. The rendered pages were non-blank.

## Organization administration

The existing privileged `operator` authentication role is the authoritative
AITAM Organization Admin capability; no parallel authentication architecture
was introduced. Admin-only organization APIs and the Admin Department
Management page now support:

- one persisted AITAM organization;
- create/edit and activate/deactivate department records;
- department code, name, type, and description;
- create department staff accounts using the existing hash mechanism;
- reset password, deactivate/reactivate, and edit department accounts;
- assign existing users to a department;
- department status, account counts, active incidents, and resource counts.

The eight persisted active departments are Medical, Search & Rescue, Fire,
Security / Public Safety, Transport, Communication, Infrastructure /
Facilities, and Shelter. No duplicate department codes or department account
emails were found.

A temporary department and account were created, deactivated, and removed from
the database during verification. They were isolated verification records and
were not retained.

## Authentication and RBAC

- Admin login: verified with the documented local credential.
- Community login: verified; the Community portal rendered in Chrome.
- Security, Medical, Search & Rescue, Fire, Transport, Communication,
  Facilities, and Shelter department logins: all returned HTTP 200 using the
  documented credentials.
- Community access to approval operations: HTTP 403.
- Department resources, incidents, response plans, assignments, and telemetry
  are scoped to the authenticated department. Cross-department access is
  denied by backend dependencies.
- Passwords are hashed with the existing authentication service. Passwords and
  hashes are not returned by organization APIs.

## Community emergency reporting

The Community emergency modal supports description, category, timestamp,
manual location selection, browser geolocation, exact latitude/longitude
confirmation, and an evidence reference. Browser geolocation uses the actual
`navigator.geolocation` result with high accuracy requested; it does not
substitute Guntur, Nepal, or a fixed fallback coordinate. The current Chrome
session reported GPS as offline, so physical browser GPS permission was not
available for this run.

Binary photo storage is not available in the existing architecture. The UI
therefore does not claim an upload: it preserves a clearly labelled local
evidence reference only.

A controlled AITAM-coordinate emergency was submitted through the running
backend, enriched, moved to `awaiting_approval`, given a response plan, approved
by the Admin, and routed to targeted departments. Temporary incident data and
its dependent audit/notification rows were removed afterward.

## Emergency processing and dispatch

The verified controlled flow was:

`Community report → classification/enrichment → event fusion → LangGraph
workflow → specialist agents → risk/priority/resources → response plan →
human approval → department assignments/notifications`

Approval remains human-controlled. Community users cannot approve plans. On
approval, only departments selected from the incident disaster type and risk
routing policy receive durable department assignments and notifications. The
controlled AITAM flow produced targeted assignments for Communication,
Facilities, Fire, Medical, Security, and Transport; it did not broadcast to
all departments.

The existing WebSocket event system received the workflow and dispatch events.
The UI reported one connected `/api/v1/events/ws` channel; no duplicate map
socket was observed in the browser route checks.

## Department operations

Department portals rendered successfully in Chrome for Security, Medical, and
Search & Rescue. The portals load scoped incident feeds, alerts, sensor data,
rescue requests, shelters/hospitals, monitoring, and assignment controls.
Backend verification covered department login, scoped incident visibility,
targeted assignment creation, and department lifecycle transition tests.

## 3D command center and Tourist Safety

- The Admin command shell rendered the 3D Command Center route with backend,
  database, WebSocket, LangGraph, MCP, and response-planning status.
- The command shell exposes provider, event, telemetry, risk, route, and agent
  lifecycle data from backend state. Simulation controls are explicitly
  labelled as digital-twin/demo behavior and are not presented as physical
  dispatch.
- Tourist Safety uses backend safety data. The configured N-14 simulation
  location returned a backend `NOT_RECOMMENDED` result with critical risk; no
  Nepal safety result is hardcoded.

## Providers and hardware status

Provider results below are from the running backend, not frontend-private
provider calls:

| Provider | Result | Notes |
|---|---|---|
| Open-Meteo | FALLBACK | Provider request failed in this run; stored/demo observation was shown with fallback/source metadata. |
| USGS | OFFLINE | `/api/v1/earthquakes/recent` returned HTTP 503; no earthquake was fabricated. |
| OSRM | READY / not promoted to LIVE | Configured adapter and fallback route validation are present; no successful live OSRM route was claimed in this run. |
| IoT HTTP gateway | NOT CONFIGURED | Gateway API architecture exists; no physical sensor connection is claimed. |

The application distinguishes provider readiness from successful live
observations. Demo/N-14 fixtures remain explicitly marked as demo/simulation
data. Physical IoT hardware, SMS, push, telephony, and external dispatch are
not connected.

## Location and legacy audit

The active institutional anchor is AITAM, Tekkali, Srikakulam, Andhra Pradesh,
India. The project uses `18.56517, 84.19587` as the verified institutional
anchor, based on the official AITAM location source:
[AITAM official location PDF](https://adityatekkali.edu.in/Files/naac/2024/c5/5.1/5.1.3/b/ss/s7.pdf).

Legacy campus fixture offsets used by the routing/resource compatibility layer
are projected onto that anchor at runtime. User-submitted coordinates and
Nepal/N-14 coordinates are not rewritten. The two clearly unwanted active
Guntur incident records found by the real Chrome audit were removed with their
six audit rows and four notifications. No Guntur incident or resource text
remains in the authoritative active records. Demo zones remain retained and
clearly marked as demo fixtures because they support existing tests and
disaster-data architecture.

## Database safety and counts

Backups created before current-phase mutations include:

- `campusflow_pre_phase11_5c_20260829_013051.db`
- `campusflow_pre_phase11_5c_cleanup_20260829_015834.db`
- `campusflow_pre_phase11_5c_identity_cleanup_20260829_021134.db`

The first backup is the current-phase baseline. `organizations` and
`organization_departments` were additive tables created during this phase, so
their baseline is shown as `—`.

| Table | Before | Removed | After | Reason |
|---|---:|---:|---:|---|
| users | 11 | 0 | 11 | Preserve authentication users |
| department_users | 13 | 0 | 14 | Added Shelter account |
| regions | 2 | 0 | 2 | Preserve disaster regions |
| zones | 3 | 0 | 3 | Preserve demo/N-14 fixtures |
| incidents | 57 | 2 | 55 | Remove two exact legacy Guntur incidents |
| sensor_observations | 28 | 0 | 28 | Preserve sensor fixtures |
| sensor_events | 28 | 0 | 28 | Preserve sensor events |
| risk_predictions | 18 | 0 | 18 | Preserve risk history |
| campus_resources | 24 | 0 | 24 | Preserve operational resources |
| rescue_requests | 1 | 0 | 1 | Preserve rescue data |
| routes | 2 | 0 | 2 | Preserve route data |
| notifications | 180 | 4 | 176 | Remove notifications for those two incidents |
| response_plans | 84 | 0 | 84 | Preserve response plans |
| agent_runs | 15 | 0 | 15 | Preserve agent/audit data |
| department_responses | 24 | 0 | 24 | Preserve department response data |
| audit_logs | 861 | 6 | 855 | Remove audit rows for those two incidents |
| organizations | — | 0 | 1 | Additive AITAM organization registry |
| organization_departments | — | 0 | 8 | Additive authoritative department registry |

Final `PRAGMA foreign_key_check` returned no rows. Duplicate username,
duplicate user email, duplicate department account email, and duplicate
department code checks returned no duplicates.

## Tests and build

- Backend: `127 passed, 2 warnings` (`python -m pytest backend/tests -q`).
- Compile: `python -m compileall -q backend` passed.
- Frontend: `96 passed` across 10 Vitest files.
- Frontend production build: passed; Vite emitted only the existing large-chunk
  warning (approximately 508 KB and 630 KB minified chunks).
- `git diff --check`: passed; only Git line-ending normalization warnings were
  emitted.

## Security and remaining limitations

- `.env` is ignored and not tracked; no credential values were printed or
  returned by the organization API.
- Existing authentication/RBAC architecture was preserved.
- The local demo credentials are documented in `DEMO_CREDENTIALS.md` and are
  for hackathon/local testing only.
- Photo binary persistence is not implemented; only an honest evidence
  reference is retained.
- External Open-Meteo and USGS availability was not present during this run;
  they must be rechecked in the deployment environment.
- A successful live OSRM call was not available to promote route status to
  LIVE; fallback route geometry remains explicitly labelled.
- No physical IoT hardware is connected. The system is **IOT GATEWAY READY**,
  not **PHYSICAL SENSOR CONNECTED**.
- Offline/PWA shell and queue code are present and covered by tests, but full
  service-worker/reconnect behavior was not exhaustively verified in Chrome.
- The current existing password-hashing implementation and local demo
  credentials require production security review/rotation before deployment.

This report stops at Phase 11.5C. No deployment was performed and Phase 11 was
not started.
