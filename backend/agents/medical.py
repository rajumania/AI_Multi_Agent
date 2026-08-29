from typing import Dict, Any, List, Optional
from backend.services.llm_service import llm_service


MEDICAL_AGENT_SYSTEM_PROMPT = """You are the specialized Medical Response & Triage Agent for AITAM Disaster Response AI.
Your duty is to assess healthcare risks, triage readiness, first-aid deployment, and ambulance dispatch recommendations.

CRITICAL SAFETY RULES:
1. NEVER INVENT OR HALLUCINATE CASUALTIES OR INJURIES.
2. If injured_count is null (unknown), do NOT assume 0 and do NOT invent injured people. Recommend precautionary medical standby.
3. If injured_count > 0, recommend triage and direct ambulance/first-aid dispatch corresponding to confirmed injured persons.

Output JSON format:
{
  "agent_name": "Medical Agent",
  "triage_priority": "routine" | "urgent" | "immediate",
  "actions": [
    "action 1",
    "action 2"
  ],
  "recommended_ambulances": 0 | 1 | 2 | 3,
  "first_aid_units_required": 0 | 1 | 2,
  "medical_center_alert": true | false,
  "casualty_assessment": "status assessment text"
}
"""


class MedicalAgent:
    """
    Specialized Medical Agent:
    - Handles health crises, injuries, heatstroke, cardiac events, trauma.
    - Recommends ambulance dispatch and first-aid triage according to factual injury data.
    """

    def __init__(self):
        self.llm = llm_service

    def evaluate(
        self,
        incident_type: str,
        severity: str,
        location: str,
        description: str,
        injured_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        prompt = (
            f"INCIDENT DETAILS:\n"
            f"Type: {incident_type}\n"
            f"Severity: {severity}\n"
            f"Location: {location}\n"
            f"Confirmed Injured Count: {'UNKNOWN (null - precautionary mode)' if injured_count is None else injured_count}\n"
            f"Description: {description}\n\n"
            f"Provide specific medical response recommendations in structured JSON."
        )

        try:
            if self.llm.is_gemini_available() or self.llm.is_openai_available():
                result = self.llm.generate_json_response(MEDICAL_AGENT_SYSTEM_PROMPT, prompt)
                if "actions" in result and isinstance(result["actions"], list):
                    return result
        except Exception:
            pass

        # Deterministic Safety Fallback & MCP Resource Grounding
        from backend.mcp.server import mcp_server

        # Query real ambulances and first aid units via MCP
        discovered_ambulances = mcp_server.call_tool("find_available_ambulances", {"location": location, "limit": 2})
        discovered_first_aid = mcp_server.call_tool("find_first_aid_units", {"location": location, "limit": 2})

        amb_ids = [a["resource_id"] for a in discovered_ambulances]
        fa_ids = [f["resource_id"] for f in discovered_first_aid]

        actions = []
        is_high = severity in ["high", "critical"]

        if injured_count is not None and injured_count > 0:
            target_amb = min(injured_count, len(amb_ids)) if amb_ids else 1
            if amb_ids:
                actions.append(f"Dispatch Emergency Ambulance ({', '.join(amb_ids[:target_amb])}) directly to {location}.")
            else:
                actions.append(f"Alert municipal ambulance dispatch for {location} (No local units available).")
            
            actions.append(f"Alert Central Medical Center emergency room for {injured_count} incoming patient(s).")
            
            if fa_ids:
                actions.append(f"Deploy First Aid Unit ({fa_ids[0]}) with trauma kits and AED equipment.")
            else:
                actions.append("Deploy on-duty First Aid responder team.")

            priority = "immediate" if (is_high or injured_count >= 2) else "urgent"
            ambulances = target_amb
            first_aid = len(fa_ids)
            alert_center = True
            casualty_assessment = f"Confirmed {injured_count} casualty/casualties requiring immediate medical intervention."
        elif injured_count == 0:
            actions.append("No active casualties reported on scene.")
            if fa_ids:
                actions.append(f"Place First Aid Unit ({fa_ids[0]}) on standard standby for {location}.")
            else:
                actions.append(f"Place nearest first-aid responder on standard standby for {location}.")
            priority = "routine"
            ambulances = 0
            first_aid = 0
            alert_center = False
            casualty_assessment = "Confirmed 0 injuries reported."
        else:
            # UNKNOWN casualties (Precautionary safety posture - strictly zero casualty hallucination)
            if amb_ids:
                actions.append(f"Place Emergency Ambulance ({amb_ids[0]}) on immediate standby near {location}.")
            else:
                actions.append(f"Request municipal standby ambulance near {location}.")

            actions.append("Instruct first security responder to confirm casualty status and relay to medical triage.")
            if is_high or incident_type in ["fire", "accident"]:
                actions.append("Notify Central Medical Center to keep emergency triage bay on yellow standby.")
            priority = "urgent" if is_high else "routine"
            ambulances = 1 if (is_high and amb_ids) else 0
            first_aid = 1 if fa_ids else 0
            alert_center = is_high
            casualty_assessment = "Casualties unconfirmed (strictly preserved as unknown/null). Precautionary medical readiness activated."

        matched = discovered_ambulances + discovered_first_aid

        return {
            "agent_name": "Medical Agent",
            "triage_priority": priority,
            "actions": actions,
            "recommended_ambulances": ambulances,
            "first_aid_units_required": first_aid,
            "medical_center_alert": alert_center,
            "casualty_assessment": casualty_assessment,
            "matched_resources": matched
        }



medical_agent = MedicalAgent()
