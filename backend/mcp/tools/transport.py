from typing import List, Optional, Dict, Any
from backend.mcp.tools.resources import query_resources


def find_available_campus_vehicles(
    location: Optional[str] = None,
    min_capacity: int = 4,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    MCP Tool: find_available_campus_vehicles
    Retrieves available evacuation shuttles, vans, and emergency transport from campus SQLite database.
    """
    return query_resources(
        resource_type="vehicle",
        availability_status="available",
        location=location,
        min_capacity=min_capacity,
        limit=limit
    )
