# Legacy Cleanup Report

## Scope

The repository was audited as a migration from the older Vignan/campus
complaint application to **AITAM Disaster Response AI — Disaster Prediction &
Community Response System**. No database reset, drop, destructive migration,
dependency change, framework change, or architecture rewrite was performed.

## 1. Legacy functionality identified

- Obsolete branding and campus-oriented copy remained in active UI, prompts,
  seed defaults, responder messages, and documentation.
- The old login profile/team-card implementation and image assets were present
  in the working migration and were confirmed as unrelated to the active
  disaster platform.
- An unused signup page and unused campus-map placeholder remained after the
  direct-to-command-center login change.
- A repository-wide audit found no active dedicated Vignan complaint router,
  complaint API, complaint service, complaint agent, complaint prompt,
  complaint database model, or complaint-only test suite.

## 2. Legacy functionality removed or rebranded

- Removed the unused `SignupPage` and `CampusMapPlaceholder` components.
- Confirmed the four obsolete login profile cards, team-card components, and
  four associated profile images are no longer imported or rendered.
- Removed the dead account-creation link to the deleted signup route.
- Rebranded active UI, assistant text, prompts, seed display names, responder
  messages, and current documentation to AITAM, Community, Department,
  emergency, and disaster-response terminology.
- Preserved the existing incident/report abstraction because it is the active
  disaster-report and event-fusion path, not a legacy complaint subsystem.

## 3. Legacy functionality preserved for compatibility

- FastAPI, React/Vite, LangGraph, deterministic risk engine, weather and
  environmental ingestion, sensors, map/GIS, resources, rescue, routing,
  alerts, approvals, monitoring, re-planning, tourist safety, WebSockets,
  authentication, and PWA/offline services were preserved.
- Internal role values such as `operator`, `user`, and `student`, endpoint
  names, database table names, `CampusResourceDB`, campus-location APIs, road
  graph identifiers, and telemetry/storage keys were retained where changing
  them would invalidate current data, tokens, or clients.

## 4. Vignan references removed

- Removed active Vignan-facing UI and seed/demo display references found in the
  audited files.
- `README.md` was rewritten as current AITAM documentation.
- Historical migration documentation remains allowed to mention the former
  project where it records migration history.
- The configured authentication secret, database filename, telemetry secret,
  and a few browser storage keys retain compatibility names. These are not
  user-facing functionality and were not changed because doing so would
  invalidate existing tokens, telemetry clients, or stored browser state.

## 5. Old assets removed

Removed from the active frontend working tree:

- `frontend/public/team/abdul-hafeez-batla.jpeg`
- `frontend/public/team/raju-kumar.jpeg`
- `frontend/public/team/rakesh-sai.png`
- `frontend/public/team/sonu.jpeg`
- `frontend/src/components/TeamGenAIShowcase.tsx`
- `frontend/src/components/teamGenAIData.ts`

Shared AITAM icons, map assets, manifest, service worker, and application
icons were preserved.

## 6. Old routes removed

No complaint-specific route existed in the audited router. The stale signup
page was removed; `/signup` remains a safe redirect to `/command` for old
bookmarks. Current `/command`, `/portal`, `/incidents`, `/map`,
`/travel-safety`, resource, sensor, alert, and department routes remain.

## 7. Old APIs removed

No dedicated complaint API was registered. Current incident, disaster-domain,
risk, weather, sensor, map, resource, routing, alert, approval, simulation,
agent-trace, and travel-safety APIs were retained and exercised.

## 8. Old agents removed

No complaint-only agent was found. Current supervisor, disaster analysis,
weather, risk, geo, hydrology, medical, rescue, security, infrastructure,
facilities, communication, resource, routing, monitoring, and recovery agents
were preserved.

## 9. Old prompts removed or updated

Active supervisor, communication, security, medical, transport, facilities,
fire, assistant, extraction, and response prompts were updated to describe
AITAM disaster response, communities, hazards, rescue, resources, warnings,
and emergency departments. Structured outputs and agent contracts were not
changed.

## 10. Old database elements handled

No complaint-only database model or table was found. Incident, community,
resource, sensor, risk, response-plan, assignment, route, alert, and auth
models were preserved. Compatibility-named campus tables and location
catalogs remain because current map, routing, resource, sensor, and rescue
flows use them.

No destructive database operation was executed.

## 11. Old seed/demo data handled

Future seed values were rebranded to AITAM/local demo identities and current
response-area names while retaining Nepal Mountain Region, N-14, sensors,
resources, shelters, hospitals, routes, and disaster scenarios.

Existing persisted rows were not deleted or rewritten. The local database may
therefore still contain historical display values from earlier seed runs; this
is recorded rather than removed destructively.

## 12. Authentication cleanup

- The visible login role choices are exactly `Community` and `Department`.
- Community continues to use the existing citizen/community-compatible auth
  flow; the backend role/API contract was preserved.
