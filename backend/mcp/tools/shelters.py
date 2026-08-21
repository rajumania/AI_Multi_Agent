from typing import List, Optional, Dict, Any
from backend.mcp.tools.resources import query_resources


def find_nearby_shelters(
    location: Optional[str] = None,
    min_capacity: int = 100,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    MCP Tool: find_nearby_shelters
    Retrieves available emergency shelters and safe muster areas from campus SQLite database.
    """
    return query_resources(
        resource_type="shelter",
        availability_status="available",
        location=location,
        min_capacity=min_capacity,
        limit=limit
    )
