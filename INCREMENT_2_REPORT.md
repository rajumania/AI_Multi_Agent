# CampusFlow AI — Increment 2 Report
## Frontend Authentication + Role-Based Portals

**Scope:** Add a login-first flow and role-based portals on top of the EXISTING
CampusFlow AI system, without rebuilding it. The working operator command center,
LangGraph orchestration, agents, resources, WebSocket, GPS/telemetry, voice
alerts, response plans, dispatch, and database all remain intact and are reached
unchanged at a new protected route.

> **Verification honesty note:** This environment (Linux sandbox) has insufficient
> disk to run `npm`, `vite`, `tsc`, `pytest`, or a browser, so I could **not**
> execute the build or the test suites here. Everything below marked "to run" must
> be run in your Windows venv / Node toolchain. I have done a thorough **static**
> verification (imports, exports, type contracts, backend/response shapes, icon
> exports, CSS classes) and report exactly what was and was not executed. I am
> **not** claiming any test or build passed.

---

## A. Files changed

### New — frontend (Increment 2)

| File | Purpose |
|------|---------|
| `frontend/src/auth/roles.ts` | Pure, DOM-free source of truth for role/department logic: role & department constants (mirrors the backend), `homePathFor`, `canAccessDepartmentPortal`, `canAccessCitizenPortal`, `canAccessCommandCenter`, `normalizeDepartment`, display helpers. |
| `frontend/src/auth/roles.test.ts` | Vitest unit tests for the above (cross-department isolation, role→portal mapping, guards). |
| `frontend/src/auth/AuthContext.tsx` | Single owner of session state. Bootstraps by validating any stored token against `GET /auth/me`; login helpers for the three real backend flows + citizen registration; logout; registers the 401 handler. |
| `frontend/src/auth/ProtectedRoute.tsx` | Client route guard: loader while validating, redirect to `/login` when unauthenticated, redirect to the caller's own home when not permitted. |
| `frontend/src/AppRoutes.tsx` | The single ROLE→PORTAL routing table (`/login`, `/signup`, `/command`, `/portal`, `/dept/:department`, `/`, `*`). |
| `frontend/src/pages/CitizenPortal.tsx` | Citizen portal: report via the existing modal, own-incidents feed, simplified agent-free progress, labeled notification/chatbot previews. |
| `frontend/src/pages/DepartmentPortal.tsx` | One parameterized portal for all six departments: scoped responder feed + identity indicator. No operator command controls. |
| `frontend/src/components/PortalHeader.tsx` | Minimal identity header (Name, Role, Department, Sign Out) for citizen/department portals. Deliberately excludes the operator service-status board. |
| `frontend/src/portal/incidentProgress.ts` | Pure, DOM-free mapping from incident `status` → a 5-phase citizen-safe timeline. Emits no agent internals. |
| `frontend/src/portal/incidentProgress.test.ts` | Vitest tests for the progress mapping (incl. an assertion that labels never contain agent/internal terms). |

### Modified — frontend

| File | Change |
|------|--------|
| `frontend/package.json` | Added dependency `react-router-dom ^6.26.2`. **Requires `npm install`.** |
| `frontend/src/main.tsx` | Wrapped the app in `<BrowserRouter><AuthProvider><AppRoutes/>`; kept `index.css` + Leaflet CSS imports. |
| `frontend/src/App.tsx` | Header now shows the authenticated user and a working logout; **all** dashboard logic (WebSocket, telemetry, workflow, modal, tabs, voice) is unchanged. |
| `frontend/src/pages/LoginPage.tsx` | Rewritten into a multi-mode login (Operator / Campus Member / Department) that authenticates against the **existing** backend auth APIs and routes by server-verified role. No fake frontend-only auth. |
| `frontend/src/pages/SignupPage.tsx` | Uses router navigation instead of callback props (operator/student self-registration preserved). |
| `frontend/src/services/api.ts` | Added a 401 interceptor (`setUnauthorizedHandler`) that fires only for tokened, non-auth endpoints; `clearAuthToken` now also clears the cached user. Token plumbing otherwise unchanged (still backward-compatible/anonymous when no token). |
| `frontend/src/index.css` | Appended two additive utility classes (`.spin`, `.pulse`) with uniquely-named keyframes. Also fixes the previously-static spinner referenced by `.spin` elsewhere. |