- Department authentication and routing were preserved.
- The old signup page/link was removed while auth APIs remain available for
  existing controlled provisioning flows.

## 13. Current functionality verified

The live backend at `http://127.0.0.1:8000` returned successful responses for
health, OpenAPI/docs, authentication, regions, zones, disasters, sensors,
sensor events, risk predictions, resources, shelters, hospitals, rescue
requests, map overview, alerts, travel safety, system status, and routing.

The frontend production bundle was served locally on port 5173 from
`frontend/dist`; its API client defaults to `http://127.0.0.1:8000` and no
Render URL is configured in the frontend source or environment files.

## 14. Nepal demo verified

Existing `nepal_mountain` sensor simulation completed successfully.

- Region/zone: `DEMO-NEPAL-MOUNTAIN` / `DEMO-N14`
- Sensor inputs: rainfall, river/water level, soil moisture, and ground
  movement
- Sensor events: created and marked detected/anomalous
- Disaster event: `DIS-20260828-EF31CE8C` (latest live run)
- Agent run: completed with all required specialist results
- Risk: deterministic `63.32/100`, `HIGH`, `100%` confidence, fresh evidence
- Resources: database-backed allocation including ambulances, boat, kit, and
  facility resources
- Routing: successful response-area graph route calculation
- Approval: response plan created with `approval_status: pending`
- Monitoring: active in the agent run; recovery remains standby
- Travel safety: current Nepal data returned `CRITICAL` recommendation based on
  current risk/alerts

The map overview also returned current N-14 risk/vulnerability layers,
including a critical risk record from the active demo data.

## 15. Test results

- Backend suite: **111 passed**, 4 warnings.
- Frontend suite: **96 passed** across 10 files.
- Root/legacy suite: **52 passed, 1 skipped, 1 known pre-existing failure**.
  The remaining failure is `tests/test_supervisor_agent.py::test_api_analyze_incident_by_id`, caused by the existing Gemini/event-loop
  fallback timing behavior and not by legacy cleanup.
- No tests were deleted or weakened. Two approval assertions were updated to
  the intentional current AITAM commander display label.

## 16. Build results

`npm.cmd run build` completed successfully. TypeScript compilation and Vite
production bundling both passed. Vite emitted only the existing large-chunk
warning for the command-center bundles.

## 17. Remaining legacy references

Remaining references are compatibility or historical only:

- Internal RBAC identifiers and function names containing `operator`.
- The database filename and telemetry/auth/storage compatibility keys using
  old project names.
- Historical migration documentation.
- Compatibility names such as campus location/resource APIs and graph source
  identifiers used by active disaster map/routing code.

The post-cleanup active-code/test search found **zero** `complaint` or
`complaints` matches under `backend`, `frontend/src`, and `tests`.

## 18. Known issues

1. The root legacy suite retains its known single supervisor timing failure and
   emits dependency/runtime warnings from the deprecated Gemini client and
   async gRPC cleanup.
2. The existing local database contains historical rows from earlier seeds;
   those rows were intentionally not deleted or rewritten without an explicit
   safe data-migration decision.
3. The local frontend dev dependency installation is incomplete for the Vite
   dev command in this worktree. The production build succeeds and the built
   frontend is available through the existing local static server on port 5173.

## Files created

- `LEGACY_CLEANUP_PLAN.md`
- `LEGACY_CLEANUP_REPORT.md`

## Files modified

The cleanup touched current branding, prompt, seed, compatibility-display,
auth-label, test-assertion, API-client, and documentation files across:

- `README.md`, `AGENT_ARCHITECTURE.md`, `.env.example`
- `backend/config.py`, `backend/database/seed.py`, backend API/model/service/
  agent files used by current response flows
- `backend/tests/conftest.py` and current auth, incident, assignment,
  transport, phase, and verification tests
- `frontend/src/pages`, `frontend/src/components`, `frontend/src/auth`,
  `frontend/src/services`, `frontend/src/portal`, `frontend/src/App.tsx`,
  `frontend/src/AppRoutes.tsx`, and frontend package metadata
- `tests/test_response_and_approval.py` for the intentional commander-label
  assertion update

The worktree was already dirty with Phase 1–5 additions and edits before this
cleanup; those existing current-platform changes were preserved.

## Files deleted

- `frontend/src/pages/SignupPage.tsx`
- `frontend/src/components/CampusMapPlaceholder.tsx`
- The four obsolete team/profile image files listed in section 5
- `frontend/src/components/TeamGenAIShowcase.tsx`
- `frontend/src/components/teamGenAIData.ts`

## Final assessment

The active application no longer exposes a Vignan/campus complaint system.
The current disaster-response APIs, agents, map, risk engine, resources,
approval gate, WebSocket event path, offline assets, authentication, and Nepal
sensor scenario remain connected and operational. The project is ready for a
local judge demonstration with the known legacy-suite timing failure and
non-destructive historical database rows documented above.
