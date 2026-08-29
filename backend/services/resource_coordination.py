"""Database-backed resource and facility discovery for disaster agents."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.database.models import CampusResourceDB


def available_resources(db: Session, zone_id: str | None = None) -> list[dict[str, Any]]:
    query = db.query(CampusResourceDB).filter(CampusResourceDB.availability_status.in_(["available", "AVAILABLE"]))
    rows = query.order_by(CampusResourceDB.resource_type.asc(), CampusResourceDB.name.asc()).all()
    return [_resource(row) for row in rows]


def resources_by_types(db: Session, types: set[str], zone_id: str | None = None) -> list[dict[str, Any]]:
    return [item for item in available_resources(db, zone_id) if item["resource_type"].lower() in {value.lower() for value in types}]


def _resource(row: CampusResourceDB) -> dict[str, Any]:
    return {"resource_id": row.resource_id, "name": row.name, "resource_type": row.resource_type, "location": row.location, "latitude": row.latitude, "longitude": row.longitude, "status": row.availability_status, "capacity": row.capacity, "quantity": row.quantity, "contact": row.contact, "last_updated": row.last_updated.isoformat() if row.last_updated else None, "department": row.department}


def nearest_facilities(db: Session, types: set[str], limit: int = 10) -> list[dict[str, Any]]:
    return resources_by_types(db, types)[:limit]
