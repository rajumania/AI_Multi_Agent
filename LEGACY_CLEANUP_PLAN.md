# Legacy Cleanup Plan

## Scope and safety boundary

This audit separates the retired Vignan/campus complaint semantics from the
active AITAM disaster-response platform. Current incident/disaster-report
flows, authentication APIs, database compatibility names, geospatial
location catalogs, resource coordination, LangGraph orchestration, and
offline/WebSocket infrastructure are in scope for preservation unless a
candidate is proven to be complaint-only.

No database reset, drop, destructive migration, dependency change, or
architecture change is planned.

## Inventory and classification

| Area | Candidate / evidence | Classification | Action boundary |
|---|---|---:|---|
| Legacy Vignan UI | Vignan/CampusFlow branding, campus complaint-era wording, old signup role labels, and old command-briefing text in active UI | REFACTOR | Update current-facing labels to AITAM, Community, Department, disaster, emergency, and response terminology. Preserve page behavior and auth calls. |
| Legacy profile cards/assets | Four old login profile cards and their four team images/components were already removed in the existing worktree | REMOVE | Confirm no active imports or rendered references remain. Do not remove shared icons/map assets. |
| Legacy frontend routes | Repository route audit found no `/complaints`, `/student-complaints`, `/campus-complaints`, or complaint-management route. `/portal` is the active community disaster portal. | PRESERVE | Keep current routes; do not remove `/portal`, `/incidents`, `/map`, or report flows because their names represent current disaster functionality. |
| Legacy complaint APIs | Repository-wide complaint search found no dedicated complaint router or complaint endpoint. `incidents.py` and disaster-domain report APIs are active current APIs. | PRESERVE | Keep incident/report endpoints and verify no complaint-only registration exists. |
| Legacy complaint services | No complaint-only service was found. `llm_service.py`, severity, event, response, routing, and simulation services support current disaster workflows, although some text is legacy-branded. | REFACTOR | Remove only obsolete brand/campus complaint semantics from user-facing prompts and explanations; preserve deterministic behavior and service contracts. |
| Legacy complaint agents | No complaint-only agent was found. Agents in `backend/agents` are weather/geo/risk/medical/rescue/security/infrastructure/facilities/communication/supervisor or current compatibility agents. | PRESERVE | Keep all agents and LangGraph imports; verify fan-out, results, and failure handling. |
| Legacy complaint prompts | Active assistant/extraction prompts contain CampusFlow/Vignan/campus wording. | REFACTOR | Reword prompts to AITAM disaster response and community safety without changing structured outputs or extraction behavior. |
| Database models | No explicit complaint-only model/table was found. `IncidentDB`, `CommunityDB`, resources, sensors, risk, responses, assignments, routes, alerts, and auth tables are current. `CampusResourceDB` and `campus_resources` are compatibility names used by current map/resource code. | PRESERVE | Do not delete or rename models/tables. Document any obsolete persisted seed values; do not mutate deployed data. |
| Seed/demo data | Seed data contains old Vignan resource names/emails and current disaster-domain data including Nepal Mountain Region/N-14. | REFACTOR | Preserve rows, IDs, coordinates, auth compatibility, and Nepal scenario. Update only safe future-seed display text if dependency-safe; do not rewrite or delete existing DB rows. |
| Legacy assets/images | Old login team images are deleted in the existing worktree. No other asset is proven to be legacy-only without usage tracing. | REMOVE / PRESERVE | Keep shared AITAM icons, PWA assets, map imagery, and UI icons. Confirm deleted team assets are not imported. |
| Legacy tests | No complaint-only test files or test paths were found in the initial search. Existing auth, incident, transport, risk, map, agent, offline, and simulation tests cover current behavior. | PRESERVE | Do not delete tests. Update only assertions that intentionally describe a changed current-facing label, if needed. |
| Legacy documentation | `README.md` is current-facing CampusFlow/Vignan documentation. Phase reports and migration history may legitimately describe the migration. | REFACTOR | Rewrite current README/active architecture wording for AITAM; retain historical migration records where they explain history and do not present legacy functionality as active. |
| Shared campus/location infrastructure | `campus_locations`, `CampusMap`, local road graph, MCP resource tools, campus resource table, and campus-named compatibility fields are used by the active map, routing, resources, sensors, and rescue flows. | PRESERVE | Do not delete or blindly rename. Reword visible descriptions only where safe. |
| Authentication compatibility | Backend `operator`/`user` values, seeded accounts, department auth, and frontend auth guards are active compatibility behavior. | PRESERVE / REFACTOR | Keep internal role values and APIs. User-facing login terminology remains Community/Department; do not invalidate existing tokens or accounts. |

## Verification plan

1. Re-scan for Vignan/campus/student/operator/complaint references and review
   each remaining active-code occurrence individually.
2. Confirm no obsolete complaint navigation, router, model, agent, prompt, or
   asset import remains.
3. Run backend tests and frontend tests without weakening coverage.
4. Run the production frontend build.
5. Exercise health, API registration, database-backed domain queries,
   WebSocket connection, Nepal sensor simulation, LangGraph trace, risk,
   resources, routing, approval pause, alerts, travel safety, and offline/PWA
   checks using existing endpoints and data.
6. Record any unresolved internal compatibility or historical references in
   `LEGACY_CLEANUP_REPORT.md` rather than making unsafe destructive changes.
