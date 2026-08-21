"""
CampusFlow AI - Model Context Protocol (MCP) Server
Provides standard MCP tool registration, schema definitions, and invocation routing.
"""
from typing import Dict, Any, List, Callable, Optional
from backend.mcp.tools import (
    find_available_ambulances,
    find_security_units,
    find_first_aid_units,
    find_nearby_shelters,
    find_available_campus_vehicles,
    find_facility_resources,
    find_nearby_resources,
)


class MCPServer:
    """
    Model Context Protocol (MCP) Server for Campus Emergency Resource Retrieval.
    Decouples database and factual physical resource queries from LLM reasoning.
    """

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._register_default_tools()

    def register_tool(
        self,
        name: str,
        description: str,
        func: Callable,
        parameters_schema: Dict[str, Any]
    ):
        self._tools[name] = {
            "name": name,
            "description": description,
            "func": func,
            "parameters": parameters_schema
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        """Returns MCP tool definitions."""
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"]
            }
            for t in self._tools.values()
        ]

    def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Executes an MCP tool deterministically."""
        if tool_name not in self._tools:
            raise ValueError(f"Unknown MCP tool: '{tool_name}'")
        
        func = self._tools[tool_name]["func"]
        args = arguments or {}
        return func(**args)

    def _register_default_tools(self):
        self.register_tool(
            name="find_available_ambulances",
            description="Find available campus ambulances with location proximity and contact details.",
            func=find_available_ambulances,
            parameters_schema={
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "Target incident campus location"},
                    "limit": {"type": "integer", "default": 5}
                }
            }
        )

        self.register_tool(
            name="find_security_units",
            description="Find available campus security patrols and guard stations with capacity info.",
            func=find_security_units,
            parameters_schema={
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "Target incident campus location"},
                    "required_capacity": {"type": "integer", "default": 1},
                    "limit": {"type": "integer", "default": 5}
                }
            }
        )

        self.register_tool(
            name="find_first_aid_units",
            description="Find rapid response first aid units and medical teams.",
            func=find_first_aid_units,
            parameters_schema={
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "Target incident campus location"},
                    "limit": {"type": "integer", "default": 5}
                }
            }
        )

        self.register_tool(
            name="find_nearby_shelters",
            description="Find emergency campus shelters, safe muster zones, and capacity thresholds.",
            func=find_nearby_shelters,
            parameters_schema={
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "Target incident campus location"},
                    "min_capacity": {"type": "integer", "default": 100},
                    "limit": {"type": "integer", "default": 5}
                }
            }
        )

        self.register_tool(
            name="find_available_campus_vehicles",
            description="Find evacuation buses, transport vans, and logistics vehicles.",
            func=find_available_campus_vehicles,
            parameters_schema={
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "Target incident campus location"},
                    "min_capacity": {"type": "integer", "default": 4},
                    "limit": {"type": "integer", "default": 5}
                }
            }
        )

        self.register_tool(
            name="find_facility_resources",
            description="Find facility hazard teams and fire response equipment units.",
            func=find_facility_resources,
            parameters_schema={
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "Target incident campus location"},
                    "limit": {"type": "integer", "default": 5}
                }
            }
        )

        self.register_tool(
            name="find_nearby_resources",
            description="General search across all campus emergency resource inventories.",
            func=find_nearby_resources,
            parameters_schema={
                "type": "object",
                "properties": {
                    "resource_type": {"type": "string", "description": "Optional category filter"},
                    "location": {"type": "string", "description": "Target incident campus location"},
                    "availability": {"type": "string", "default": "available"},
                    "limit": {"type": "integer", "default": 10}
                }
            }
        )


mcp_server = MCPServer()
