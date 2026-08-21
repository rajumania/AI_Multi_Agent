from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.database.database import SessionLocal
from backend.database.models import CampusResourceDB


def get_db_session() -> Session:
    """Helper to acquire a database session for MCP tool execution."""
    return SessionLocal()


def query_resources(
    resource_type: Optional[str] = None,
    availability_status: str = "available",
    location: Optional[str] = None,
    min_capacity: Optional[int] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Core MCP query function:
    Queries real campus resources from SQLite.
    Supports filtering by type, availability, proximity, and capacity.
    """
    db = get_db_session()
    try:
        query = db.query(CampusResourceDB)

        if resource_type:
            query = query.filter(CampusResourceDB.resource_type == resource_type.lower().strip())

        if availability_status and availability_status.lower() != "all":
            query = query.filter(CampusResourceDB.availability_status == availability_status.lower().strip())

        if min_capacity:
            query = query.filter(CampusResourceDB.capacity >= min_capacity)

        resources = query.all()

        results = []
        for r in resources:
            item = {
                "resource_id": r.resource_id,
                "name": r.name,
                "resource_type": r.resource_type,
                "location": r.location,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "availability_status": r.availability_status,
                "capacity": r.capacity,
                "quantity": r.quantity,
                "contact": r.contact,
                "last_updated": r.last_updated,
            }
            results.append(item)


        # Location-aware sorting (simple proximity relevance heuristic)
        if location and results:
            loc_lower = location.lower()
            results.sort(
                key=lambda x: (
                    0 if loc_lower in x["location"].lower() or any(w in x["location"].lower() for w in loc_lower.split()) else 1
                )
            )

        return results[:limit]
    finally:
        db.close()
