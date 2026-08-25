"""Idempotent, additive schema migration for CampusFlow AI.

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

from sqlalchemy import text
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
    ],
    "campus_resources": [
        ("department", "VARCHAR(50)", None),
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
    "routes": [
        ("assignment_id", "INTEGER", None),
        ("route_version", "INTEGER", "1"),
        ("geometry_source", "VARCHAR(60)", None),
        ("updated_at", "DATETIME", None),
    ],
    "route_replans": [
        ("assignment_id", "INTEGER", None),
        ("route_version", "INTEGER", None),
    ],
}


def _existing_columns(conn, table: str) -> List[str]:
    """Return the column names currently present on ``table`` (empty if none)."""
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    # PRAGMA table_info columns: cid, name, type, notnull, dflt_value, pk
    return [row[1] for row in rows]


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
