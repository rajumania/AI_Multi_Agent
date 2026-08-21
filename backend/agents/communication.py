from typing import Dict, Any, List, Optional
from backend.services.llm_service import llm_service


COMMUNICATION_AGENT_SYSTEM_PROMPT = """You are the specialized Emergency Communications & Public Information Agent for CAMPUSFLOW AI.
Your duty is to draft verified campus alerts, coordinator briefings, and public safety announcements.

CRITICAL SAFETY RULES:
1. NEVER BROADCAST UNVERIFIED FACTS OR CASUALTY ESTIMATES.
2. IF INJURIES ARE UNCONFIRMED, STATE ONLY THAT EMERGENCY TEAMS ARE ON SCENE ASSESSING THE SITUATION.
3. CLEARLY SPECIFY NOTIFICATION CHANNELS (e.g., SMS, App Push, Campus Coordinator Hotline).

Output JSON format:
{
  "agent_name": "Communication Agent",
  "broadcast_priority": "standard" | "high" | "urgent",
  "alert_headline": "short headline",
  "broadcast_channels": ["sms", "push", "email", "coordinator_radio"],
  "recommended_message": "composed message text",
  "actions": [
    "action 1",
    "action 2"
  ]
}
"""


class CommunicationAgent:
    """
    Specialized Communication Agent:
    - Composes calibrated emergency broadcasts and alerts.
    - Recommends communication channels (SMS, Push, Staff Hotline, Campus Web).
    - Preserves factual boundaries without alarming or fabricating details.
    """

    def __init__(self):
        self.llm = llm_service

    def evaluate(
        self,
        incident_type: str,
        severity: str,
        location: str,
        description: str,
        summary: str,
        injured_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        prompt = (
            f"INCIDENT DETAILS:\n"
            f"Type: {incident_type}\n"
            f"Severity: {severity}\n"
            f"Location: {location}\n"
            f"Summary: {summary}\n"
            f"Casualty Status: {'UNKNOWN (Do not guess)' if injured_count is None else str(injured_count)}\n\n"
            f"Provide calibrated emergency broadcast recommendations in structured JSON."
        )

        try:
            if self.llm.is_gemini_available() or self.llm.is_openai_available():
                result = self.llm.generate_json_response(COMMUNICATION_AGENT_SYSTEM_PROMPT, prompt)
                if "recommended_message" in result:
                    return result
        except Exception:
            pass

        # Deterministic Safety Fallback
        is_high = severity in ["high", "critical"]
        channels = ["push", "coordinator_radio"]
        if is_high:
            channels.extend(["sms", "digital_signage"])

        headline = f"CAMPUS ALERT: {incident_type.upper()} incident reported at {location}"

        if is_high:
            msg = (
                f"Emergency teams are responding to an incident near {location}. "
                f"Please avoid the area and follow directions from campus security stewards."
            )
            priority = "urgent" if severity == "critical" else "high"
        else:
            msg = f"Operations notice: Facilities response underway at {location}. Normal operations continue in surrounding zones."
            priority = "standard"

        actions = [
            f"Prepare verified situation bulletin for Campus Emergency Operations Center.",
            f"Stage alert broadcast across: {', '.join(channels)}.",
            f"Send real-time status update to campus security dispatcher."
        ]

        return {
            "agent_name": "Communication Agent",
            "broadcast_priority": priority,
            "alert_headline": headline,
            "broadcast_channels": channels,
            "recommended_message": msg,
            "actions": actions
        }


communication_agent = CommunicationAgent()
