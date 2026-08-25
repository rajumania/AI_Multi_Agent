# PHASE 3 — Real-Time 3D AI-Agent Command Center

**PHASE:** 3 of 17 — Lazy-loaded 3D AI-agent visualization system

**STATUS:** ✅ Implemented in code — ⏳ awaiting your verification (`npm install`, `npm test`, `npm run build`)

---

## Implemented

A real, lazy-loaded 3D command center that visualizes the five headline AI agents and reacts **only** to real backend state — no timers, no scripted sequence, no fake progress. The backend remains the single source of truth; this layer renders the Phase 2 realtime state and never drives the workflow.

What went in:

- **Five visual agents**, each bound to a REAL LangGraph backend node key so every node is event-driven:
  - Incident Intelligence → `supervisor`
  - Medical Response → `medical`
  - Safety / Hazard → `fire`
  - Resource Allocation → `transport`
  - Response Planning → `synthesizer` (also the human-approval gate)
- **All six required visual states**, derived purely from real signals in the Phase 2 model:
  - `IDLE` (no incident / not started), `QUEUED` (workflow started, this agent's turn pending), `WORKING` (real `agent_started`/`agent_progress`), `COMPLETED` (real `agent_completed`), `FAILED` (real `agent_failed`), `WAITING_APPROVAL` (real `approval_required` still pending on the planner).
  - Working/waiting states pulse; completed/failed are steady. Every transition is caused by an actual backend event.
- **Reusable components**: a three.js `AgentNode` factory (glowing icosahedron core + identity ring) and a DOM `AgentCard` (status badge, message, structured-output chips). The card only ever shows structured, non-sensitive output — never raw reasoning.
- **Imperative three.js scene** (`CommandCenterScene`): renderer, camera, lights, connector lines, manual pointer-drag + gentle auto-orbit, resize handling, and a full `dispose()` that releases every GPU resource and listener. WebGL creation is guarded.
- **Lazy loading / code splitting**: the heavy 3D view (three.js) is behind `React.lazy` + `Suspense`, wrapped in an error boundary. It is reached only from the privileged `/command` operator shell — never from login/signup, and never in the main bundle.
- **Graceful degradation**: if WebGL is unavailable or the chunk fails, the same AgentCards render as a DOM-only fallback, so the feature is never bricked.
- **Wiring**: the operator shell now folds each real WebSocket event into the Phase 2 reducer using the **existing single socket** (no second WebSocket), and exposes a new privileged **"AI Command 3D"** tab.

### Rendering approach note (transparency)

You chose **Three.js / WebGL**. The option text mentioned `@react-three/fiber` + `drei`, but I implemented with **core `three` only** (imperative renderer + manual orbit, no `fiber`/`drei`, no `three/examples/jsm` imports). This keeps the dependency footprint and build risk minimal (Rule 23) while delivering the same real WebGL 3D. If you'd prefer the react-three-fiber stack, I can switch in a follow-up — but core three is lighter and lazy-loaded.

---

## Files changed

**New (`frontend/src/command3d/`):**

- `agentCatalog.ts` — the 5 visual agents + backend-key bindings + connections (pure, DOM-free, three-free)
- `agentStatus.ts` — six-state derivation + status→visual mapping (pure, DOM-free, three-free)
- `AgentNode.ts` — reusable three.js node factory
- `AgentCard.tsx` — reusable DOM status card
- `CommandCenterScene.ts` — imperative three.js scene (WebGL-guarded, disposable)
- `CommandCenter3D.tsx` — **default export**, the lazy target; owns scene lifecycle + overlay + fallback
- `CommandCenter3DLazy.tsx` — `React.lazy` + `Suspense` + error boundary (the only module the shell imports)
- `agentStatus.test.ts` — DOM-free vitest suite (catalog integrity + all six states)

**Modified:**

- `frontend/package.json` — added `three ^0.169.0` (dep) and `@types/three ^0.169.0` (devDep)
- `frontend/src/App.tsx` — added `useReducer(reduceRealtime)` fed by the **existing** socket's `onmessage`; added the lazy "AI Command 3D" tab; computes the active workflow via `getActiveWorkflow`
- `frontend/src/components/Sidebar.tsx` — added the "AI Command 3D" nav item (Cpu icon)

No existing files were rebuilt, replaced, or deleted.

---

## Existing functionality preserved: **YES**

- No changes to authentication, RBAC, the database, the backend, the incident workflow, the existing AI agents, or existing APIs.
- **No duplicate WebSocket** — the reducer is fed by the one socket App.tsx already owns (Rule 11).
- The reducer returns the same state object for irrelevant events, so the operator dashboard re-renders only on meaningful change.
- Login/signup remain lightweight: they never import App, and the 3D chunk is `React.lazy`-split, so it is not in the main bundle (Rules 24–26).
- All prior tabs (Overview, Incidents, Resources, Response Plans, Activity Logs) are untouched.

---

## Backend tests

Not applicable to Phase 3 (frontend-only). No backend files were modified. Backend suites remain to be run separately as before:

```
python -m pytest backend/tests -q
python -m pytest tests -q
```

(Note: Phase 1 backend lifecycle-event emission — the code that populates these node states at runtime — is implemented but its pytest run is still pending your confirmation. The Phase 3 UI is verified independently by the pure unit tests + build; live node animation will flow once Phase 1 events are confirmed green.)

---

## Frontend tests

**Written, not yet executed here** (this environment cannot run npm/vitest — disk-constrained). Please run on your Windows venv:

```
cd frontend
npm install        # REQUIRED — pulls in three + @types/three
npm test
```

New suite: `src/command3d/agentStatus.test.ts` — covers catalog integrity (exactly 5 agents, unique real keys, hex accents, valid connections, approval-gate binding), the full `STATUS_VISUALS` mapping, `workflowStarted`, and all six derived states including the `WAITING_APPROVAL` override and its clearing after a decision. Expected to add to the existing 58 passing tests.

---

## Build

**Not yet executed here.** Please run:

```
cd frontend
npm run build      # tsc && vite build
```

Everything was written against your strict TS config (`noUnusedLocals`/`noUnusedParameters`, etc.). Expect Vite to emit a separate lazy chunk for the 3D view (three.js), downloaded only when the "AI Command 3D" tab is opened.

---

## Known issues

- **`npm install` is required before test/build** — `three` and `@types/three` are new dependencies.
- **Tests + build have not been run in this environment** (sandbox is out of disk). They are handed to you to run on the Windows venv; I have not claimed them green.
- The existing Vite **chunk-size warning** will likely remain and may now also reference the new 3D chunk — that is expected and benign (the chunk is lazy-loaded).
- Live 3D animation depends on **Phase 1** backend events actually flowing; until you confirm the Phase 1 pytest suites, nodes will render/idle correctly but won't animate through WORKING→COMPLETED without those real events.

---

## Next phase

**Phase 4 — Student real-time view (role-safe progress).** 

Per your standing instruction, I will **not** proceed to Phase 4 until you confirm Phase 3 is verified: `npm install`, then `npm test` and `npm run build` both green.
