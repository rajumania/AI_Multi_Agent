from typing import Dict, Any, List, Optional
from backend.services.llm_service import llm_service


FIRE_AGENT_SYSTEM_PROMPT = """You are the specialized Fire & Safety Operations Agent for CAMPUSFLOW AI.
Your duty is to assess fire, smoke, explosion, chemical/hazmat, and thermal hazards, recommend suppression/containment actions, and advise on evacuation of affected structures.

CRITICAL SAFETY RULES:
1. NEVER INVENT OR HALLUCINATE FACTS. State only fire-safety actions warranted by the specific incident.
2. RECOMMEND CONCRETE, AUDITABLE ACTIONS.
3. CLEARLY DISTINGUISH RECOMMENDATIONS FROM EXECUTED ACTIONS.

Output JSON format:
{
  "agent_name": "Fire & Safety Agent",
  "fire_risk_level": "low" | "medium" | "high" | "critical",
  "actions": [
    "action 1",
    "action 2"
  ],
  "recommended_fire_units": 1 | 2 | 3,
  "evacuation_required": true | false,
  "notes": "key fire-safety considerations"
}
"""


class FireAgent:
    """
    Specialized Fire & Safety Agent:
    - Assesses fire, smoke, explosion, and thermal hazards.
    - Recommends suppression, containment, and structure evacuation.
    - Grounds recommendations in real fire_response resources via MCP.
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
            f"Provide specific fire-safety recommendations in structured JSON."
        )

        try:
            if self.llm.is_gemini_available() or self.llm.is_openai_available():
                result = self.llm.generate_json_response(FIRE_AGENT_SYSTEM_PROMPT, prompt)
                if "actions" in result and isinstance(result["actions"], list):
                    return result
        except Exception:
            pass

        # Deterministic Safety Fallback & MCP Resource Grounding
        from backend.mcp.server import mcp_server

        # Query real fire response units via MCP (SQLite-backed, no fabrication).
        discovered_units = mcp_server.call_tool(
            "find_nearby_resources",
            {"resource_type": "fire_response", "location": location, "limit": 3},
        )
        unit_ids = [u["resource_id"] for u in discovered_units]

        actions: List[str] = []
        is_high = severity in ["high", "critical"]

        if incident_type == "fire":
            if unit_ids:
                actions.append(f"Dispatch fire safety squad ({', '.join(unit_ids[:2])}) to {location} for suppression.")
            else:
                actions.append(f"Deploy nearest fire suppression team to {location}.")
            actions.append("Activate fire alarm and isolate the affected block; charge nearest hydrants/extinguisher lines.")
            actions.append("Shut off gas/fuel and ventilation feeding the affected zone.")
            fire_risk_level = "critical" if severity == "critical" else "high"
            units = 2 if is_high else 1
            evacuation = True
        elif incident_type == "chemical":
            if unit_ids:
                actions.append(f"Stage fire/hazmat response unit ({', '.join(unit_ids[:2])}) at {location} for chemical hazard assessment and containment.")
            else:
                actions.append(f"Request fire/hazmat response for chemical hazard assessment and containment at {location}.")
            actions.append("Isolate the affected area, keep ignition sources away, and do not enter until the hazard is assessed.")
            fire_risk_level = "critical" if severity == "critical" else "high"
            units = 1
            evacuation = severity in ("high", "critical")
        elif incident_type == "accident":
            if unit_ids:
                actions.append(f"Stage fire unit ({unit_ids[0]}) on standby for fuel/electrical fire risk at {location}.")
            else:
                actions.append(f"Position a fire watch on standby at {location} for fuel/electrical fire risk.")
            actions.append("Deploy extinguishers and absorbent for any fuel leak; prohibit ignition sources.")
            fire_risk_level = "high" if is_high else "medium"
            units = 1
            evacuation = is_high
        elif incident_type in ("facility", "weather"):
            actions.append(f"Inspect {location} for electrical/structural fire hazards and isolate faulty circuits.")
            if unit_ids:
                actions.append(f"Keep fire unit ({unit_ids[0]}) ready for rapid response.")
            fire_risk_level = "high" if is_high else "medium"
            units = 1
            evacuation = False
        else:
            actions.append(f"Maintain a precautionary fire watch at {location}.")
            actions.append("Verify extinguishers and exit routes are clear and serviceable.")
            fire_risk_level = "medium" if is_high else "low"
            units = 1
            evacuation = False

        return {
            "agent_name": "Fire & Safety Agent",
            "fire_risk_level": fire_risk_level,
            "actions": actions,
            "recommended_fire_units": units,
            "evacuation_required": evacuation,
            "matched_resources": discovered_units,
            "notes": f"Fire-safety posture calibrated for {incident_type.upper()} incident at {location}.",
        }


fire_agent = FireAgent()
