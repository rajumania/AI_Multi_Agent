from typing import Dict, Any, List, Optional
from backend.services.llm_service import llm_service


SECURITY_AGENT_SYSTEM_PROMPT = """You are the specialized Security & Perimeter Operations Agent for AITAM Disaster Response AI.
Your duty is to assess physical security risks, hazardous-material perimeter control, crowd safety, evacuation routes, and security unit dispatch recommendations.

CRITICAL SAFETY RULES:
1. NEVER INVENT OR HALLUCINATE FACTS. State only security actions warranted by the specific incident.
2. RECOMMEND CONCRETE, AUDITABLE ACTIONS.
3. CLEARLY DISTINGUISH RECOMMENDATIONS FROM EXECUTED ACTIONS.

Output JSON format:
{
  "agent_name": "Security Agent",
  "threat_level": "low" | "medium" | "high" | "critical",
  "actions": [
    "action 1",
    "action 2"
  ],
  "recommended_security_units": 1 | 2 | 3,
  "perimeter_lockdown_required": true | false,
  "notes": "key security considerations"
}
"""


class SecurityAgent:
    """
    Specialized Security Agent:
    - Assesses security threats, intruders, unauthorized access, and crowd risks.
    - Recommends perimeter security, access restrictions, and guard dispatch.
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
            f"Provide specific security recommendations in structured JSON."
        )

        try:
            if self.llm.is_gemini_available() or self.llm.is_openai_available():
                result = self.llm.generate_json_response(SECURITY_AGENT_SYSTEM_PROMPT, prompt)
                if "actions" in result and isinstance(result["actions"], list):
                    return result
        except Exception:
            pass

        # Deterministic Safety Fallback & MCP Resource Grounding
        from backend.mcp.server import mcp_server
        
        # Query real security units via MCP
        discovered_units = mcp_server.call_tool("find_security_units", {"location": location, "limit": 3})
        unit_ids = [u["resource_id"] for u in discovered_units]

        actions = []
        is_high = severity in ["high", "critical"]

        if incident_type in ("fire", "chemical"):
            actions.append(f"Establish 100m safety perimeter around {location}.")
            if unit_ids:
                actions.append(f"Deploy Security Unit ({unit_ids[0]}) to clear emergency vehicle access lanes.")
            else:
                actions.append("Clear emergency vehicle access lanes for incoming fire/first-aid units.")
            actions.append("Direct building occupants to the designated safe area and keep the emergency access lane clear.")
            if incident_type == "chemical":
                actions.append("Establish a perimeter and restrict entry until the chemical hazard is assessed by the safety team.")
            threat_level = "high" if is_high else "medium"
            units = 2 if is_high else 1
            lockdown = False
        elif incident_type == "security":
            if unit_ids:
                actions.append(f"Dispatch public-safety patrol ({', '.join(unit_ids[:2])}) immediately to {location}.")
            else:
                actions.append(f"Dispatch public-safety patrol immediately to {location}.")
            actions.append("Monitor building CCTV feeds and isolate access points.")
            if is_high:
                actions.append("Initiate temporary controlled access lockdown for adjacent zones.")
            threat_level = "critical" if severity == "critical" else "high"
            units = 3 if is_high else 2
            lockdown = is_high
        elif incident_type == "crowd":
            actions.append(f"Deploy crowd management stewards ({', '.join(unit_ids[:2]) if unit_ids else 'Station Patrol'}) to {location}.")
            actions.append("Open secondary exit gates to relieve egress pressure.")
            threat_level = "high" if is_high else "medium"
            units = 3 if is_high else 2
            lockdown = False
        else:
            actions.append(f"Position safety steward at {location} for scene assessment.")
            actions.append("Prevent unauthorized bystander entry.")
            threat_level = "medium" if is_high else "low"
            units = 1
            lockdown = False

        return {
            "agent_name": "Security Agent",
            "threat_level": threat_level,
            "actions": actions,
            "recommended_security_units": units,
            "perimeter_lockdown_required": lockdown,
            "matched_resources": discovered_units,
            "notes": f"Security posture calibrated for {incident_type.upper()} incident at {location}."
        }



security_agent = SecurityAgent()