### Backend (the approved "minimal data scoping" for Increment 2)

| File | Change |
|------|--------|
| `backend/api/incidents.py` | `GET /incidents` list and `GET /incidents/{id}` are scoped by the verified principal (citizen → own only; department → routed departments only; operator/admin/anonymous-compat → all). Out-of-scope detail returns **404** (no existence disclosure). Response schema exposes no ownership/routing internals. |
| `backend/tests/test_incident_scoping.py` | New RBAC tests for list + detail scoping across citizen/department/operator. |

---

## B. Authentication flow

1. **First page is Login.** An unauthenticated visit to `/` (or any unknown path)
   resolves through `homePathFor(null) === '/login'`. `/login` and `/signup` are
   the only public routes.
2. **Real backend auth.** The login page calls the existing APIs through
   `AuthContext`:
   - Operator/Admin → `POST /api/v1/auth/login` (username + password)
   - Campus Member → `POST /api/v1/auth/user/login` or `/user/register` (email + phone)
   - Department → `POST /api/v1/auth/department/login` (email + password + department)
   There is **no** frontend-only/fake authentication; the token is issued and
   signed by the backend.
3. **Server-verified identity.** After a successful login the context calls
   `GET /api/v1/auth/me` and uses that server-verified principal (role +
   department) as the source of truth — not any client-supplied value.
4. **Token storage.** The signed token is stored in `localStorage` (`cf_token`,
   the key the API layer already used) and attached to every REST request and the
   events WebSocket. A display copy of the user is cached in `cf_user` but is
   always re-validated against `/me` on reload.
5. **Route to the correct portal** via `homePathFor(user)` (see mapping below).
6. **Logout** clears the token + cached user and returns to `/login`.
7. **Expired/invalid token.** Any tokened request that returns **401** triggers a
   session teardown and a redirect to `/login` with a "session expired" notice.
8. **Bootstrap.** On page load, a stored token is validated once against `/me`;
   if rejected, the session is cleared.

---

## C. Role → portal mapping

| Backend role | `homePathFor` | Portal | Notes |
|---|---|---|---|
| `admin` | `/command` | Existing command-center dashboard | Rendered by the unchanged `App`. |
| `operator` | `/command` | Existing command-center dashboard | Rendered by the unchanged `App`. |
| `user` (citizen) | `/portal` | Citizen Emergency Portal | Report + own incidents + simplified progress. |
| `department` / `department_head` (SECURITY) | `/dept/SECURITY` | Department Portal (Security) | Scoped feed only. |
| …MEDICAL / TRANSPORT / COMMUNICATION / FIRE / FACILITIES | `/dept/<CODE>` | Department Portal | Same component, parameterized by department. |

The frontend role/department constants in `roles.ts` were verified against the
backend (`backend/services/auth_service.py`: `admin`/`operator`/`user`/
`department`/`department_head`; `backend/services/departments.py`: the six
UPPERCASE department codes). The backend `/me` and department-login responses
return the department as a normalized UPPERCASE code and a `department_label`,
which is exactly what the frontend expects.

### Protected routes / cross-portal isolation (defense in depth)

- **Navigation guard.** `/command` requires `canAccessCommandCenter` (privileged
  only), `/portal` requires `canAccessCitizenPortal` (citizen only), and
  `/dept/:department` additionally checks `canAccessDepartmentPortal(user, dept)`
  so a Security user manually typing `/dept/MEDICAL` is redirected to their own
  home — they never see another department's portal shell. An unauthenticated user
  hitting any protected route is sent to `/login`.
- **Data guard (authoritative).** Even if navigation were bypassed, the backend
  independently scopes incident data by the verified token, so a citizen or a
  wrong-department user cannot fetch another party's incidents. Out-of-scope
  incident detail returns 404.

### Citizen safety (no internal reasoning exposed)

