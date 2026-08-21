from typing import List, Optional, Dict, Any
from backend.mcp.tools.resources import query_resources


def find_security_units(
    location: Optional[str] = None,
    required_capacity: int = 1,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    MCP Tool: find_security_units
    Retrieves active available security response units from campus SQLite database.
    """
    return query_resources(
        resource_type="security",
        availability_status="available",
        location=location,
        min_capacity=required_capacity,
        limit=limit
    )
