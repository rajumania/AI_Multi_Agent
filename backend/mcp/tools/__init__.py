"""
AITAM Disaster Response AI - MCP Resource Coordination Tools
"""
from backend.mcp.tools.resources import query_resources
from backend.mcp.tools.ambulances import find_available_ambulances
from backend.mcp.tools.security import find_security_units
from backend.mcp.tools.medical import find_first_aid_units
from backend.mcp.tools.shelters import find_nearby_shelters
from backend.mcp.tools.transport import find_available_campus_vehicles
from backend.mcp.tools.facilities import find_facility_resources, find_nearby_resources

__all__ = [
    "query_resources",
    "find_available_ambulances",
    "find_security_units",
    "find_first_aid_units",
    "find_nearby_shelters",
    "find_available_campus_vehicles",
    "find_facility_resources",
    "find_nearby_resources",
]