The citizen portal shows only a simplified 5-phase progress (Reported → Assessed →
Plan Prepared → Responders Dispatched → Resolved) derived purely from the public
`status`. It renders **no** agent names, tool traces, confidence scores, resource
IDs, approvals, or the operator console. Notifications and the safety-assistant
chatbot are shown as clearly-labeled "Preview" placeholders because no backend for
them exists yet.

---

## D. Existing functionality preserved

- The operator command center is the **same** `App` component, now mounted at
  `/command`. Its WebSocket, telemetry polling, emergency workflow, report modal,
  tabs, maps, and voice alerts are unchanged — the only edit is that the header
  identity/logout is now driven by the real authenticated user instead of a
  hard-coded placeholder.
- The API layer stays backward-compatible: with no token, requests are anonymous
  exactly as before (the backend's `ALLOW_ANONYMOUS_ADMIN` compat shim keeps the
  legacy demo working); a token simply enables real RBAC.
- No agent, orchestration, resource, response-plan, dispatch, GPS, or database
  behavior was modified in this increment. The only backend change is additive
  read-scoping on the incident list/detail endpoints.

---

## E. Tests run + exact results

**Not executed in this environment** (sandbox lacks disk to run Node/Python — see
the note at the top). The following are the exact commands to run in your Windows
venv, and what to expect. Please paste the real output back and I will reconcile
anything that does not match.

Frontend (from `frontend/`):

```bash
npm install            # REQUIRED: installs the newly added react-router-dom
npm run build          # tsc --noEmit + vite build → full TypeScript typecheck
npm test               # vitest run → roles.test.ts + incidentProgress.test.ts
```

Backend (from the repo root, run the two suites SEPARATELY as before):

```bash
# Increment-1/2 RBAC suite (expects ALLOW_ANONYMOUS_ADMIN disabled per its conftest)
python -m pytest backend/tests -q

# Legacy suite (default settings)
python -m pytest tests -q
```

**Static verification that WAS performed here (no execution):**

- Every Increment 2 module's imports resolve to a real export (routes, context,
  guards, pages, helpers, portal header, progress module).
- The login redirect uses the **resolved** user returned by the login call, so
  there is no stale-state redirect to `/login`.
- Backend contract check: role strings and UPPERCASE department codes returned by
  `/auth/login`, `/auth/user/*`, `/auth/department/login`, and `/auth/me` match
  what `roles.ts` / `homePathFor` consume.
- `tsconfig` uses `isolatedModules` **without** `verbatimModuleSyntax`, so the
  mixed type/value imports (matching the existing `api.ts` style) compile.
- All `lucide-react` icons used in the new files were confirmed to exist in the
  installed package's type declarations.
- The `.spin` / `.pulse` CSS classes now exist.

---

## F. Remaining limitations / follow-ups

1. **`npm install` is required** before the frontend builds — `react-router-dom`
   is declared in `package.json` but not yet in `node_modules`.
2. **Tests/build not run here.** Completion is contingent on the commands in
   section E passing in your environment.
3. **Notifications & chatbot are placeholders** (clearly labeled). They need
   backend endpoints before becoming functional — intentionally out of scope for
   this increment.
4. **Live update cadence.** The citizen and department feeds poll every 10s (real
   backend data, no fake progress). A future increment could switch them to the
   existing WebSocket for push updates.
5. **Department portal is read-oriented** by design: it shows the scoped responder
   feed but exposes no approve/dispatch/resolve controls (those remain
   operator-only in the command center). Per-department action workflows, if
   desired, would be a later increment.
6. **No jsdom/testing-library** in the project, so component rendering isn't unit
   tested; the tested logic was deliberately extracted into pure modules
   (`roles.ts`, `incidentProgress.ts`). Component behavior should be checked in the
   manual click-through (below).

### Suggested manual click-through
Operator `admin`/`password123` → `/command` (full dashboard). Citizen
`student@vignan.ac.in`/`9000000000` → `/portal` (report + progress). Department
`security@vignan.ac.in`/`password123` (Security) → `/dept/SECURITY`; then try
manually visiting `/dept/MEDICAL` and confirm the redirect back to
`/dept/SECURITY`. Log out from each and confirm the return to `/login`; refresh a
logged-in tab and confirm the session persists.
