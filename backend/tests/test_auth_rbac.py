"""Auth / RBAC / departments test suite for CampusFlow AI (Increment 1).

Covers, per the requirements:
  * Part 3  — backend-enforced RBAC (never trust the frontend)
  * Part 4  — citizen portal identity (email + phone)
  * Part 5  — department staff login + department isolation
  * Part 7  — incident -> department routing
  * signup privilege-escalation clamp
  * token integrity (signature + expiry)
  * WebSocket event visibility rules (unit level)
  * the ALLOW_ANONYMOUS_ADMIN backward-compat shim (on and off)

These tests exercise the real FastAPI app against a throwaway SQLite DB (see
conftest.py). The anonymous-admin shim is OFF by default so the guards are
genuinely enforced; one test flips it on to prove the migration path.
"""

import time

from backend.config import settings
from backend.database.database import SessionLocal
from backend.database.models import IncidentDB

from backend.services import departments as dept
from backend.services.auth_service import (
    Principal,
    hash_password,
    verify_password,
    create_token,
    decode_token,
    verify_token,
    token_payload_for_user,
    ROLE_OPERATOR,
    ROLE_USER,
    ROLE_DEPARTMENT,
    SUBJECT_OPERATOR,
    SUBJECT_USER,
    SUBJECT_DEPARTMENT,
)
from backend.services.event_visibility import (
    ConnectionScope,
    guest_scope,
    operator_scope,
    scope_from_principal,
    should_deliver,
    USER_SAFE_EVENTS,
)


# --------------------------------------------------------------------------
# Local login helpers (kept in-module to avoid conftest-import fragility).
# --------------------------------------------------------------------------

