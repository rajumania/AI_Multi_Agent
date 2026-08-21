from typing import List, Optional, Dict, Any
from backend.mcp.tools.resources import query_resources


def find_facility_resources(
    location: Optional[str] = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    MCP Tool: find_facility_resources
    Retrieves facility teams, hazard control units, and fire safety assets from campus SQLite database.
    """
    fac = query_resources(
        resource_type="facility",
        availability_status="available",
        location=location,
        limit=limit
    )
    fire = query_resources(
        resource_type="fire_response",
        availability_status="available",
        location=location,
        limit=limit
    )
    return fac + fire


def find_nearby_resources(
    resource_type: Optional[str] = None,
    location: Optional[str] = None,
    availability: str = "available",
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    MCP Tool: find_nearby_resources
    General location-aware resource discovery tool across all asset types.
    """
    return query_resources(
        resource_type=resource_type,
        availability_status=availability,
        location=location,
        limit=limit
    )
