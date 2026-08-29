"""Idempotent, additive schema migration for AITAM Disaster Response AI.

SQLite's ``CREATE TABLE`` (via ``Base.metadata.create_all``) creates any brand
new tables, but it will NOT add new columns to tables that already exist from a
previous build. This module bridges that gap: it inspects each pre-existing
table with ``PRAGMA table_info`` and issues ``ALTER TABLE ... ADD COLUMN`` for
any column defined in models.py that is missing on disk.

Design guarantees:
  * Additive only — never drops or rewrites columns/tables/data.
  * Idempotent — safe to run on every startup; a fully migrated DB is a no-op.
  * Fresh DB safe — after create_all on a new DB every column already exists,
    so this simply verifies and backfills nothing.

Call ``ensure_schema(engine)`` AFTER ``Base.metadata.create_all(...)`` and
BEFORE seeding.

IMPORTANT: keep ADDITIVE_COLUMNS in sync with the "Increment 1 additions" in
backend/database/models.py.
"""

from typing import Dict, List, Tuple

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from backend.services.departments import RESOURCE_TYPE_TO_DEPARTMENT

# table -> list of (column_name, column_type_sql, default_sql | None)
# Only columns ADDED in Increment 1 to PRE-EXISTING tables belong here.
# New tables are handled entirely by Base.metadata.create_all.
ADDITIVE_COLUMNS: Dict[str, List[Tuple[str, str, str]]] = {
    "incidents": [
        ("user_id", "VARCHAR(50)", None),
        ("latitude", "FLOAT", None),
        ("longitude", "FLOAT", None),
        ("category", "VARCHAR(50)", None),
        ("required_departments", "TEXT", None),
        ("ai_provider_status", "VARCHAR(50)", "'PENDING'"),
        ("resolved_by", "VARCHAR(100)", None),
        ("resolution_message", "TEXT", None),
        ("disaster_type", "VARCHAR(50)", None),
        ("region_id", "VARCHAR(50)", None),
        ("zone_id", "VARCHAR(50)", None),
        ("community_id", "VARCHAR(50)", None),
        ("image_url", "VARCHAR(500)", None),
        ("detection_evidence", "TEXT", None),
        ("client_operation_id", "VARCHAR(100)", None),
    ],
    "campus_resources": [
        ("department", "VARCHAR(50)", None),
        ("current_assignment", "VARCHAR(100)", None),
        ("emergency_beds", "INTEGER", None),
        ("is_demo", "INTEGER", "0"),
    ],
    "users": [
        ("email", "VARCHAR(120)", None),
        ("phone", "VARCHAR(30)", None),
        ("department", "VARCHAR(50)", None),
        ("status", "VARCHAR(30)", "'active'"),
    ],
    "chat_messages": [
        ("conversation_id", "VARCHAR(50)", None),
    ],
    "notifications": [
        ("alert_type", "VARCHAR(50)", None),
        ("audience", "VARCHAR(50)", None),
        ("region_id", "VARCHAR(50)", None),
        ("zone_id", "VARCHAR(50)", None),
        ("expires_at", "TIMESTAMP", None),
        ("is_demo", "INTEGER", "0"),
        ("priority", "VARCHAR(20)", "'medium'"),
        ("lifecycle_status", "VARCHAR(20)", "'CREATED'"),
        ("delivered_at", "TIMESTAMP", None),
        ("read_at", "TIMESTAMP", None),
        ("event_key", "VARCHAR(160)", None),
        ("details_json", "TEXT", None),
    ],
    "zones": [
        ("elevation_m", "FLOAT", None),
        ("slope_deg", "FLOAT", None),
        ("vulnerability_score", "FLOAT", None),
        ("historical_disaster_frequency", "FLOAT", None),
        ("river_proximity_km", "FLOAT", None),
        ("drainage_vulnerability", "FLOAT", None),
        ("hazard_classification", "VARCHAR(80)", None),
        ("coastal_vulnerability", "FLOAT", None),
    ],
    "weather_observations": [
        ("location", "VARCHAR(120)", None),
        ("latitude", "FLOAT", None),
        ("longitude", "FLOAT", None),
        ("received_at", "TIMESTAMP", None),
        ("rainfall_intensity", "FLOAT", None),
        ("humidity", "FLOAT", None),
        ("wind_direction", "FLOAT", None),
        ("pressure", "FLOAT", None),
        ("precipitation_probability", "FLOAT", None),
    ],
    "environmental_observations": [
        ("location", "VARCHAR(120)", None),
        ("latitude", "FLOAT", None),
        ("longitude", "FLOAT", None),
        ("received_at", "TIMESTAMP", None),
    ],
    "risk_predictions": [
        ("prediction_id", "VARCHAR(60)", None),
        ("risk_score", "FLOAT", None),
        ("confidence", "FLOAT", None),
        ("features", "TEXT", None),
        ("contributing_factors", "TEXT", None),
        ("recommendations", "TEXT", None),
        ("explanation", "TEXT", None),
        ("data_status", "VARCHAR(30)", "'demo'"),
        ("data_freshness_seconds", "FLOAT", None),
        ("stale", "INTEGER", "0"),
    ],
    "agent_runs": [
        ("run_id", "VARCHAR(60)", None),
        ("event_id", "VARCHAR(60)", None),
        ("required_agents", "TEXT", None),
        ("agent_results", "TEXT", None),
        ("agent_errors", "TEXT", None),
        ("created_at", "TIMESTAMP", None),
    ],
    "routes": [
        ("assignment_id", "INTEGER", None),
        ("route_version", "INTEGER", "1"),
        ("geometry_source", "VARCHAR(60)", None),
        ("updated_at", "TIMESTAMP", None),
    ],
    "route_replans": [
        ("assignment_id", "INTEGER", None),
        ("route_version", "INTEGER", None),
    ],
}


