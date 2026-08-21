from typing import List, Optional, Dict, Any
from backend.mcp.tools.resources import query_resources


def find_available_ambulances(
    location: Optional[str] = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    MCP Tool: find_available_ambulances
    Retrieves available ambulances from campus SQLite resource database.
    """
    return query_resources(
        resource_type="ambulance",
        availability_status="available",
        location=location,
        limit=limit
    )
