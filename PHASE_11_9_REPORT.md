# PHASE 11.9 — Real-Time In-App Department Notifications

## Status

**PHASE 11.9 STATUS: COMPLETE**

The existing notification table, authenticated `/api/v1/events/ws` stream,
RBAC visibility rules, assignment lifecycle, portals, monitoring event stream,
and 3D Command Center were extended in place. SMS and email were not added.

## Notification architecture

- Operational notifications are created by the existing approved-response
  assignment path in `assignment_service.py`.
- A notification is created only after the response plan is approved by an
  authorized operator/department approver. Community users cannot approve or
  dispatch.
- Department rows use the existing canonical department codes and are scoped
  by the server to the matching department. Admin receives separate
  `recipient_type=admin` operational rows, so it does not receive duplicate
  department rows through the department stream.
- Each row now has `priority`, `lifecycle_status`, `delivered_at`, `read_at`,
  an idempotent `event_key`, and safe structured `details_json`.
- `event_key` is protected by a unique SQLite index. Repeated approval or
  assignment processing does not create duplicate notifications.
- The REST notification feed remains the durable source of truth. The UI
  reconciles it on socket connect/reconnect and refreshes after lifecycle
  events without reloading the application.

## Department targeting

The existing evidence-based `required_departments`/department recommendation
path remains authoritative. Notifications are emitted only for the resulting
assignments; the implementation does not broadcast every incident to all
departments. Each notification includes the targeting reason and confidence
when available, along with the incident's exact latitude/longitude, location
label, hazard, severity, risk metadata, approval state, response state, and
safe evidence summary.

## WebSocket delivery and lifecycle

The existing authenticated endpoint remains:

`/api/v1/events/ws?token=<backend-issued-token>`

Supported lifecycle states are `CREATED`, `DELIVERED`, `READ`, and `FAILED`.

- `notification_created` is emitted only for the authorized recipient stream.
- A department/admin/community socket sends a delivery acknowledgement only
  after its portal receives the notification frame.
- The server validates that acknowledgement against the authenticated socket
  scope before setting `DELIVERED`.
- A failed socket send can set `FAILED`; the server never treats a failed send
  as delivered.
- Read and mark-all-read operations persist `READ`/`read_at` and emit the real
  `notification_read` event.
- A disconnected department retains its persisted unread row and receives it
  from REST synchronization after reconnect. No new row is generated merely
  because a socket reconnects.

Event names are included in the existing event broadcast/visibility policy,
including `notification_created`, `notification_delivered`,
`notification_read`, `notification_failed`, `department_tasks_dispatched`,
and the existing assignment/monitoring events.

## Portal behavior

The existing notification bell now shows up to 20 persisted history entries,
unread count, severity/priority, department, incident, lifecycle state,
timestamp, and expandable operational details. It supports individual and
mark-all read actions.

- Department portals receive only their own department notifications and
  refresh immediately from the existing socket.
- Admin sees the admin operational stream and all targeted department context
  contained in those rows.
- Community users see only their own user notifications/public-safe audience;
  internal department notes, approval details, responder data, and credentials
  are not exposed.
- The existing 3D Command Center consumes the same live lifecycle event stream;
  no timer-generated notification or agent animation was introduced.
- Monitoring and re-planning continue to use the existing real backend event
  stream. No new SMS/email path was created.

## RBAC verification

Isolated tests and live API checks verified:

- Medical sees only `MEDICAL` department rows.
- Security sees only `SECURITY` department rows.
- Admin sees `recipient_type=admin` operational rows.
- Community sees user/public-safe rows, not department rows.
- A wrong department cannot acknowledge or receive another department's
  notification event.
- Guest/invalid WebSocket scopes receive no events.
- Existing approval restrictions remain in force.

## Controlled end-to-end validation

The controlled Himalayan landslide scenario used exact coordinates
`27.9881, 86.9250` and was executed in the isolated pytest database. It
verified the existing approved-assignment path, exact-coordinate notification
metadata, department targeting, idempotency, delivery authorization, and
department event isolation. It was explicitly a controlled test and did not
assert that a real landslide existed or insert a record into the operational
`campusflow.db`.

The live application was verified read-only with the existing accounts and
current operational data. No permanent test incident, notification, or
assignment was created in the authoritative database.

## Database safety

Only `campusflow.db` was used. Before each live backend restart/migration a
timestamped backup was made. The latest relevant backup is:

`campusflow_pre_phase11_9_restart_20260829_050816.db`

Counts before and after the final additive migration/restart were unchanged:

| Table | Before | After |
|---|---:|---:|
| incidents | 56 | 56 |
| notifications | 178 | 178 |
| department_responses | 24 | 24 |
| response_plans | 84 | 84 |
| agent_events | 0 | 0 |

The final `PRAGMA foreign_key_check` returned no rows. `aitam.db` does not
exist. No operational data was reset, dropped, renamed, or seeded again.

## Local verification

- Backend: `http://127.0.0.1:8000` — `/health` returned HTTP 200.
- Frontend: `http://127.0.0.1:5173` — returned HTTP 200.
- Authenticated department WebSocket connected successfully, accepted the
  existing client protocol, remained open during the check, and closed cleanly.
- Live notification REST responses included the new lifecycle, priority,
  delivery/read timestamps, and safe details fields.

Interactive browser automation was not available in this execution
environment; the browser-facing frontend was served and production-built,
while the notification socket/RBAC behavior was verified through the running
API and isolated backend tests.

## Validation results

- Backend tests: **140 passed**.
- Phase 11.9 focused tests: **4 passed** in the final focused run, including
  idempotency, exact-coordinate details, delivery authorization, and event
  isolation.
- Frontend tests: **96 passed**.
- `python -m compileall -q backend`: passed.
- `git diff --check`: passed; Git emitted only existing LF/CRLF normalization
  warnings.
- `npm run build`: passed; Vite completed the production build. It reports the
  existing large-chunk advisory only.

## Remaining limitations

- This phase intentionally does not implement SMS or email.
- Vision analysis remains governed by the Phase 11.8 backend-only provider
  boundary and is unavailable when no vision credential is configured; it is
  not used to fabricate an operational notification.
- Real deployment still requires production WebSocket infrastructure,
  credential rotation, HTTPS, and operational monitoring/retention policy.
- The controlled end-to-end test is isolated from production operational data;
  live dispatch remains subject to the existing human approval and physical
  responder infrastructure.

No Phase 12 work was started.
