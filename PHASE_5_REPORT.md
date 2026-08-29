# Phase 5 Report — Offline and Low-Connectivity Safety

## Status and scope

Phase 5 implements the previously deferred offline behavior without changing
the existing API contracts or realtime socket. The app now gives users an
honest offline state, preserves safe map snapshots locally, queues emergency
reports for replay, and prevents duplicate reports when a reconnect happens
after an ambiguous network response.

## Offline data and submission behavior

`frontend/src/services/offlineStore.ts` uses IndexedDB for timestamped map
snapshots and queued incident operations, with a local-storage fallback for
browsers where IndexedDB is unavailable. Only structured map data is cached;
external map tiles and API responses are not silently cached by the service
worker. Cached map data is labelled `CACHED / STALE` and includes its saved
timestamp.

If an emergency POST fails because of a network failure, the report modal
stores the complete validated payload with a client-generated operation ID and
shows `REPORT SAVED OFFLINE`. The queue retries automatically on the browser's
`online` event and can also be synced manually. HTTP validation/auth failures
are not treated as offline failures.

The backend persists the operation ID on `IncidentDB` and creates a nullable
unique index through the additive migration. Replaying the same operation
returns the original incident, including after a server-side commit succeeded
but the response was lost. Existing records and direct internal callers remain
compatible.

## PWA shell

The production frontend now includes `manifest.webmanifest`, install icons,
and a service worker. The worker caches the application shell and navigation
fallback only. It deliberately excludes `/api/*` and external map tiles so
stale operational data cannot masquerade as a live response.

`OfflineStatus` is shown in both the operator and citizen shells. It reports
either `Offline — showing saved data` or the number of queued reports waiting
to synchronize. The browser location control remains consent-based and is not
used as a background tracker.

## Demo-data boundary

The generic `/api/v1/resources` endpoint now excludes explicitly labelled
Nepal demonstration resources by default, with `include_demo=true` available
for an intentional opt-in. The Phase 4 consolidated disaster map continues to
show those assets with their `DEMO/SIMULATION` provenance.

## Validation

- Backend: **111 passed**.
- New offline idempotency backend test: **passed**.
- Frontend: **96 passed**.
- New offline safeguard tests: **2 passed**.
- Frontend production build: **successful**; manifest, service worker, and
  install icons are emitted in `frontend/dist`.
- Python compilation and `git diff --check`: **successful**.
- Legacy suite: **52 passed, 1 skipped, 1 known timing-related failure** in
  `tests/test_supervisor_agent.py::test_api_analyze_incident_by_id`, unchanged
  from the prior phases. The failure is caused by the existing automatic
  background pipeline racing the explicit analysis assertion.

## Remaining limitations

- Offline reports remain pending until a backend connection is available;
  physical dispatch and approvals never occur locally.
- External OpenStreetMap tiles are not available offline; the cached map
  snapshot still renders its records, but the basemap may be blank.
- Queue replay currently retries failed server responses and records attempt
  metadata locally; durable cross-device sync and operator reconciliation are
  future deployment work.