def _existing_columns(conn, table: str) -> List[str]:
    """Return column names currently present on a table."""
    inspector = inspect(conn)

    if not inspector.has_table(table):
        return []

    return [column["name"] for column in inspector.get_columns(table)]

def ensure_schema(engine: Engine) -> Dict[str, List[str]]:
    """Add any missing Increment-1 columns to pre-existing tables.

    Returns a dict of {table: [columns_added]} for logging/verification.
    """
    added: Dict[str, List[str]] = {}

    with engine.begin() as conn:
        for table, columns in ADDITIVE_COLUMNS.items():
            present = _existing_columns(conn, table)
            if not present:
                # Table doesn't exist yet — create_all will build it fresh with
                # all columns already defined, so nothing to ALTER here.
                continue

            for name, col_type, default_sql in columns:
                if name in present:
                    continue
                ddl = f"ALTER TABLE {table} ADD COLUMN {name} {col_type}"
                if default_sql is not None:
                    ddl += f" DEFAULT {default_sql}"
                conn.execute(text(ddl))
                added.setdefault(table, []).append(name)

        # --- Backfills (safe / idempotent) ---
        _backfill(conn)

        # A nullable unique index allows legacy rows to remain untouched while
        # making retries of an offline report resolve to the original record.
        if "client_operation_id" in _existing_columns(conn, "incidents"):
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_incidents_client_operation_id "
                "ON incidents (client_operation_id)"
            ))
        if "event_key" in _existing_columns(conn, "notifications"):
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_notifications_event_key "
                "ON notifications (event_key)"
            ))

    return added


def _backfill(conn) -> None:
    """Populate newly added columns with sensible values from existing data."""
    # 1) campus_resources.department <- derived from resource_type.
    if "department" in _existing_columns(conn, "campus_resources"):
        for resource_type, department in RESOURCE_TYPE_TO_DEPARTMENT.items():
            conn.execute(
                text(
                    "UPDATE campus_resources SET department = :dept "
                    "WHERE resource_type = :rt "
                    "AND (department IS NULL OR department = '')"
                ),
                {"dept": department, "rt": resource_type},
            )

    # 2) incidents.category <- mirror of incident_type when not set.
    incident_cols = _existing_columns(conn, "incidents")
    if "category" in incident_cols and "incident_type" in incident_cols:
        conn.execute(
            text(
                "UPDATE incidents SET category = incident_type "
                "WHERE category IS NULL OR category = ''"
            )
        )

    # 3) users.status <- default 'active' for any legacy NULLs.
    if "status" in _existing_columns(conn, "users"):
        conn.execute(
            text(
                "UPDATE users SET status = 'active' "
                "WHERE status IS NULL OR status = ''"
            )
        )

    # 4) Legacy observations did not track receipt time. Treat their
    # observation timestamp as the best available receipt time so old rows
    # remain readable and are honestly subject to freshness checks.
    for table in ("weather_observations", "environmental_observations"):
        columns = _existing_columns(conn, table)
        if "received_at" in columns and "observed_at" in columns:
            conn.execute(
                text(
                    f"UPDATE {table} SET received_at = observed_at "
                    "WHERE received_at IS NULL"
                )
            )
