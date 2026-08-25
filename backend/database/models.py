from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, Text
from backend.database.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class IncidentDB(Base):
    __tablename__ = "incidents"

    incident_id = Column(String(50), primary_key=True, index=True)
    description = Column(Text, nullable=False)
    incident_type = Column(String(50), default="unknown", index=True)
    location = Column(String(100), nullable=False, index=True)
    severity = Column(String(50), default="unknown", index=True)
    injured_count = Column(Integer, nullable=True)  # Strictly null if unknown
    evidence_source = Column(String(100), nullable=True)
    reported_by = Column(String(100), default="Campus Operator")
    status = Column(String(50), default="reported", index=True)
    ai_provider_status = Column(String(50), default="PENDING", index=True)
    current_step = Column(String(200), default="Emergency report received and logged in system.")
    next_action = Column(String(200), default="Intake assessment and category classification.")
    summary = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    resolution_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # --- Increment 1 additions (multi-role / RBAC foundation) ---
    # Which authenticated user reported this incident (citizen/user portal).
    # Nullable so existing operator-created incidents remain valid.
    user_id = Column(String(50), index=True, nullable=True)
    # Precise coordinates supplied by the reporter (real device GPS), if any.
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    # Classified category (mirrors incident_type; kept distinct per Part 6 spec).
    category = Column(String(50), nullable=True, index=True)
    # JSON list of departments the supervisor routed this incident to.
    required_departments = Column(Text, nullable=True)
    # Verified-resolution metadata (Main Admin closes; not auto-resolved).
    resolved_by = Column(String(100), nullable=True)
    resolution_message = Column(Text, nullable=True)


class CampusResourceDB(Base):
    __tablename__ = "campus_resources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False, index=True)
    location = Column(String(100), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    availability_status = Column(String(50), default="available", index=True)
    capacity = Column(Integer, nullable=True)
    quantity = Column(Integer, default=1)
    contact = Column(String(100), nullable=True)
    last_updated = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # --- Increment 1 addition ---
    # Owning department (SECURITY/MEDICAL/TRANSPORT/COMMUNICATION/FIRE/FACILITIES).
    # Nullable + backfilled by migration from resource_type.
    department = Column(String(50), nullable=True, index=True)


class ResponsePlanDB(Base):
    __tablename__ = "response_plans"

    plan_id = Column(String(50), primary_key=True, index=True)
    incident_id = Column(String(50), index=True, nullable=False)
    title = Column(String(200), nullable=False)
    severity = Column(String(50), nullable=False)
    location = Column(String(100), nullable=False)
    recommended_actions = Column(Text, nullable=False)  # JSON serialized list of actions
    allocated_resources = Column(Text, nullable=False)  # JSON serialized list of resource IDs
    requires_approval = Column(String(10), default="true")  # "true" | "false"
    approval_status = Column(String(50), default="pending", index=True)  # "pending", "approved", "rejected"
    approved_by = Column(String(100), nullable=True)
    approval_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class AuditLogDB(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(50), index=True, nullable=True)
    plan_id = Column(String(50), index=True, nullable=True)
    action_type = Column(String(100), index=True, nullable=False)
    actor = Column(String(100), default="system")
    description = Column(Text, nullable=False)
    details = Column(Text, nullable=True)  # JSON serialized payload
    timestamp = Column(DateTime(timezone=True), default=utc_now, index=True)


class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(100), nullable=False)
    role = Column(String(50), default="operator")  # "operator" | "admin" | "user"
    full_name = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # --- Increment 1 additions ---
    # Citizen/user portal identity is email + phone (Part 4). Nullable so the
    # existing seeded `admin` operator row stays valid.
    email = Column(String(120), index=True, nullable=True)
    phone = Column(String(30), nullable=True)
    # Optional department affiliation for operator/admin accounts (usually null).
    department = Column(String(50), nullable=True)
    status = Column(String(30), default="active")  # "active" | "suspended"


# ---------------------------------------------------------------------------
# Increment 1 — new tables (Part 14 required schema).
# All strictly additive; created by Base.metadata.create_all at startup.
# ---------------------------------------------------------------------------


class DepartmentUserDB(Base):
    """Staff accounts that log in with email + password + department (Part 5)."""

    __tablename__ = "department_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(120), unique=True, index=True, nullable=False)
    hashed_password = Column(String(100), nullable=False)
    full_name = Column(String(100), nullable=True)
    department = Column(String(50), index=True, nullable=False)
    role = Column(String(50), default="department")  # "department" | "department_head"
    status = Column(String(30), default="active")  # "active" | "suspended"
    created_at = Column(DateTime(timezone=True), default=utc_now)


class IncidentStatusHistoryDB(Base):
    """Append-only trail of incident status transitions (source of truth)."""

    __tablename__ = "incident_status_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(50), index=True, nullable=False)
    from_status = Column(String(50), nullable=True)
    to_status = Column(String(50), nullable=False)
    actor = Column(String(100), nullable=True)  # who caused the transition
    actor_role = Column(String(50), nullable=True)
    note = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=utc_now, index=True)


