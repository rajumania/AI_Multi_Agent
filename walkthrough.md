# CAMPUSFLOW AI — Autonomous Multi-Agent Emergency Operations Walkthrough

## 1. Overview & Architectural Transformation

We have upgraded **CAMPUSFLOW AI** from an operator-driven prototype into a **true Autonomous Event-Driven Multi-Agent Emergency Coordination System**.

### Key Architectural Capabilities Delivered:
1. **Event Engine & Autonomous Progression**:
   - Replaced manual button-driven steps with an event bus (`INCIDENT_CREATED` ➔ `SUPERVISOR_ASSESSED` ➔ `AGENTS_COORDINATED` ➔ `POLICY_CHECKED` ➔ `DISPATCHED` ➔ `MONITORED` ➔ `AUTO_RELEASED` ➔ `ARCHIVED`).
2. **Real MCP Tool-Calling Agents**:
   - Security: `find_nearest_security_team()`, `assign_security_team()`, `create_perimeter()`
   - Medical: `find_nearest_ambulance()`, `reserve_ambulance()`, `check_medical_capacity()`
   - Transport: `calculate_emergency_route()`, `reserve_vehicle()`, `block_route()`
   - Facilities: `get_building_details()`, `check_safety_equipment()`, `request_facilities_team()`
   - Communication: `create_alert()`, `send_targeted_notification()`
3. **Live AI Decision Trace & Explainability ("Why?")**:
   - Real-time timestamped reasoning stream showing what each agent thought, confidence metrics, and why resources were selected or why severity was rated.
4. **Deterministic & Auditable Severity Policy**:
   - Replaced opaque outputs with point-based rule scoring (+35 classification +20 building density +25 casualties +15 hazard velocity) with transparent rationale breakdown.
5. **Report Deduplication & Corroboration Clustering**:
   - Clusters repeated incoming reports for the same building into a single verified incident entity with a live corroboration counter.
6. **Digital Twin Simulation Engine & Failure Injection**:
   - **`[ ▶ RUN SCENARIO ]`** (`🔥 U-Block Fire`, `🏥 Hostel Medical`, `🚨 Gate Lockdown`)
   - **`[ ⚠️ SIMULATE RESOURCE BREAKDOWN (AMB-001 FAILS) ]`** button demonstrating live autonomous re-planning where the monitoring agent detects the failure, searches for `AMB-002`, recalculates routes, and updates the response plan autonomously.

---

## 2. Verification & Test Results

### Automated Tests
- **All 45 Pytest unit and integration tests passed cleanly**:
  - `tests/test_autonomous_operations.py`: Severity policy, policy guardrails, decision trace, digital twin scenario execution, and failure injection re-planning.
  - `tests/test_dispatch_and_resolution.py`: On-scene confirmation and automatic resource release.
  - `tests/test_incidents.py`: Multi-modal intake and classification.
  - `tests/test_map_and_spatial.py`: Campus coordinate and safe route calculations.
  - `tests/test_mcp_tools.py`: Resource query and tool execution.
  - `tests/test_multi_agent_graph.py`: Specialized agent graph coordination.
  - `tests/test_response_and_approval.py`: Plan generation and approval gateway.
  - `tests/test_supervisor_agent.py`: Intake parsing and spatial triage.

### Frontend Compilation
- **Vite React TypeScript Build**: 0 errors (`✓ built in 505ms`).
- **Live Servers**:
  - Web Application: **[http://localhost:5173/](http://localhost:5173/)**
  - FastAPI Backend: **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**

---

## 3. How to Demonstrate in 60 Seconds (Hackathon Demo Script)

1. Open **[http://localhost:5173/](http://localhost:5173/)**.
2. Look at the top **Digital Twin Autonomous Simulation** banner.
3. Click **`[ RUN SCENARIO: U-BLOCK FIRE ]`**:
   - An incident is automatically created, classified by the Supervisor, and evaluated by the Deterministic Severity Engine (`Score: 75/100`).
   - The Security, Medical, Transport, Facilities, and Communication agents actively invoke their MCP tools.
   - The **🧠 Live AI Decision Trace** streams each agent's thoughts and tool calls in real time.
4. Click **`[ APPROVE RESPONSE DEPLOYMENT ]`** (the only human authorization step required by policy).
5. Click **`[ ⚠️ SIMULATE AMB-001 BREAKDOWN ]`**:
   - The Monitoring Agent detects the transponder failure.
   - The Medical Agent autonomously searches for `AMB-002`, recalculates the emergency route, and updates the Response Plan live!
6. Click **`[ CONFIRM SITUATION UNDER CONTROL & RESOLVE ]`**:
   - Emergency is resolved and all vehicles/guards are automatically released back to `AVAILABLE`.
