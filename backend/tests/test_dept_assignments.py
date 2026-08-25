"""Phase 6 department assignment lifecycle, isolation, events and notifications."""

import json
from uuid import uuid4

from backend.database.models import AuditLogDB, DepartmentResponseDB, IncidentDB
from backend.services.assignment_service import create_required_assignments
from backend.services.event_engine import event_engine
from backend.services.event_visibility import ConnectionScope, should_deliver


def _operator_token(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _department_token(client, email, department):
    response = client.post("/api/v1/auth/department/login", json={"email": email, "password": "password123", "department": department})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _citizen_token(client):
    response = client.post("/api/v1/auth/user/login", json={"email": "student@vignan.ac.in", "phone": "9000000000"})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _incident(db_session, departments=("MEDICAL", "SECURITY")):
    incident_id = f"INC-P6-{uuid4().hex[:8].upper()}"
    row = IncidentDB(
        incident_id=incident_id,
        description="Phase 6 test incident",
        incident_type="accident",
        location="North Gate",
        severity="high",
        required_departments=json.dumps(list(departments)),
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _create(client, db_session, departments=("MEDICAL", "SECURITY")):
    incident = _incident(db_session, departments)
    create_required_assignments(incident, db_session)
    return incident.incident_id


def test_assignment_creation_and_idempotency(client, db_session):
    incident_id = _create(client, db_session)
    rows = db_session.query(DepartmentResponseDB).filter_by(incident_id=incident_id).all()
    assert {row.department for row in rows} == {"MEDICAL", "SECURITY"}
    assert {row.status for row in rows} == {"NOTIFIED"}
    create_required_assignments(db_session.query(IncidentDB).filter_by(incident_id=incident_id).one(), db_session)
    assert db_session.query(DepartmentResponseDB).filter_by(incident_id=incident_id).count() == 2


def test_operator_visibility_and_department_isolation(client, db_session):
    incident_id = _create(client, db_session)
    operator = _operator_token(client)
    medical = _department_token(client, "medical@vignan.ac.in", "MEDICAL")
    security = _department_token(client, "security@vignan.ac.in", "SECURITY")
    assert len(client.get(f"/api/v1/incidents/{incident_id}/assignments", headers=_auth(operator)).json()) == 2
    assert [row["department"] for row in client.get(f"/api/v1/incidents/{incident_id}/assignments", headers=_auth(medical)).json()] == ["MEDICAL"]
    assert [row["department"] for row in client.get(f"/api/v1/incidents/{incident_id}/assignments", headers=_auth(security)).json()] == ["SECURITY"]


def test_accept_decline_and_exact_lifecycle(client, db_session):
    incident_id = _create(client, db_session)
    medical = _department_token(client, "medical@vignan.ac.in", "MEDICAL")
    security = _department_token(client, "security@vignan.ac.in", "SECURITY")
    headers = _auth(medical)
    assert client.post(f"/api/v1/incidents/{incident_id}/assignments/MEDICAL/accept", headers=headers).json()["status"] == "ACCEPTED"
    assert client.post(f"/api/v1/incidents/{incident_id}/assignments/MEDICAL/team-assigned", headers=headers, json={"resource_ids": ["AMB-001"]}).json()["status"] == "TEAM_ASSIGNED"
    assert client.post(f"/api/v1/incidents/{incident_id}/assignments/MEDICAL/en-route", headers=headers).json()["status"] == "EN_ROUTE"
    assert client.post(f"/api/v1/incidents/{incident_id}/assignments/MEDICAL/on-scene", headers=headers).json()["status"] == "ON_SCENE"
    assert client.post(f"/api/v1/incidents/{incident_id}/assignments/MEDICAL/completed", headers=headers).json()["status"] == "COMPLETED"
    assert client.post(f"/api/v1/incidents/{incident_id}/assignments/SECURITY/decline", headers=_auth(security)).json()["status"] == "DECLINED"


def test_invalid_transitions_are_rejected(client, db_session):
    incident_id = _create(client, db_session, ("MEDICAL",))
    medical = _auth(_department_token(client, "medical@vignan.ac.in", "MEDICAL"))
    assert client.post(f"/api/v1/incidents/{incident_id}/assignments/MEDICAL/en-route", headers=medical).status_code == 409
    assert client.post(f"/api/v1/incidents/{incident_id}/assignments/MEDICAL/completed", headers=medical).status_code == 409
    client.post(f"/api/v1/incidents/{incident_id}/assignments/MEDICAL/accept", headers=medical)
    assert client.post(f"/api/v1/incidents/{incident_id}/assignments/MEDICAL/on-scene", headers=medical).status_code == 409


def test_unauthorized_department_and_citizen_are_blocked(client, db_session):
    incident_id = _create(client, db_session, ("MEDICAL",))
    security = _auth(_department_token(client, "security@vignan.ac.in", "SECURITY"))
    citizen = _auth(_citizen_token(client))
    assert client.post(f"/api/v1/incidents/{incident_id}/assignments/MEDICAL/accept", headers=security).status_code == 403
    assert client.get(f"/api/v1/incidents/{incident_id}/assignments", headers=citizen).status_code == 403
    assert client.post(f"/api/v1/incidents/{incident_id}/assignments/MEDICAL/accept", headers=citizen).status_code == 403


def test_events_and_audit_include_assignment_context(client, db_session, monkeypatch):
    incident_id = _create(client, db_session, ("MEDICAL",))
    captured = []
    original = event_engine.publish_event
    def capture(event_name, incident_id, payload, db=None):
        captured.append((event_name, incident_id, dict(payload)))
        return original(event_name, incident_id, payload, db=db)
    monkeypatch.setattr(event_engine, "publish_event", capture)
    medical = _auth(_department_token(client, "medical@vignan.ac.in", "MEDICAL"))
    assert client.post(f"/api/v1/incidents/{incident_id}/assignments/MEDICAL/accept", headers=medical).status_code == 200
    assert any(name == "dept_assignment_accepted" and payload["department"] == "MEDICAL" and payload["status"] == "ACCEPTED" for name, iid, payload in captured if iid == incident_id)
    logs = db_session.query(AuditLogDB).filter_by(incident_id=incident_id, action_type="dept_assignment_accepted").all()
    assert logs and "previous_status" in (logs[-1].details or "") and "new_status" in (logs[-1].details or "")


def test_notifications_are_scoped_and_read_state_is_real(client, db_session):
    incident_id = _create(client, db_session, ("MEDICAL", "SECURITY"))
    medical = _department_token(client, "medical@vignan.ac.in", "MEDICAL")
    security = _department_token(client, "security@vignan.ac.in", "SECURITY")
    medical_rows = client.get("/api/v1/notifications", headers=_auth(medical)).json()
    security_rows = client.get("/api/v1/notifications", headers=_auth(security)).json()
    assert medical_rows and all(row["department"] == "MEDICAL" for row in medical_rows if row["incident_id"] == incident_id)
    assert security_rows and all(row["department"] == "SECURITY" for row in security_rows if row["incident_id"] == incident_id)
    assert not any(row["department"] == "SECURITY" for row in medical_rows if row["incident_id"] == incident_id)
    notification_id = next(row["id"] for row in medical_rows if row["incident_id"] == incident_id)
    marked = client.post(f"/api/v1/notifications/{notification_id}/read", headers=_auth(medical))
    assert marked.status_code == 200 and marked.json()["read"] == 1


def test_operator_sees_system_notifications(client, db_session):
    incident_id = _create(client, db_session, ("MEDICAL",))
    operator = _auth(_operator_token(client))
    rows = client.get("/api/v1/notifications", headers=operator).json()
    assert any(row["incident_id"] == incident_id and row["recipient_type"] == "admin" for row in rows)


def test_approved_dispatch_creates_real_required_assignments(client):
    operator = _auth(_operator_token(client))
    created = client.post("/api/v1/incidents", headers=operator, json={
        "description": "Phase 6 dispatch integration incident",
        "incident_type": "accident",
        "location": "East Gate",
        "severity": "high",
        "injured_count": 1,
    })
    assert created.status_code == 201, created.text
    incident_id = created.json()["incident_id"]
    plan = client.post(f"/api/v1/response-plans/generate/{incident_id}", headers=operator)
    assert plan.status_code == 201, plan.text
    plan_id = plan.json()["plan_id"]
    approved = client.post(f"/api/v1/approvals/{plan_id}/decide", headers=operator, json={"decision": "approve", "operator_name": "Ignored by server"})
    assert approved.status_code == 200, approved.text
    dispatched = client.post(f"/api/v1/dispatch/{plan_id}/execute", headers=operator)
    assert dispatched.status_code == 200, dispatched.text
    rows = client.get(f"/api/v1/incidents/{incident_id}/assignments", headers=operator)
    assert rows.status_code == 200
    # Existing routing adds COMMUNICATION for high-severity campus-wide alerts;
    # Phase 6 must honor that backend configuration rather than inventing a UI list.
    assert {row["department"] for row in rows.json()} == {"MEDICAL", "TRANSPORT", "SECURITY", "COMMUNICATION"}
    assert {row["status"] for row in rows.json()} == {"NOTIFIED"}


def test_full_lifecycle_is_backend_driven_and_operator_sees_every_department(client, db_session, monkeypatch):
    """The complete human-response lifecycle is explicit and observable.

    No transition is advanced by a timer: every state below is produced by the
    corresponding authenticated department action and returned by the backend
    snapshot endpoint for the operator.
    """
    incident_id = _create(client, db_session, ("MEDICAL", "SECURITY", "TRANSPORT", "FIRE"))
    operator = _auth(_operator_token(client))
    departments = {
        "MEDICAL": _auth(_department_token(client, "medical@vignan.ac.in", "MEDICAL")),
        "SECURITY": _auth(_department_token(client, "security@vignan.ac.in", "SECURITY")),
        "TRANSPORT": _auth(_department_token(client, "transport@vignan.ac.in", "TRANSPORT")),
        "FIRE": _auth(_department_token(client, "fire@vignan.ac.in", "FIRE")),
    }
    captured = []
    original = event_engine.publish_event

    def capture(event_name, captured_incident_id, payload, db=None):
        if captured_incident_id == incident_id:
            captured.append((event_name, dict(payload)))
        return original(event_name, captured_incident_id, payload, db=db)

    monkeypatch.setattr(event_engine, "publish_event", capture)

    for department, headers in departments.items():
        assert client.post(f"/api/v1/incidents/{incident_id}/assignments/{department}/accept", headers=headers).json()["status"] == "ACCEPTED"
        assert client.post(
            f"/api/v1/incidents/{incident_id}/assignments/{department}/team-assigned",
            headers=headers,
            json={"resource_ids": [], "team_name": f"{department.title()} Team"},
        ).json()["status"] == "TEAM_ASSIGNED"
        assert client.post(f"/api/v1/incidents/{incident_id}/assignments/{department}/en-route", headers=headers).json()["status"] == "EN_ROUTE"
        assert client.post(f"/api/v1/incidents/{incident_id}/assignments/{department}/on-scene", headers=headers).json()["status"] == "ON_SCENE"
        assert client.post(f"/api/v1/incidents/{incident_id}/assignments/{department}/completed", headers=headers).json()["status"] == "COMPLETED"

    expected_events = [
        "dept_assignment_accepted",
        "dept_team_assigned",
        "dept_en_route",
        "dept_on_scene",
        "dept_assignment_completed",
    ]
    for department in departments:
        actual = [
            name for name, payload in captured
            if payload.get("department") == department and name in expected_events
        ]
        assert actual == expected_events
        assert sum(
            name == "notification_created"
            and payload.get("department") == department
            for name, payload in captured
        ) == 5

    operator_rows = client.get(f"/api/v1/incidents/{incident_id}/assignments", headers=operator)
    assert operator_rows.status_code == 200
    assert {row["department"] for row in operator_rows.json()} == set(departments)
    assert {row["status"] for row in operator_rows.json()} == {"COMPLETED"}

    logs = db_session.query(AuditLogDB).filter_by(incident_id=incident_id).all()
    for department in departments:
        assert any(
            log.action_type == "dept_assignment_completed"
            and department in (log.details or "")
            for log in logs
        )

    notifications = client.get("/api/v1/notifications", headers=operator).json()
    assert all(
        any(row["incident_id"] == incident_id and row["department"] == department for row in notifications)
        for department in departments
    )


def test_security_lifecycle_never_changes_medical_or_transport(client, db_session):
    """Regression: each DepartmentResponseDB row is an independent state machine."""
    incident_id = _create(client, db_session, ("SECURITY", "MEDICAL", "TRANSPORT"))
    security = _auth(_department_token(client, "security@vignan.ac.in", "SECURITY"))
    operator = _auth(_operator_token(client))

    for action, payload in (
        ("accept", None),
        ("team-assigned", {"resource_ids": [], "team_name": "Security Team"}),
        ("en-route", None),
        ("on-scene", None),
        ("completed", None),
    ):
        response = client.post(
            f"/api/v1/incidents/{incident_id}/assignments/SECURITY/{action}",
            headers=security,
            json=payload,
        )
        assert response.status_code == 200, response.text

    rows = client.get(f"/api/v1/incidents/{incident_id}/assignments", headers=operator)
    assert rows.status_code == 200
    statuses = {row["department"]: row["status"] for row in rows.json()}
    assert statuses == {"SECURITY": "COMPLETED", "MEDICAL": "NOTIFIED", "TRANSPORT": "NOTIFIED"}


def test_department_websocket_assignment_events_are_target_scoped():
    incident_scope = {"user_id": None, "departments": {"MEDICAL", "SECURITY"}}
    medical = ConnectionScope(subject_type="department", role="department", department="MEDICAL")
    security = ConnectionScope(subject_type="department", role="department", department="SECURITY")
    event = {"department": "MEDICAL", "status": "ON_SCENE"}

    assert should_deliver(medical, "dept_on_scene", incident_scope, event) is True
    assert should_deliver(security, "dept_on_scene", incident_scope, event) is False
    # Non-assignment incident events remain visible to every department routed
    # to the incident, which is required for shared operational awareness.
    assert should_deliver(security, "response_dispatched", incident_scope, event) is True