class AgentRunDB(Base):
    """One row per agent invocation for an incident (lifecycle timing)."""

    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(50), index=True, nullable=False)
    agent = Column(String(60), index=True, nullable=False)  # e.g. "security_agent"
    department = Column(String(50), index=True, nullable=True)
    status = Column(String(30), default="started")  # started|completed|failed
    summary = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), default=utc_now, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class AgentEventDB(Base):
    """Fine-grained agent activity events (drives 3D viz + activity history)."""

    __tablename__ = "agent_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(50), index=True, nullable=False)
    agent_id = Column(String(60), index=True, nullable=False)  # e.g. "SECURITY"
    department = Column(String(50), index=True, nullable=True)
    event_type = Column(String(60), nullable=False)  # AGENT_STARTED, TOOL_CALLED, ...
    status = Column(String(30), nullable=True)  # WORKING|COMPLETED|WAITING|FAILED
    message = Column(Text, nullable=True)
    details = Column(Text, nullable=True)  # JSON serialized payload
    timestamp = Column(DateTime(timezone=True), default=utc_now, index=True)


class DepartmentResponseDB(Base):
    """A department's response record for an incident (accept/act/complete)."""

    __tablename__ = "department_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(50), index=True, nullable=False)
    department = Column(String(50), index=True, nullable=False)
    status = Column(String(40), default="notified", index=True)
    # notified | acknowledged | accepted | en_route | on_scene | completed
    accepted = Column(Integer, default=0)  # 0/1 boolean
    message = Column(Text, nullable=True)
    responder = Column(String(100), nullable=True)  # dept staff email/name
    assigned_resources = Column(Text, nullable=True)  # JSON list of resource_ids
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ResourceAssignmentDB(Base):
    """Links resources to incidents/plans with dispatch lifecycle state."""

    __tablename__ = "resource_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(50), index=True, nullable=False)
    plan_id = Column(String(50), index=True, nullable=True)
    resource_id = Column(String(50), index=True, nullable=False)
    department = Column(String(50), index=True, nullable=True)
    status = Column(String(30), default="assigned")  # assigned|dispatched|released
    assigned_at = Column(DateTime(timezone=True), default=utc_now)
    released_at = Column(DateTime(timezone=True), nullable=True)


class RouteDB(Base):
    """Computed route for a dispatched resource (Dijkstra over campus graph)."""

    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(50), index=True, nullable=False)
    assignment_id = Column(Integer, index=True, nullable=True)
    resource_id = Column(String(50), index=True, nullable=True)
    origin = Column(String(100), nullable=True)
    destination = Column(String(100), nullable=True)
    path = Column(Text, nullable=True)  # JSON serialized list of nodes/coords
    distance_m = Column(Float, nullable=True)
    eta_seconds = Column(Float, nullable=True)
    status = Column(String(30), default="active")  # active|blocked|replaced
    route_version = Column(Integer, default=1, index=True)
    geometry_source = Column(String(60), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class RouteReplanDB(Base):
    """Records a route recalculation when a segment is blocked."""

    __tablename__ = "route_replans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(50), index=True, nullable=False)
    assignment_id = Column(Integer, index=True, nullable=True)
    resource_id = Column(String(50), index=True, nullable=True)
    original_route = Column(Text, nullable=True)  # JSON
    blocked_segment = Column(String(200), nullable=True)
    new_route = Column(Text, nullable=True)  # JSON
    reason = Column(String(200), nullable=True)
    route_version = Column(Integer, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=utc_now, index=True)


class TransportTelemetryDB(Base):
    """Durable, assignment-scoped transport location history."""

    __tablename__ = "transport_telemetry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(String(50), index=True, nullable=False)
    assignment_id = Column(Integer, index=True, nullable=False)
    incident_id = Column(String(50), index=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)
    speed = Column(Float, nullable=True)
    heading = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)
    source = Column(String(30), default="REAL", nullable=False)


class RoadConditionDB(Base):
    """Authenticated road condition reports used for legitimate replanning."""

    __tablename__ = "road_conditions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    node_a = Column(String(80), index=True, nullable=False)
    node_b = Column(String(80), index=True, nullable=False)
    status = Column(String(20), index=True, nullable=False)  # blocked|cleared
    reason = Column(String(200), nullable=False)
    source = Column(String(40), default="operator_report", nullable=False)
    reported_by = Column(String(120), nullable=False)
    incident_id = Column(String(50), index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)


class NotificationDB(Base):
    """Persisted notifications targeted at users / departments / admin."""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recipient_type = Column(String(30), index=True, nullable=False)  # user|department|admin
    recipient_id = Column(String(60), index=True, nullable=True)  # user_id or dept name
    department = Column(String(50), index=True, nullable=True)
    incident_id = Column(String(50), index=True, nullable=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    level = Column(String(20), default="info")  # info|alert|critical
    read = Column(Integer, default=0)  # 0/1 boolean
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)


class ChatMessageDB(Base):
    """Chatbot conversation turns for the user portal (no internal reasoning)."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(50), index=True, nullable=True)
    incident_id = Column(String(50), index=True, nullable=True)
    user_id = Column(String(50), index=True, nullable=True)
    sender = Column(String(20), nullable=False)  # "user" | "assistant"
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)
