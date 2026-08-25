"""Incident data-scoping tests for CampusFlow AI (Increment 2).

Increment 2 makes the department / citizen portals' isolation *real at the data
layer*: ``GET /api/v1/incidents`` (list) and ``GET /api/v1/incidents/{id}``
(detail) are scoped by the authenticated principal, never by the frontend.

  * Privileged operator/admin (and anonymous, compatibility mode) -> ALL.
  * Citizen/user -> only incidents they themselves reported.
  * Department staff -> only incidents routed to their own department.

The suite's DB is session-scoped and accumulates incidents created by other
tests, so these assertions are written in terms of *membership* of the specific
incidents created here (by id), never absolute counts.
"""

from backend.services.auth_service import ROLE_OPERATOR, ROLE_USER


# --- local login helpers (mirrors test_auth_rbac.py to avoid import fragility) ---

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
        json={"email": "student@vignan.ac.in", "phone": "9000000000"},
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _create_incident(client, body, headers=None):
    r = client.post("/api/v1/incidents", headers=headers or {}, json=body)
    assert r.status_code == 201, r.text
    return r.json()["incident_id"]


def _list_ids(client, headers=None):
    r = client.get("/api/v1/incidents", headers=headers or {})
    assert r.status_code == 200, r.text
    return {row["incident_id"] for row in r.json()}


# A fire routes to FIRE/SECURITY/MEDICAL/COMMUNICATION (never TRANSPORT).
_FIRE = {
    "description": "ScopeTest fire: smoke near the V-Block chemistry lab.",
    "incident_type": "fire",
    "location": "ScopeTest V-Block",
    "severity": "high",
}
# An accident routes to MEDICAL/TRANSPORT/SECURITY (never FIRE).
_ACCIDENT = {
    "description": "ScopeTest accident: two-wheeler collision at the north gate.",
    "incident_type": "accident",
    "location": "ScopeTest North Gate",
    "severity": "medium",
}


class TestIncidentListScoping:
    def test_citizen_sees_only_their_own(self, client):
        citizen = _citizen_token(client)
        operator = _operator_token(client)

        own_id = _create_incident(client, _FIRE, headers=_bearer(citizen))
        other_fire_id = _create_incident(client, _FIRE, headers=_bearer(operator))
        accident_id = _create_incident(client, _ACCIDENT, headers=_bearer(operator))

        visible = _list_ids(client, headers=_bearer(citizen))
        assert own_id in visible
        assert other_fire_id not in visible   # reported by operator, not this citizen
        assert accident_id not in visible

    def test_department_sees_only_routed_incidents(self, client):
        operator = _operator_token(client)
        fire_id = _create_incident(client, _FIRE, headers=_bearer(operator))
        accident_id = _create_incident(client, _ACCIDENT, headers=_bearer(operator))

        # TRANSPORT is routed for accidents, NOT for fires.
        transport = _department_token(client, "transport@vignan.ac.in", "TRANSPORT")
        transport_visible = _list_ids(client, headers=_bearer(transport))
        assert accident_id in transport_visible
        assert fire_id not in transport_visible

        # FIRE is routed for fires, NOT for accidents.
        fire_dept = _department_token(client, "fire@vignan.ac.in", "FIRE")
        fire_visible = _list_ids(client, headers=_bearer(fire_dept))
        assert fire_id in fire_visible
        assert accident_id not in fire_visible

    def test_operator_sees_all(self, client):
        operator = _operator_token(client)
        fire_id = _create_incident(client, _FIRE, headers=_bearer(operator))
        accident_id = _create_incident(client, _ACCIDENT, headers=_bearer(operator))

        visible = _list_ids(client, headers=_bearer(operator))
        assert fire_id in visible and accident_id in visible

    def test_anonymous_sees_all_compat(self, client):
        # The list endpoint uses get_optional_principal (not the command shim),
        # so anonymous callers keep full visibility regardless of the flag —
        # preserving the legacy operator console / kiosk behavior.
        operator = _operator_token(client)
        fire_id = _create_incident(client, _FIRE, headers=_bearer(operator))
        accident_id = _create_incident(client, _ACCIDENT, headers=_bearer(operator))

        visible = _list_ids(client)  # no auth header
        assert fire_id in visible and accident_id in visible


class TestIncidentDetailScoping:
    def test_citizen_detail_own_ok_others_404(self, client):
        citizen = _citizen_token(client)
        operator = _operator_token(client)
        own_id = _create_incident(client, _FIRE, headers=_bearer(citizen))
        foreign_id = _create_incident(client, _FIRE, headers=_bearer(operator))

        ok = client.get(f"/api/v1/incidents/{own_id}", headers=_bearer(citizen))
        assert ok.status_code == 200, ok.text

        # Out-of-scope detail is 404 (existence not disclosed), never 200.
        blocked = client.get(f"/api/v1/incidents/{foreign_id}", headers=_bearer(citizen))
        assert blocked.status_code == 404

    def test_department_detail_scoped(self, client):
        operator = _operator_token(client)
        fire_id = _create_incident(client, _FIRE, headers=_bearer(operator))
        accident_id = _create_incident(client, _ACCIDENT, headers=_bearer(operator))

        transport = _department_token(client, "transport@vignan.ac.in", "TRANSPORT")
        assert client.get(f"/api/v1/incidents/{accident_id}", headers=_bearer(transport)).status_code == 200
        assert client.get(f"/api/v1/incidents/{fire_id}", headers=_bearer(transport)).status_code == 404

    def test_operator_detail_any(self, client):
        operator = _operator_token(client)
        fire_id = _create_incident(client, _FIRE, headers=_bearer(operator))
        assert client.get(f"/api/v1/incidents/{fire_id}", headers=_bearer(operator)).status_code == 200
