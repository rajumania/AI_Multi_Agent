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
    current_step = Column(String(200), default="Emergency report received and logged in system.")
    next_action = Column(String(200), default="Intake assessment and category classification.")
    summary = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    resolution_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


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
    role = Column(String(50), default="operator")  # "operator" | "student"
    full_name = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)


