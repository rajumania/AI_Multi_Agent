"""Focused verification for exact incidents and assignment-bound transport tracking."""

import json
from uuid import uuid4

from backend.database.models import DepartmentResponseDB, IncidentDB, RouteDB, RouteReplanDB, TransportTelemetryDB
from backend.services.assignment_service import create_required_assignments
from backend.services.event_engine import event_engine
from backend.services.event_visibility import ConnectionScope, should_deliver


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _login(client, path, payload):
    response = client.post(path, json=payload)
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _operator(client):
    return _login(client, "/api/v1/auth/login", {"username": "admin", "password": "password123"})


def _transport(client):
    return _login(client, "/api/v1/auth/department/login", {"email": "transport@aitam.local", "password": "password123", "department": "TRANSPORT"})


def _citizen(client):
    return _login(client, "/api/v1/auth/user/login", {"email": "community@aitam.local", "phone": "9000000000"})


def _incident(db_session, *, lat=18.56577, lng=84.19657):
    row = IncidentDB(
        incident_id=f"INC-TRACK-{uuid4().hex[:8].upper()}",
        description="Temporary transport tracking test incident",
        incident_type="accident",
        location="H-Block",
        severity="high",
        latitude=lat,
        longitude=lng,
        required_departments=json.dumps(["TRANSPORT"]),
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    create_required_assignments(row, db_session)
    return row


def _prepare_transport_assignment(client, db_session):
    incident = _incident(db_session)
    token = _transport(client)
    headers = _auth(token)
    assert client.post(f"/api/v1/incidents/{incident.incident_id}/assignments/TRANSPORT/accept", headers=headers).status_code == 200
    assigned = client.post(
        f"/api/v1/incidents/{incident.incident_id}/assignments/TRANSPORT/team-assigned",
        headers=headers,
        json={"resource_ids": ["VEH-001"]},
    )
    assert assigned.status_code == 200, assigned.text
    en_route = client.post(f"/api/v1/incidents/{incident.incident_id}/assignments/TRANSPORT/en-route", headers=headers)
    assert en_route.status_code == 200, en_route.text
    assignment = db_session.query(DepartmentResponseDB).filter_by(incident_id=incident.incident_id, department="TRANSPORT").one()
    return incident, assignment, token


def test_campus_member_can_create_and_read_exact_coordinates(client):
    token = _citizen(client)
    response = client.post(
        "/api/v1/incidents",
        headers=_auth(token),
        json={
            "description": "Exact map location test",
            "incident_type": "accident",
            "location": "H-Block",
            "severity": "high",
            "latitude": 16.234501,
            "longitude": 80.550501,
        },
    )
    assert response.status_code == 201, response.text
    incident_id = response.json()["incident_id"]
    assert response.json()["latitude"] == 16.234501
    read = client.get(f"/api/v1/incidents/{incident_id}", headers=_auth(token))
    assert read.status_code == 200
    assert read.json()["longitude"] == 80.550501


def test_invalid_incident_coordinate_pair_is_rejected(client):
    response = client.post(
        "/api/v1/incidents",
        json={"description": "Invalid coordinate test", "incident_type": "other", "location": "H-Block", "latitude": 16.2},
    )
    assert response.status_code == 422


def test_assigned_transport_writes_durable_gps_and_creates_coordinate_route(client, db_session, monkeypatch):
    monkeypatch.setattr("backend.services.road_network.road_network.fetch_osrm_route", lambda *args, **kwargs: None)
    incident, assignment, token = _prepare_transport_assignment(client, db_session)
    from backend.config import settings

    response = client.post(
        "/api/v1/telemetry/location",
        headers={**_auth(token), "X-GPS-Device-Token": settings.GPS_TELEMETRY_SECRET},
        json={
            "vehicle_id": "VEH-001",
            "assignment_id": assignment.id,
            "incident_id": incident.incident_id,
            "latitude": 18.56497,
            "longitude": 84.19567,
            "accuracy": 4.0,
            "speed": 5.0,
            "heading": 90.0,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["route_version"] == 1
    telemetry = db_session.query(TransportTelemetryDB).filter_by(assignment_id=assignment.id).one()
    assert (telemetry.latitude, telemetry.longitude) == (18.56497, 84.19567)
    route = db_session.query(RouteDB).filter_by(assignment_id=assignment.id, status="active").one()
    route_data = json.loads(route.path)
    assert route_data["coordinates"][0] == [18.56497, 84.19567] or tuple(route_data["coordinates"][0]) == (18.56497, 84.19567)
    snapshot = client.get(f"/api/v1/transport/assignments/{assignment.id}/tracking", headers=_auth(token))
    assert snapshot.status_code == 200
    assert snapshot.json()["gps_source"] == "REAL"
    assert snapshot.json()["route"]["route_version"] == 1

    # A later real GPS point must move the active route origin without creating
    # a replan record for ordinary movement.
    moved = client.post(
        "/api/v1/telemetry/location",
        headers={**_auth(token), "X-GPS-Device-Token": settings.GPS_TELEMETRY_SECRET},
        json={
            "vehicle_id": "VEH-001",
            "assignment_id": assignment.id,
            "incident_id": incident.incident_id,
            "latitude": 18.5651,
            "longitude": 84.1958,
            "accuracy": 4.0,
            "speed": 5.0,
            "heading": 90.0,
        },
    )
    assert moved.status_code == 200, moved.text
    db_session.expire_all()
    refreshed_route = db_session.query(RouteDB).filter_by(assignment_id=assignment.id, status="active").one()
    assert json.loads(refreshed_route.origin)["latitude"] == 18.5651
    assert refreshed_route.route_version == 1
    assert db_session.query(RouteReplanDB).filter_by(assignment_id=assignment.id).count() == 0


def test_transport_resource_and_websocket_visibility_are_scoped(client, db_session, monkeypatch):
    monkeypatch.setattr("backend.services.road_network.road_network.fetch_osrm_route", lambda *args, **kwargs: None)
    incident, assignment, token = _prepare_transport_assignment(client, db_session)
    from backend.config import settings

    unauthorized_resource = client.post(
        "/api/v1/telemetry/location",
        headers={**_auth(token), "X-GPS-Device-Token": settings.GPS_TELEMETRY_SECRET},
        json={"vehicle_id": "VEH-002", "assignment_id": assignment.id, "incident_id": incident.incident_id, "latitude": 16.233, "longitude": 80.551},
    )
    assert unauthorized_resource.status_code == 403

    unauthorized_department = _login(client, "/api/v1/auth/department/login", {"email": "medical@aitam.local", "password": "password123", "department": "MEDICAL"})
    blocked = client.get(f"/api/v1/transport/assignments/{assignment.id}/tracking", headers=_auth(unauthorized_department))
    assert blocked.status_code == 403

    transport_scope = ConnectionScope(subject_type="department", role="department_head", department="TRANSPORT")
    medical_scope = ConnectionScope(subject_type="department", role="department_head", department="MEDICAL")
    scope = {"user_id": None, "departments": {"TRANSPORT"}}
    payload = {"department": "TRANSPORT", "resource_id": "VEH-001"}
    for event_name in ("transport_location_updated", "transport_route_created", "transport_route_updated", "transport_eta_updated", "transport_arrived", "route_recalculated"):
        assert should_deliver(transport_scope, event_name, scope, payload) is True
        assert should_deliver(medical_scope, event_name, scope, payload) is False


def test_blocked_campus_segment_creates_route_replan(client, db_session, monkeypatch):
    monkeypatch.setattr("backend.services.road_network.road_network.fetch_osrm_route", lambda *args, **kwargs: None)
    incident, assignment, token = _prepare_transport_assignment(client, db_session)
    from backend.config import settings

    telemetry_headers = {**_auth(token), "X-GPS-Device-Token": settings.GPS_TELEMETRY_SECRET}
    assert client.post(
        "/api/v1/telemetry/location",
        headers=telemetry_headers,
        json={"vehicle_id": "VEH-001", "assignment_id": assignment.id, "incident_id": incident.incident_id, "latitude": 18.56497, "longitude": 84.19567},
    ).status_code == 200
    response = client.post(
        "/api/v1/road-conditions",
        headers=_auth(_operator(client)),
        json={"node_a": "admin_roundabout", "node_b": "u_block_junc", "status": "blocked", "reason": "Authorized temporary road closure", "incident_id": incident.incident_id},
    )
    assert response.status_code == 200, response.text
    assert response.json()["source"] == "authorized_operator_report"
    assert db_session.query(RouteReplanDB).filter_by(assignment_id=assignment.id).count() >= 1


def test_transport_arrival_event_requires_explicit_on_scene_transition(client, db_session, monkeypatch):
    incident, assignment, token = _prepare_transport_assignment(client, db_session)
    captured = []
    original = event_engine.publish_event

    def capture(event_name, captured_incident_id, payload, db=None):
        if captured_incident_id == incident.incident_id:
            captured.append((event_name, dict(payload)))
        return original(event_name, captured_incident_id, payload, db=db)

    monkeypatch.setattr(event_engine, "publish_event", capture)
    response = client.post(f"/api/v1/incidents/{incident.incident_id}/assignments/TRANSPORT/on-scene", headers=_auth(token))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ON_SCENE"
    arrivals = [(name, payload) for name, payload in captured if name == "transport_arrived"]
    assert len(arrivals) == 1
    assert arrivals[0][1]["assignment_id"] == assignment.id
    assert arrivals[0][1]["resource_id"] == "VEH-001"
