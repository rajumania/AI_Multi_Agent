"""Phase 8 personal assistant, targeted notification, and privacy tests."""

import json
from uuid import uuid4

from backend.database.models import ChatMessageDB, IncidentDB, NotificationDB
from backend.services.event_engine import event_engine
from backend.services.event_visibility import ConnectionScope, should_deliver
from backend.services.llm_service import llm_service
from backend.services.memory_service import memory_service


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _register(client, suffix):
    response = client.post("/api/v1/auth/user/register", json={
        "email": f"phase8-{suffix}@vignan.ac.in",
        "phone": f"90000{suffix:05d}" if isinstance(suffix, int) else "9000099999",
        "full_name": f"Phase 8 {suffix}",
    })
    assert response.status_code == 200, response.text
    return response.json()["token"], str(response.json()["user"]["id"])


def test_chat_requires_auth_and_persists_conversation(client, db_session, monkeypatch):
    unauthenticated = client.post("/api/v1/chat/message", json={"message": "Where is the safety desk?"})
    assert unauthenticated.status_code == 401
    token, user_id = _register(client, 1)
    monkeypatch.setattr(llm_service, "generate_chat_response", lambda **_: "Use the campus safety reporting path.")
    response = client.post("/api/v1/chat/message", headers=_auth(token), json={"message": "Where is the safety desk?"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["message"] == "Use the campus safety reporting path."
    assert payload["conversation_id"]
    assert payload["memory_used"] is False
    history = client.get("/api/v1/chat/history", headers=_auth(token))
    assert history.status_code == 200
    assert [row["sender"] for row in history.json()["messages"]] == ["user", "assistant"]
    assert all(row["conversation_id"] == payload["conversation_id"] for row in history.json()["messages"])
    assert db_session.query(ChatMessageDB).filter(ChatMessageDB.user_id == user_id).count() == 2


def test_chat_memory_operation_is_scoped_to_authenticated_user(client, monkeypatch):
    token, user_id = _register(client, 2)
    seen = []

    class FakeMem0:
        def search(self, query, user_id=None):
            seen.append(("search", user_id))
            return [{"memory": "prefers English"}]

        def add(self, messages, user_id=None):
            seen.append(("add", user_id))
            return {"status": "PENDING"}

    monkeypatch.setattr(memory_service, "client", FakeMem0())
    monkeypatch.setattr(llm_service, "generate_chat_response", lambda **kwargs: "I can use that preference.")
    response = client.post("/api/v1/chat/message", headers=_auth(token), json={"message": "Please use English."})
    assert response.status_code == 200
    assert response.json()["memory_used"] is True
    assert seen == [("search", user_id), ("add", user_id)]


def test_chat_history_cannot_cross_users(client, db_session):
    token_a, user_a = _register(client, 3)
    _, user_b = _register(client, 4)
    db_session.add(ChatMessageDB(user_id=user_b, conversation_id="conv-b", sender="assistant", message="private B context"))
    db_session.commit()
    history = client.get("/api/v1/chat/history", headers=_auth(token_a))
    assert history.status_code == 200
    assert "private B context" not in history.text
    assert all(row.get("conversation_id") != "conv-b" for row in history.json()["messages"])


def test_targeted_lifecycle_notifications_user_and_operator_only(client, db_session):
    user_token, user_id = _register(client, 5)
    incident_id = f"INC-P8-{uuid4().hex[:8].upper()}"
    db_session.add(IncidentDB(
        incident_id=incident_id,
        description="Phase 8 notification incident",
        incident_type="chemical",
        category="chemical",
        location="V-Block",
        severity="critical",
        injured_count=2,
        user_id=user_id,
        required_departments=json.dumps(["MEDICAL", "SECURITY"]),
    ))
    db_session.commit()
    event_engine.publish_event("incident_assessed", incident_id, {"event_name": "incident_assessed"})
    user_rows = client.get("/api/v1/notifications", headers=_auth(user_token)).json()
    assert any(row["incident_id"] == incident_id and row["recipient_type"] == "user" for row in user_rows)
    assert all(row["recipient_type"] == "user" and row["incident_id"] == incident_id for row in user_rows if row["incident_id"] == incident_id)
    operator = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"}).json()["token"]
    operator_rows = client.get("/api/v1/notifications", headers=_auth(operator)).json()
    assert any(row["incident_id"] == incident_id and row["recipient_type"] == "admin" for row in operator_rows)


def test_notification_websocket_visibility_requires_exact_recipient_and_department():
    incident = {"user_id": "7", "departments": {"MEDICAL", "SECURITY"}}
    user = ConnectionScope(subject_type="user", role="user", user_id="7")
    department = ConnectionScope(subject_type="department", role="department_head", department="MEDICAL")
    assert should_deliver(user, "notification_created", incident, {"recipient_type": "user", "recipient_id": "7"})
    assert not should_deliver(user, "notification_created", incident, {"recipient_type": "user", "recipient_id": "8"})
    assert should_deliver(department, "notification_created", incident, {"recipient_type": "department", "department": "MEDICAL"})
    assert not should_deliver(department, "notification_created", incident, {"recipient_type": "department", "department": "SECURITY"})