def _operator_token(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _department_token(client, email, department):
    r = client.post(
        "/api/v1/auth/department/login",
        json={"email": email, "password": "password123", "department": department},
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _citizen_token(client):
    r = client.post(
        "/api/v1/auth/user/login",
        json={"email": "community@aitam.local", "phone": "9000000000"},
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ==========================================================================
# 1. Department registry / routing (pure functions, no DB)
# ==========================================================================

class TestDepartmentRouting:
    def test_normalize_is_case_insensitive_and_validates(self):
        assert dept.normalize_department("security") == "SECURITY"
        assert dept.normalize_department("  Medical ") == "MEDICAL"
        assert dept.normalize_department("nonsense") is None
        assert dept.normalize_department(None) is None
        assert dept.is_valid_department("FIRE") is True
        assert dept.is_valid_department("hr") is False

    def test_eight_canonical_departments(self):
        assert dept.DEPARTMENTS == (
            "MEDICAL", "SEARCH_AND_RESCUE", "FIRE", "SECURITY", "TRANSPORT", "COMMUNICATION", "FACILITIES", "SHELTER",
        )

    def test_resource_type_to_department(self):
        assert dept.department_for_resource_type("ambulance") == "MEDICAL"
        assert dept.department_for_resource_type("first_aid") == "MEDICAL"
        assert dept.department_for_resource_type("security") == "SECURITY"
        assert dept.department_for_resource_type("fire_response") == "FIRE"
        assert dept.department_for_resource_type("facility") == "FACILITIES"
        assert dept.department_for_resource_type("shelter") == "SHELTER"
        assert dept.department_for_resource_type("vehicle") == "TRANSPORT"
        # "other" is intentionally unmapped.
        assert dept.department_for_resource_type("other") is None

    def test_resource_types_for_department_round_trip(self):
        medical_types = set(dept.resource_types_for_department("medical"))
        assert {"ambulance", "first_aid", "medical_center"} <= medical_types

    def test_agent_to_department(self):
        assert dept.department_for_agent("fire_agent") == "FIRE"
        assert dept.department_for_agent("facilities_agent") == "FACILITIES"
        assert dept.department_for_agent("supervisor_agent") is None

    def test_departments_for_incident_base(self):
        assert dept.departments_for_incident("fire") == [
            "FIRE", "MEDICAL", "SECURITY", "TRANSPORT", "FACILITIES", "COMMUNICATION",
        ]
        assert dept.departments_for_incident("medical", "low") == ["MEDICAL", "SECURITY"]
        assert dept.departments_for_incident("unknown") == ["SECURITY"]

    def test_high_severity_engages_communication(self):
        engaged = dept.departments_for_incident("medical", "critical")
        assert "COMMUNICATION" in engaged
        # No duplicates, priority order preserved.
        assert engaged[0] == "MEDICAL"
        assert len(engaged) == len(set(engaged))


# ==========================================================================
# 2. Auth service core (hashing, tokens, Principal)
# ==========================================================================

class TestAuthServiceCore:
    def test_password_hash_and_verify(self):
        h = hash_password("password123")
        assert verify_password("password123", h) is True
        assert verify_password("wrong", h) is False
        assert verify_password("", h) is False

    def test_token_round_trip(self):
        token = create_token({"typ": SUBJECT_OPERATOR, "sub": "1", "role": ROLE_OPERATOR})
        claims = decode_token(token)
        assert claims is not None
        assert claims["role"] == ROLE_OPERATOR
        assert claims["sub"] == "1"
        assert verify_token(token) is True

    def test_tampered_token_rejected(self):
        token = create_token({"sub": "1", "role": ROLE_OPERATOR})
        payload_b64, _sig = token.split(".")
        forged = payload_b64 + "." + ("0" * 64)
        assert decode_token(forged) is None
        assert verify_token(forged) is False

    def test_expired_token_rejected(self):
        token = create_token({"sub": "1", "role": ROLE_OPERATOR}, expires_seconds=-1)
        assert decode_token(token) is None

    def test_none_and_garbage_tokens(self):
        assert decode_token(None) is None
        assert decode_token("") is None
        assert decode_token("not-a-token") is None

    def test_principal_role_predicates(self):
        op = Principal(subject_type=SUBJECT_OPERATOR, id="1", role=ROLE_OPERATOR)
        assert op.is_privileged and op.is_admin
        assert not op.is_department and not op.is_user

        user = Principal(subject_type=SUBJECT_USER, id="9", role=ROLE_USER)
        assert user.is_user and not user.is_privileged and not user.is_department

        staff = Principal(
            subject_type=SUBJECT_DEPARTMENT, id="3", role=ROLE_DEPARTMENT, department="SECURITY",
        )
        assert staff.is_department and not staff.is_privileged and not staff.is_user

    def test_principal_department_isolation(self):
        sec = Principal(
            subject_type=SUBJECT_DEPARTMENT, id="3", role=ROLE_DEPARTMENT, department="SECURITY",
        )
        assert sec.can_access_department("security") is True   # own dept, any case
        assert sec.can_access_department("MEDICAL") is False   # other dept blocked
        # Privileged actors can access any department.
        op = Principal(subject_type=SUBJECT_OPERATOR, id="1", role=ROLE_OPERATOR)
        assert op.can_access_department("MEDICAL") is True

    def test_public_dict_has_no_secrets(self):
        op = Principal(subject_type=SUBJECT_OPERATOR, id="1", role=ROLE_OPERATOR, username="admin")
        pub = op.to_public_dict()
        assert "hashed_password" not in pub and "password" not in pub
        assert pub["role"] == ROLE_OPERATOR


# ==========================================================================
# 3. WebSocket event visibility (unit level — mirrors REST RBAC)
# ==========================================================================

class TestEventVisibility:
    incident = {"user_id": "42", "departments": {"SECURITY", "MEDICAL"}}

    def test_privileged_receives_everything(self):
        scope = operator_scope()
        assert should_deliver(scope, "agent_started", self.incident) is True
        assert should_deliver(scope, "incident_resolved", self.incident) is True

    def test_guest_receives_nothing(self):
        assert should_deliver(guest_scope(), "incident_created", self.incident) is False
        assert should_deliver(None, "incident_created", self.incident) is False

    def test_department_scoped_to_routed_incidents(self):
        sec = ConnectionScope(subject_type="department", role="department", department="SECURITY")
        tra = ConnectionScope(subject_type="department", role="department", department="TRANSPORT")
        assert should_deliver(sec, "agent_started", self.incident) is True   # SECURITY is routed
        assert should_deliver(tra, "agent_started", self.incident) is False  # TRANSPORT is not

    def test_citizen_only_owned_and_safe_events(self):
        owner = ConnectionScope(subject_type="user", role="user", user_id="42")
        other = ConnectionScope(subject_type="user", role="user", user_id="99")
        # Owns the incident + safe event -> delivered.
        assert should_deliver(owner, "incident_resolved", self.incident) is True
        # Owns the incident but internal reasoning event -> blocked.
        assert should_deliver(owner, "agent_started", self.incident) is False
        # Safe event but not the owner -> blocked.
        assert should_deliver(other, "incident_resolved", self.incident) is False

    def test_internal_events_are_not_user_safe(self):
        for internal in ("agent_started", "tool_started", "approval_requested", "trace_updated"):
            assert internal not in USER_SAFE_EVENTS

    def test_scope_from_principal(self):
        op = Principal(subject_type=SUBJECT_OPERATOR, id="1", role=ROLE_OPERATOR)
        assert scope_from_principal(op).privileged is True
        staff = Principal(
            subject_type=SUBJECT_DEPARTMENT, id="3", role=ROLE_DEPARTMENT, department="FIRE",
        )
        s = scope_from_principal(staff)
        assert s.subject_type == "department" and s.department == "FIRE"
        user = Principal(subject_type=SUBJECT_USER, id="7", role=ROLE_USER)
        u = scope_from_principal(user)
        assert u.subject_type == "user" and u.user_id == "7" and u.privileged is False


# ==========================================================================
# 4. Auth API — login flows for the three identities
# ==========================================================================

class TestAuthApi:
    def test_operator_login_and_me(self, client):
        token = _operator_token(client)
        me = client.get("/api/v1/auth/me", headers=_bearer(token))
        assert me.status_code == 200
        body = me.json()
        assert body["role"] == ROLE_OPERATOR
        assert body["subject_type"] == SUBJECT_OPERATOR

    def test_operator_login_wrong_password(self, client):
        r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "nope"})
        assert r.status_code == 400

    def test_me_requires_token(self, client):
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_citizen_login_and_me(self, client):
        token = _citizen_token(client)
        me = client.get("/api/v1/auth/me", headers=_bearer(token))
        assert me.status_code == 200
        assert me.json()["role"] == ROLE_USER

    def test_citizen_login_wrong_phone(self, client):
        r = client.post(
            "/api/v1/auth/user/login",
            json={"email": "community@aitam.local", "phone": "0000000000"},
        )
        assert r.status_code == 400

    def test_department_login_and_me(self, client):
        token = _department_token(client, "security@aitam.local", "SECURITY")
        me = client.get("/api/v1/auth/me", headers=_bearer(token))
        assert me.status_code == 200
        body = me.json()
        assert body["subject_type"] == SUBJECT_DEPARTMENT
        assert body["department"] == "SECURITY"
        assert body.get("department_label") == "Security / Public Safety"

    def test_department_login_wrong_department_rejected(self, client):
        # Correct credentials but claiming a department the account isn't in.
        r = client.post(
            "/api/v1/auth/department/login",
            json={"email": "security@aitam.local", "password": "password123", "department": "MEDICAL"},
        )
        assert r.status_code == 403

    def test_department_login_wrong_password(self, client):
        r = client.post(
            "/api/v1/auth/department/login",
            json={"email": "security@aitam.local", "password": "wrong", "department": "SECURITY"},
        )
        assert r.status_code == 400


# ==========================================================================
# 5. Privilege-escalation clamp + admin-only provisioning
# ==========================================================================

class TestPrivilegeBoundaries:
    def test_signup_cannot_self_assign_operator(self, client):
        # Anonymous signup requesting "operator" must be clamped to "user".
        uname = f"escalate_{int(time.time()*1000)}"
        r = client.post(
            "/api/v1/auth/signup",
            json={"username": uname, "password": "password123", "role": "operator", "full_name": "X"},
        )
        assert r.status_code == 200
        assert r.json()["role"] == ROLE_USER  # downgraded

    def test_department_register_requires_auth(self, client):
        r = client.post(
            "/api/v1/auth/department/register",
            json={"email": "new-dept@aitam.local", "password": "password123", "department": "FIRE"},
        )
        # No token at all -> get_current_principal raises 401.
        assert r.status_code == 401

    def test_department_register_forbidden_for_citizen(self, client):
        token = _citizen_token(client)
        r = client.post(
            "/api/v1/auth/department/register",
            headers=_bearer(token),
            json={"email": "new-dept2@aitam.local", "password": "password123", "department": "FIRE"},
        )
        assert r.status_code == 403

    def test_department_register_allowed_for_admin(self, client):
        token = _operator_token(client)
        email = f"crew_{int(time.time()*1000)}@aitam.local"
        r = client.post(
            "/api/v1/auth/department/register",
            headers=_bearer(token),
            json={"email": email, "password": "password123", "department": "FACILITIES"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["department"] == "FACILITIES"


# ==========================================================================
# 6. Command-endpoint RBAC guards (anonymous shim OFF)
# ==========================================================================

class TestCommandGuards:
    """With ALLOW_ANONYMOUS_ADMIN off, command endpoints require a privileged
    token. We probe a missing incident id: the auth dependency runs first, so
    anon -> 401 and citizen -> 403 short-circuit before the 404, while a valid
    operator passes auth and only then hits 'incident not found' (404)."""

    MISSING = "/api/v1/incidents/INC-DOES-NOT-EXIST/orchestrate"

    def test_anonymous_blocked(self, client):
        assert settings.ALLOW_ANONYMOUS_ADMIN is False
        assert client.post(self.MISSING).status_code == 401

    def test_citizen_forbidden(self, client):
        token = _citizen_token(client)
        assert client.post(self.MISSING, headers=_bearer(token)).status_code == 403

    def test_operator_passes_guard(self, client):
        token = _operator_token(client)
        # 404 == auth succeeded, then incident lookup failed (guard did not block).
        assert client.post(self.MISSING, headers=_bearer(token)).status_code == 404

    def test_generate_plan_and_dispatch_guarded(self, client):
        # Both are privileged command actions -> anonymous rejected.
        assert client.post("/api/v1/response-plans/generate/INC-NONE").status_code == 401
        assert client.post("/api/v1/dispatch/PLAN-NONE/execute").status_code == 401
        assert client.post("/api/v1/simulation/start", json={"scenario_key": "ublock_fire"}).status_code == 401


# ==========================================================================
# 7. Backward-compat: anonymous shim ON keeps the legacy console working
# ==========================================================================

class TestAnonymousShim:
    def test_anonymous_operator_when_shim_enabled(self, client, anonymous_admin_on):
        # With the shim on, an unauthenticated caller is treated as operator and
        # passes the guard, so a missing incident now yields 404 (not 401).
        r = client.post("/api/v1/incidents/INC-DOES-NOT-EXIST/orchestrate")
        assert r.status_code == 404


# ==========================================================================
# 8. Incident intake: open reporting + ownership stamping + routing metadata
# ==========================================================================

class TestIncidentIntake:
    BODY = {
        "description": "Smoke reported near the chemistry lab in V-Block.",
        "incident_type": "fire",
        "location": "V-Block",
        "severity": "high",
    }

    def test_anonymous_reporting_allowed(self, client):
        # Citizen reporting must work even with the shim OFF (create is open).
        assert settings.ALLOW_ANONYMOUS_ADMIN is False
        r = client.post("/api/v1/incidents", json=self.BODY)
        assert r.status_code == 201, r.text
        incident_id = r.json()["incident_id"]

        # No principal -> no owner stamped; routing metadata still populated.
        session = SessionLocal()
        try:
            row = session.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
            assert row is not None
            assert row.user_id is None
            assert row.category == "fire"
            assert "FIRE" in (row.required_departments or "")
            assert "SECURITY" in (row.required_departments or "")
        finally:
            session.close()

    def test_citizen_report_is_owned(self, client):
        token = _citizen_token(client)
        me = client.get("/api/v1/auth/me", headers=_bearer(token)).json()
        r = client.post("/api/v1/incidents", headers=_bearer(token), json=self.BODY)
        assert r.status_code == 201, r.text
        incident_id = r.json()["incident_id"]

        session = SessionLocal()
        try:
            row = session.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
            assert row.user_id == me["id"]  # stamped with the citizen's id
        finally:
            session.close()

    def test_operator_report_not_owned_as_citizen(self, client):
        # An operator filing on someone's behalf does not "own" it as a citizen.
        token = _operator_token(client)
        r = client.post("/api/v1/incidents", headers=_bearer(token), json=self.BODY)
        assert r.status_code == 201
        incident_id = r.json()["incident_id"]
        session = SessionLocal()
        try:
            row = session.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
            assert row.user_id is None
        finally:
            session.close()


# ==========================================================================
# 9. Seed + migration integrity
# ==========================================================================

class TestSeedAndMigration:
    def test_resources_have_departments(self):
        from backend.database.models import CampusResourceDB
        session = SessionLocal()
        try:
            amb = session.query(CampusResourceDB).filter_by(resource_id="AMB-001").first()
            sec = session.query(CampusResourceDB).filter_by(resource_id="SEC-001").first()
            fire = session.query(CampusResourceDB).filter_by(resource_id="FIRE-001").first()
            assert amb.department == "MEDICAL"
            assert sec.department == "SECURITY"
            assert fire.department == "FIRE"
        finally:
            session.close()

    def test_department_accounts_seeded(self, client):
        # Every one of the six departments must have a working login.
        for email, _name, code in [
            ("security@aitam.local", "", "SECURITY"),
            ("medical@aitam.local", "", "MEDICAL"),
            ("transport@aitam.local", "", "TRANSPORT"),
            ("communication@aitam.local", "", "COMMUNICATION"),
            ("fire@aitam.local", "", "FIRE"),
            ("facilities@aitam.local", "", "FACILITIES"),
        ]:
            token = _department_token(client, email, code)
            assert token

    def test_migration_is_idempotent(self):
        from backend.database.database import engine
        from backend.database.migrate import ensure_schema
        # Schema already migrated by the session fixture; a second run adds nothing.
        result = ensure_schema(engine)
        assert all(len(cols) == 0 for cols in result.values()), result
