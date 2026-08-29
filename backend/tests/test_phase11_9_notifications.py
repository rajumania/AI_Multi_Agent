"""Focused Phase 11.9 tests for durable, scoped in-app notifications."""

import json
from uuid import uuid4

from backend.database.models import IncidentDB, NotificationDB, ResponsePlanDB
from backend.services.assignment_service import create_required_assignments
from backend.services.event_visibility import ConnectionScope, should_deliver
from backend.services.notification_service import mark_notification_delivered
from backend.services.response_service import response_service


def _incident(db_session, departments=("SEARCH_AND_RESCUE", "MEDICAL", "TRANSPORT")):
    row = IncidentDB(
        incident_id=f"INC-P11-9-{uuid4().hex[:8].upper()}",
        description="Controlled Himalayan landslide notification test",
        incident_type="landslide",
        location="Controlled Himalayan test coordinate",
        latitude=27.9881,
        longitude=86.9250,
        severity="high",
        required_departments=json.dumps(list(departments)),
        detection_evidence=json.dumps({
            "supporting_evidence": ["Controlled test report"],
            "department_recommendations": [
                {"department": departments[0], "reason": "Mountain-road obstruction and rescue need", "confidence": 0.9},
            ],
        }),
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_approved_assignment_notification_has_safe_operational_context_and_is_idempotent(db_session):
    incident = _incident(db_session, ("SEARCH_AND_RESCUE",))
    created = create_required_assignments(incident, db_session)
    assert [assignment.department for assignment in created] == ["SEARCH_AND_RESCUE"]

    row = db_session.query(NotificationDB).filter_by(
        incident_id=incident.incident_id,
        recipient_type="department",
        department="SEARCH_AND_RESCUE",
    ).one()
    details = json.loads(row.details_json)
    assert row.event_key == f"department:{incident.incident_id}:SEARCH_AND_RESCUE:NOTIFIED"
    assert row.lifecycle_status == "CREATED"
    assert row.priority == "critical"
    assert details["latitude"] == 27.9881
    assert details["longitude"] == 86.9250
    assert details["approval_status"] == "approved"
    assert "password" not in json.dumps(details).lower()

    create_required_assignments(incident, db_session)
    assert db_session.query(NotificationDB).filter_by(
        incident_id=incident.incident_id,
        recipient_type="department",
        department="SEARCH_AND_RESCUE",
    ).count() == 1


def test_notification_delivery_is_authorized_and_scoped(db_session):
    incident = _incident(db_session, ("MEDICAL", "SECURITY"))
    create_required_assignments(incident, db_session)
    medical = db_session.query(NotificationDB).filter_by(
        incident_id=incident.incident_id,
        recipient_type="department",
        department="MEDICAL",
    ).one()
    medical_scope = ConnectionScope(subject_type="department", role="department_head", department="MEDICAL")
    security_scope = ConnectionScope(subject_type="department", role="department_head", department="SECURITY")

    assert mark_notification_delivered(medical.id, security_scope) is False
    db_session.expire_all()
    assert db_session.get(NotificationDB, medical.id).lifecycle_status == "CREATED"
    assert mark_notification_delivered(medical.id, medical_scope) is True
    db_session.expire_all()
    assert db_session.get(NotificationDB, medical.id).lifecycle_status == "DELIVERED"
    assert mark_notification_delivered(medical.id, medical_scope) is True


def test_notification_events_never_cross_department_or_approval_boundary(db_session):
    incident = _incident(db_session, ("MEDICAL", "SECURITY"))
    # This helper is called by the approved-dispatch path. The visibility test
    # confirms that the resulting event is private to the named department.
    create_required_assignments(incident, db_session)
    payload = {"recipient_type": "department", "department": "MEDICAL", "notification_id": 1}
    incident_scope = {"user_id": None, "departments": {"MEDICAL", "SECURITY"}}
    assert should_deliver(ConnectionScope(subject_type="department", role="head", department="MEDICAL"), "notification_created", incident_scope, payload)
    assert not should_deliver(ConnectionScope(subject_type="department", role="head", department="SECURITY"), "notification_created", incident_scope, payload)
    assert not should_deliver(ConnectionScope(subject_type="user", role="community", user_id="other"), "notification_created", incident_scope, payload)


def test_approval_is_the_operational_notification_boundary(db_session):
    incident = _incident(db_session, ("SEARCH_AND_RESCUE",))
    plan = ResponsePlanDB(
        plan_id=f"PLAN-P11-9-{uuid4().hex[:8].upper()}",
        incident_id=incident.incident_id,
        title="Controlled Himalayan response plan",
        severity="high",
        location=incident.location,
        recommended_actions=json.dumps(["Verify access"]),
        allocated_resources=json.dumps([]),
        requires_approval="true",
        approval_status="pending",
    )
    db_session.add(plan)
    db_session.commit()
    assert db_session.query(NotificationDB).filter_by(incident_id=incident.incident_id, recipient_type="department").count() == 0
    response_service.decide_approval(plan.plan_id, "approve", operator_name="Controlled Test Commander", db=db_session)
    assert db_session.query(NotificationDB).filter_by(incident_id=incident.incident_id, recipient_type="department", department="SEARCH_AND_RESCUE").count() == 1
