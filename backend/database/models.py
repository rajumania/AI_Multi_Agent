from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Index
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
    reported_by = Column(String(100), default="Community Reporter")
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
    # Disaster-domain links are nullable to preserve every legacy incident.
    disaster_type = Column(String(50), nullable=True, index=True)
    region_id = Column(String(50), nullable=True, index=True)
    zone_id = Column(String(50), nullable=True, index=True)
    community_id = Column(String(50), nullable=True, index=True)
    # Optional reporter-provided evidence reference; the binary asset remains
    # outside this database and is never required for sensor-driven events.
    image_url = Column(String(500), nullable=True)
    # Structured evidence-fusion result for Admin/audit consumers. Nullable so
    # all existing incidents remain compatible with the additive migration.
    detection_evidence = Column(Text, nullable=True)
    # Client-generated idempotency key used by offline report replay. Nullable
    # keeps all existing/operator-created rows compatible with the migration.
    client_operation_id = Column(String(100), unique=True, index=True, nullable=True)


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
    current_assignment = Column(String(100), nullable=True, index=True)
    emergency_beds = Column(Integer, nullable=True)
    is_demo = Column(Integer, default=0, nullable=False)


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


class OrganizationDB(Base):
    """Authoritative organization record for persisted administration data."""

    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(40), unique=True, index=True, nullable=False)
    name = Column(String(160), nullable=False)
    status = Column(String(30), default="active", index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class DepartmentDB(Base):
    """Persisted organization department registry managed by an admin."""

    __tablename__ = "organization_departments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, index=True, nullable=False)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(120), nullable=False)
    department_type = Column(String(80), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(30), default="active", index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


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
    # Aggregate execution metadata used by the Phase 3 disaster graph.
    run_id = Column(String(60), unique=True, index=True, nullable=True)
    event_id = Column(String(60), index=True, nullable=True)
    required_agents = Column(Text, nullable=True)
    agent_results = Column(Text, nullable=True)
    agent_errors = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True, nullable=True)


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

    __table_args__ = (
        Index("uq_department_response_incident_department", "incident_id", "department", unique=True),
    )


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
    # Alert metadata is additive; existing notifications remain valid alerts.
    alert_type = Column(String(50), nullable=True, index=True)
    audience = Column(String(50), nullable=True)
    region_id = Column(String(50), nullable=True, index=True)
    zone_id = Column(String(50), nullable=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_demo = Column(Integer, default=0, nullable=False)
    # Operational notification lifecycle. These additive fields preserve all
    # legacy rows while making delivery/read state and safe structured context
    # durable across WebSocket reconnects.
    priority = Column(String(20), default="medium", nullable=False)
    lifecycle_status = Column(String(20), default="CREATED", nullable=False)  # CREATED|DELIVERED|READ|FAILED
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    event_key = Column(String(160), nullable=True, index=True)
    details_json = Column(Text, nullable=True)

    __table_args__ = (
        Index("uq_notification_event_key", "event_key", unique=True),
    )


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


class RegionDB(Base):
    """Administrative/geographic area used by disaster risk and response APIs."""

    __tablename__ = "regions"

    id = Column(String(50), primary_key=True)
    name = Column(String(120), nullable=False, index=True)
    risk_status = Column(String(30), default="demo", nullable=False)
    population = Column(Integer, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_demo = Column(Integer, default=0, nullable=False)


class ZoneDB(Base):
    """A response zone within a region."""

    __tablename__ = "zones"

    id = Column(String(50), primary_key=True)
    region_id = Column(String(50), index=True, nullable=False)
    name = Column(String(120), nullable=False, index=True)
    risk_status = Column(String(30), default="demo", nullable=False)
    population = Column(Integer, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    elevation_m = Column(Float, nullable=True)
    slope_deg = Column(Float, nullable=True)
    vulnerability_score = Column(Float, nullable=True)
    historical_disaster_frequency = Column(Float, nullable=True)
    river_proximity_km = Column(Float, nullable=True)
    drainage_vulnerability = Column(Float, nullable=True)
    hazard_classification = Column(String(80), nullable=True)
    coastal_vulnerability = Column(Float, nullable=True)
    is_demo = Column(Integer, default=0, nullable=False)


class CommunityDB(Base):
    """Community grouping for local reports and targeted alerts."""

    __tablename__ = "communities"

    id = Column(String(50), primary_key=True)
    zone_id = Column(String(50), index=True, nullable=True)
    name = Column(String(120), nullable=False, index=True)
    population = Column(Integer, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_demo = Column(Integer, default=0, nullable=False)


class WeatherObservationDB(Base):
    __tablename__ = "weather_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    region_id = Column(String(50), index=True, nullable=True)
    zone_id = Column(String(50), index=True, nullable=True)
    location = Column(String(120), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    observed_at = Column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)
    received_at = Column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)
    condition = Column(String(120), nullable=False)
    rainfall_mm = Column(Float, nullable=True)
    rainfall_intensity = Column(Float, nullable=True)
    temperature_c = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    wind_speed_kph = Column(Float, nullable=True)
    wind_direction = Column(Float, nullable=True)
    pressure = Column(Float, nullable=True)
    precipitation_probability = Column(Float, nullable=True)
    source = Column(String(50), default="demo", nullable=False)


class EnvironmentalObservationDB(Base):
    __tablename__ = "environmental_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    region_id = Column(String(50), index=True, nullable=True)
    zone_id = Column(String(50), index=True, nullable=True)
    location = Column(String(120), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    observed_at = Column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)
    received_at = Column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)
    indicator = Column(String(80), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(30), nullable=True)
    source = Column(String(50), default="demo", nullable=False)


class RiskPredictionDB(Base):
    """Storage foundation for Phase 2 risk predictions; no predictor runs yet."""

    __tablename__ = "risk_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prediction_id = Column(String(60), unique=True, index=True, nullable=True)
    region_id = Column(String(50), index=True, nullable=True)
    zone_id = Column(String(50), index=True, nullable=True)
    disaster_type = Column(String(50), index=True, nullable=False)
    risk_level = Column(String(30), index=True, nullable=False)
    probability = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    features = Column(Text, nullable=True)
    contributing_factors = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=True)
    explanation = Column(Text, nullable=True)
    data_status = Column(String(30), default="demo", nullable=False)
    data_freshness_seconds = Column(Float, nullable=True)
    stale = Column(Integer, default=0, nullable=False)
    rationale = Column(Text, nullable=True)
    valid_from = Column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(30), default="foundation", nullable=False)


class SensorObservationDB(Base):
    """Normalized environmental/sensor reading; demo readings are explicit."""

    __tablename__ = "sensor_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sensor_id = Column(String(80), index=True, nullable=False)
    sensor_type = Column(String(50), index=True, nullable=False)
    region_id = Column(String(50), index=True, nullable=True)
    zone_id = Column(String(50), index=True, nullable=True)
    location = Column(String(120), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    value = Column(Float, nullable=False)
    unit = Column(String(30), nullable=True)
    observed_at = Column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)
    received_at = Column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)
    source = Column(String(50), default="DEMO_SIMULATION", nullable=False)
    metadata_json = Column(Text, nullable=True)


