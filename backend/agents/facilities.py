from typing import Dict, Any, List, Optional
from backend.services.llm_service import llm_service


FACILITIES_AGENT_SYSTEM_PROMPT = """You are the specialized Facilities & Maintenance Operations Agent for AITAM Disaster Response AI.
Your duty is to assess infrastructure and chemical-exposure support hazards (electrical, plumbing, structural, HVAC, elevators, ventilation, utilities) and recommend isolation, shutdown, and repair-crew actions.

CRITICAL SAFETY RULES:
1. NEVER INVENT OR HALLUCINATE FACTS. State only facilities actions warranted by the specific incident.
2. RECOMMEND CONCRETE, AUDITABLE ACTIONS.
3. CLEARLY DISTINGUISH RECOMMENDATIONS FROM EXECUTED ACTIONS.

Output JSON format:
{
  "agent_name": "Facilities & Maintenance Agent",
  "infrastructure_risk_level": "low" | "medium" | "high" | "critical",
  "actions": [
    "action 1",
    "action 2"
  ],
  "recommended_facility_crews": 1 | 2 | 3,
  "utility_shutdown_required": true | false,
  "notes": "key infrastructure considerations"
}
"""


class FacilitiesAgent:
    """
    Specialized Facilities & Maintenance Agent:
    - Assesses electrical, plumbing, structural, and utility hazards.
    - Recommends isolation, safe utility shutdown, and repair-crew dispatch.
    - Grounds recommendations in real facility resources via MCP.
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
            f"Provide specific facilities/infrastructure recommendations in structured JSON."
        )

        try:
            if self.llm.is_gemini_available() or self.llm.is_openai_available():
                result = self.llm.generate_json_response(FACILITIES_AGENT_SYSTEM_PROMPT, prompt)
                if "actions" in result and isinstance(result["actions"], list):
                    return result
        except Exception:
            pass

        # Deterministic Safety Fallback & MCP Resource Grounding
        from backend.mcp.server import mcp_server

        # Query real facility hazard crews via MCP (SQLite-backed, no fabrication).
        discovered_units = mcp_server.call_tool(
            "find_nearby_resources",
            {"resource_type": "facility", "location": location, "limit": 3},
        )
        unit_ids = [u["resource_id"] for u in discovered_units]

        actions: List[str] = []
        is_high = severity in ["high", "critical"]

        if incident_type == "facility":
            if unit_ids:
                actions.append(f"Dispatch facilities hazard crew ({', '.join(unit_ids[:2])}) to {location}.")
            else:
                actions.append(f"Dispatch nearest facilities hazard crew to {location}.")
            actions.append("Isolate the affected electrical/plumbing system and cordon the hazard area.")
            infrastructure_risk_level = "critical" if severity == "critical" else "high"
            units = 2 if is_high else 1
            utility_shutdown = True
        elif incident_type == "chemical":
            if unit_ids:
                actions.append(f"Stage facilities crew ({unit_ids[0]}) to isolate ventilation/utilities serving the affected chemical area at {location}.")
            else:
                actions.append(f"Assess ventilation and utilities serving the chemical hazard area at {location}.")
            actions.append("Support area isolation and coordinate safe utility shutdown with the hazmat response lead.")
            infrastructure_risk_level = "high" if is_high else "medium"
            units = 1
            utility_shutdown = True
        elif incident_type == "fire":
            if unit_ids:
                actions.append(f"Cut power and gas to the affected block via facilities crew ({unit_ids[0]}).")
            else:
                actions.append("Cut power and gas to the affected block to support fire suppression.")
            actions.append("Ensure fire pumps/hydrant supply are pressurized and elevators recalled to ground.")
            infrastructure_risk_level = "high"
            units = 1
            utility_shutdown = True
        elif incident_type == "weather":
            actions.append(f"Inspect {location} for structural, drainage, and roof integrity; secure loose fixtures.")
            if unit_ids:
                actions.append(f"Stage facilities crew ({unit_ids[0]}) for rapid structural response.")
            infrastructure_risk_level = "high" if is_high else "medium"
            units = 1
            utility_shutdown = False
        else:
            actions.append(f"Assess {location} for utility and structural hazards; make safe as needed.")
            infrastructure_risk_level = "medium" if is_high else "low"
            units = 1
            utility_shutdown = False

        return {
            "agent_name": "Facilities & Maintenance Agent",
            "infrastructure_risk_level": infrastructure_risk_level,
            "actions": actions,
            "recommended_facility_crews": units,
            "utility_shutdown_required": utility_shutdown,
            "matched_resources": discovered_units,
            "notes": f"Facilities posture calibrated for {incident_type.upper()} incident at {location}.",
        }


facilities_agent = FacilitiesAgent()
