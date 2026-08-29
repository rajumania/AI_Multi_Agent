"""Pytest fixtures for the CampusFlow AI auth / RBAC / departments suite.

Isolation strategy
------------------
Before *any* backend module is imported we repoint ``DATABASE_URL`` at a
throwaway SQLite file and disable the anonymous-admin migration shim. Because
``backend.config.settings`` (and therefore ``backend.database.database.engine``)
is created at import time, doing this first guarantees the whole app binds to a
disposable database and never touches the real ``campusflow.db``.

Run from the repository root so the ``backend`` package is importable:

    pytest backend/tests -q
"""

import os
import tempfile
from pathlib import Path

# --- Must happen before importing anything under backend.* -----------------
_TMP_DB_FD, _TMP_DB_PATH = tempfile.mkstemp(prefix="campusflow_test_", suffix=".db")
os.close(_TMP_DB_FD)
# Use a POSIX-style path in the URL so it is valid on both Windows
# (sqlite:///C:/Users/.../file.db) and POSIX (sqlite:////tmp/file.db).
_DB_URL = f"sqlite:///{Path(_TMP_DB_PATH).as_posix()}"
os.environ["DATABASE_URL"] = _DB_URL
# Default the migration shim OFF so RBAC is genuinely exercised. Tests that want
# the legacy anonymous-operator behavior flip settings.ALLOW_ANONYMOUS_ADMIN on
# explicitly (it is read at request time inside get_command_principal).
os.environ["ALLOW_ANONYMOUS_ADMIN"] = "false"
# Existing endpoint tests invoke analysis/orchestration explicitly. Keep those
# tests focused and deterministic; the Phase 7.3 background path has dedicated
# tests that enable this setting explicitly.
os.environ["AUTOMATIC_AI_WORKFLOW"] = "false"
# Keep the isolated regression suite deterministic and network-free. Phase 9A
# provider tests inject mocked clients directly; live provider verification is
# performed separately against the configured runtime environment.
os.environ["WEATHER_PROVIDER"] = "demo"
os.environ["ENVIRONMENT_PROVIDER"] = "demo"
os.environ["SENSOR_PROVIDER"] = "demo"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.config import settings  # noqa: E402
from backend.database.database import engine, Base, SessionLocal  # noqa: E402
from backend.database import models  # noqa: E402  (registers ORM tables on Base)
from backend.database.migrate import ensure_schema  # noqa: E402
from backend.database.seed import seed_resources, seed_users, seed_disaster_domain  # noqa: E402
from backend.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _prepare_database():
    """Create the schema, run the additive migration, and seed once per run."""
    # Sanity: we must be pointed at the throwaway DB, never the real one.
    assert Path(_TMP_DB_PATH).name in settings.DATABASE_URL, "test DB isolation failed"
    assert "campusflow_test_" in settings.DATABASE_URL, "test DB isolation failed"

    Base.metadata.create_all(bind=engine)
    ensure_schema(engine)  # idempotent; no-op columns on a fresh create_all
    db = SessionLocal()
    try:
        seed_resources(db)
        seed_disaster_domain(db)
        seed_users(db)
    finally:
        db.close()

    yield

    engine.dispose()
    try:
        os.remove(_TMP_DB_PATH)
    except OSError:
        pass


@pytest.fixture()
def client():
    """A FastAPI TestClient bound to the real app (no lifespan; DB is prepared
    by the session fixture above)."""
    return TestClient(app)


@pytest.fixture()
def db_session():
    """A raw session against the test database for direct assertions."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def anonymous_admin_on():
    """Temporarily enable the legacy anonymous-operator shim for one test."""
    previous = settings.ALLOW_ANONYMOUS_ADMIN
    settings.ALLOW_ANONYMOUS_ADMIN = True
    try:
        yield
    finally:
        settings.ALLOW_ANONYMOUS_ADMIN = previous


# --- Convenience login helpers ---------------------------------------------

def operator_token(client: TestClient) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def department_token(client: TestClient, email: str, department: str) -> str:
    resp = client.post(
        "/api/v1/auth/department/login",
        json={"email": email, "password": "password123", "department": department},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def citizen_token(client: TestClient) -> str:
    resp = client.post(
        "/api/v1/auth/user/login",
    json={"email": "community@aitam.local", "phone": "9000000000"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
