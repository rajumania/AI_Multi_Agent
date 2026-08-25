import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database.database import SessionLocal

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_login_seeded_admin_success(client):
    """Test logging in as the pre-seeded admin user."""
    res = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "password123"
    })
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "operator"

def test_login_invalid_credentials_fails(client):
    """Test that login fails with incorrect credentials."""
    res = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "wrongpassword"
    })
    assert res.status_code == 400
    assert "Invalid username or password" in res.json()["detail"]

def test_signup_and_login_flow_success(client):
    """Anonymous signup + login round-trip works, but a requested privileged
    role is clamped to a plain citizen ("user").

    Increment 1 closes the previous privilege-escalation hole where an
    unauthenticated caller could self-assign "operator" via /signup. Only an
    authenticated admin/operator may mint privileged or department accounts now
    (see the clamp in backend/api/auth.py:signup and backend/api/auth.py:
    department_register). This test was updated from asserting role=="operator"
    to role=="user" to reflect that required security fix.
    """
    import uuid
    test_uname = f"op_test_{uuid.uuid4().hex[:6]}"
    # Signup requesting "operator" — the server must silently downgrade to "user".
    signup_res = client.post("/api/v1/auth/signup", json={
        "username": test_uname,
        "password": "password123",
        "role": "operator",
        "full_name": "Test Operator"
    })
    assert signup_res.status_code == 200
    assert signup_res.json()["username"] == test_uname
    assert signup_res.json()["role"] == "user"  # privilege-escalation clamp

    # Login with newly created credentials still works.
    login_res = client.post("/api/v1/auth/login", json={
        "username": test_uname,
        "password": "password123"
    })
    assert login_res.status_code == 200
    data = login_res.json()
    assert "token" in data
    assert data["user"]["username"] == test_uname
    assert data["user"]["role"] == "user"  # clamped server-side, not "operator"

def test_signup_duplicate_username_fails(client):
    """Test that signup fails if the username is already registered."""
    res = client.post("/api/v1/auth/signup", json={
        "username": "admin",
        "password": "password123",
        "role": "student",
        "full_name": "Second Admin"
    })
    assert res.status_code == 400
    assert "Username is already taken" in res.json()["detail"]
