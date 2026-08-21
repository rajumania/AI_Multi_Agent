from typing import List, Optional, Dict, Any
from backend.mcp.tools.resources import query_resources


def find_first_aid_units(
    location: Optional[str] = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    MCP Tool: find_first_aid_units
    Retrieves available first-aid response units from campus SQLite database.
    """
    return query_resources(
        resource_type="first_aid",
        availability_status="available",
        location=location,
        limit=limit
    )
