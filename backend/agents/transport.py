from typing import Dict, Any, List, Optional
from backend.services.llm_service import llm_service


TRANSPORT_AGENT_SYSTEM_PROMPT = """You are the specialized Transport & Evacuation Logistics Agent for CAMPUSFLOW AI.
Your duty is to assess mobility requirements, emergency corridor routing, evacuation shuttle dispatch, and parking/gate management.

CRITICAL SAFETY RULES:
1. NEVER INVENT NON-EXISTENT FLEET CAPACITIES.
2. RECOMMEND CONCRETE TRAFFIC AND TRANSIT CONTROLS.

Output JSON format:
{
  "agent_name": "Transport Agent",
  "route_status": "open" | "restricted" | "blocked",
  "actions": [
    "action 1",
    "action 2"
  ],
  "recommended_vehicles": 0 | 1 | 2 | 3,
  "evacuation_shuttles_required": 0 | 1 | 2,
  "traffic_rerouting_active": true | false
}
"""


class TransportAgent:
    """
    Specialized Transport Agent:
    - Coordinates campus emergency vehicles and evacuation shuttles.
    - Manages perimeter traffic flow, keeps ambulance corridors clear.
    """

    def __init__(self):
        self.llm = llm_service

    def evaluate(
        self,
        incident_type: str,
        severity: str,
        location: str,
        description: str,
    ) -> Dict[str, Any]:
        prompt = (
            f"INCIDENT DETAILS:\n"
            f"Type: {incident_type}\n"
            f"Severity: {severity}\n"
            f"Location: {location}\n"
            f"Description: {description}\n\n"
            f"Provide specific transport and traffic coordination recommendations in structured JSON."
        )

        try:
            if self.llm.is_gemini_available() or self.llm.is_openai_available():
                result = self.llm.generate_json_response(TRANSPORT_AGENT_SYSTEM_PROMPT, prompt)
                if "actions" in result and isinstance(result["actions"], list):
                    return result
        except Exception:
            pass

        # Deterministic Safety Fallback & MCP Resource Grounding
        from backend.mcp.server import mcp_server

        discovered_vehicles = mcp_server.call_tool("find_available_campus_vehicles", {"location": location, "limit": 2})
        discovered_shelters = mcp_server.call_tool("find_nearby_shelters", {"location": location, "limit": 2})

        veh_ids = [v["resource_id"] for v in discovered_vehicles]
        shelter_names = [s["name"] for s in discovered_shelters]

        actions = []
        is_high = severity in ["high", "critical"]

        if incident_type in ["fire", "accident"]:
            actions.append(f"Clear and designate primary emergency vehicle route to {location}.")
            actions.append("Direct non-emergency vehicles away from adjacent access avenues.")
            if is_high:
                if veh_ids:
                    actions.append(f"Dispatch Campus Emergency Vehicle ({veh_ids[0]}) for perimeter safety barrier transport.")
                else:
                    actions.append("Dispatch available campus van for perimeter safety barrier transport.")
            route_status = "restricted"
            vehicles = 1 if is_high else 0
            shuttles = 1 if severity == "critical" else 0
            reroute = True
        elif incident_type == "weather":
            target_shelter = shelter_names[0] if shelter_names else "North Campus Shelter"
            if veh_ids:
                actions.append(f"Deploy Campus Shuttles ({', '.join(veh_ids)}) to transfer students to {target_shelter}.")
            else:
                actions.append(f"Deploy emergency shuttles to transfer students to {target_shelter}.")
            actions.append("Close low-lying pathways subject to waterlogging.")
            route_status = "restricted"
            vehicles = 2
            shuttles = 2
            reroute = True
        elif incident_type == "crowd":
            actions.append(f"Restrict vehicular access within 200m of {location}.")
            actions.append("Coordinate shuttle staging at East Gate parking zone.")
            route_status = "restricted"
            vehicles = 1
            shuttles = 1
            reroute = True
        else:
            actions.append(f"Maintain normal transit routes with caution advisory near {location}.")
            route_status = "open"
            vehicles = 0
            shuttles = 0
            reroute = False

        matched = discovered_vehicles + discovered_shelters

        return {
            "agent_name": "Transport Agent",
            "route_status": route_status,
            "actions": actions,
            "recommended_vehicles": vehicles,
            "evacuation_shuttles_required": shuttles,
            "traffic_rerouting_active": reroute,
            "matched_resources": matched
        }



transport_agent = TransportAgent()