class SensorEventDB(Base):
    """Detected sensor anomaly that can trigger the disaster graph."""

    __tablename__ = "sensor_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(60), unique=True, index=True, nullable=False)
    sensor_id = Column(String(80), index=True, nullable=False)
    sensor_type = Column(String(50), index=True, nullable=False)
    region_id = Column(String(50), index=True, nullable=True)
    zone_id = Column(String(50), index=True, nullable=True)
    previous_value = Column(Float, nullable=True)
    current_value = Column(Float, nullable=False)
    change_value = Column(Float, nullable=True)
    anomaly_level = Column(String(30), nullable=False)
    description = Column(Text, nullable=False)
    source = Column(String(50), default="DEMO_SIMULATION", nullable=False)
    status = Column(String(30), default="detected", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)


class RescueRequestDB(Base):
    """Community rescue intake; prioritization remains a later phase concern."""

    __tablename__ = "rescue_requests"

    request_id = Column(String(50), primary_key=True, index=True)
    location = Column(String(120), nullable=False, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    people_count = Column(Integer, nullable=False, default=1)
    injured_count = Column(Integer, nullable=False, default=0)
    children_count = Column(Integer, nullable=False, default=0)
    elderly_count = Column(Integer, nullable=False, default=0)
    medical_emergency = Column(Integer, nullable=False, default=0)
    hazard_level = Column(String(30), nullable=False, default="unknown")
    description = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="reported", index=True)
    priority_score = Column(Float, nullable=True)
    user_id = Column(String(50), nullable=True, index=True)
    incident_id = Column(String(50), nullable=True, index=True)
    region_id = Column(String(50), nullable=True, index=True)
    zone_id = Column(String(50), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
