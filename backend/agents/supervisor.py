from typing import Optional, Dict, Any
from backend.services.llm_service import llm_service
from backend.models.incident import (
    SupervisorAnalysisResult,
    IncidentType,
    SeverityLevel,
)


SUPERVISOR_SYSTEM_PROMPT = """You are the Lead Emergency Intake & Classification Supervisor AI for CAMPUSFLOW AI.
Your duty is to rapidly analyze campus emergency reports, classify the incident, assess severity, extract location, and summarize the situation with extreme precision.

CRITICAL SAFETY RULES (VIOLATION IS STRICTLY PROHIBITED):
1. NEVER INVENT OR FABRICATE FACTS. Do NOT hallucinate injured people, nonexistent locations, or unconfirmed hazards.
2. PRESERVE UNKNOWN INFORMATION:
   - If the report does NOT explicitly confirm the number of injured people or explicitly state "0 injured" / "no injuries", set "injured_count" to null.
   - NEVER convert unknown injuries to 0. (Wrong: {"injured_count": 0}, Correct: {"injured_count": null}).
   - Only set "injured_count": 0 if the report explicitly states that nobody was injured.
3. ADHERE TO VALID ENUM VALUES:
   - incident_type: "fire", "medical", "security", "accident", "weather", "crowd", "facility", "other", "unknown"
   - severity: "low", "medium", "high", "critical", "unknown"
4. RECOMMENDED AGENTS:
   - "security": for intruders, crowd events, fires, theft, hazardous perimeter control
   - "medical": for injuries, health emergencies, medical triage, ambulance coordination
   - "transport": for evacuation, traffic rerouting, vehicle accidents, campus transport dispatch
   - "communication": for emergency broadcasts, student/staff alerts, command briefings

Output MUST be a single valid JSON object with the following schema:
{
  "incident_type": "fire" | "medical" | "security" | "accident" | "weather" | "crowd" | "facility" | "other" | "unknown",
  "severity": "low" | "medium" | "high" | "critical" | "unknown",
  "location": "extracted campus location or building name",
  "injured_count": <integer or null>,
  "summary": "concise, factual summary of the incident and injury confirmation status",
  "confidence": <float between 0.0 and 1.0>,
  "recommended_agents": ["security", "medical", "transport", "communication"],
  "key_observations": [
    "string observation 1",
    "string observation 2"
  ]
}
"""


class SupervisorAgent:
    """
    Supervisor Agent responsible for:
    - Ingesting incident descriptions
    - Classifying incident type and assessing severity
    - Extracting location and preserving unknown injury information
    - Generating safety-grounded summaries and confidence metrics
    - Recommending specialized agents for downstream orchestration
    """

    def __init__(self):
        self.llm = llm_service

    def analyze_incident(
        self,
        description: str,
        reported_location: Optional[str] = None,
        reported_by: Optional[str] = None,
    ) -> SupervisorAnalysisResult:
        """
        Analyze an incident description using LLM (Gemini / OpenAI) or deterministic fallback.
        """
        user_prompt = f"INCIDENT REPORT:\nDescription: {description.strip()}\n"
        if reported_location:
            user_prompt += f"Reported Location: {reported_location.strip()}\n"
        if reported_by:
            user_prompt += f"Reported By: {reported_by.strip()}\n"

        user_prompt += "\nPlease analyze this incident according to your instructions and output structured JSON."

        raw_result = self.llm.generate_json_response(
            system_instruction=SUPERVISOR_SYSTEM_PROMPT,
            user_prompt=user_prompt
        )

        return self._sanitize_and_validate(raw_result, description, reported_location)

    def _sanitize_and_validate(
        self,
        data: Dict[str, Any],
        raw_description: str,
        reported_location: Optional[str] = None
    ) -> SupervisorAnalysisResult:
        """
        Validates output and strictly enforces zero-fabrication safety rules on parsed output.
        """
        # 1. Enforce Incident Type
        raw_type = str(data.get("incident_type", "unknown")).lower().strip()
        try:
            incident_type = IncidentType(raw_type)
        except ValueError:
            incident_type = IncidentType.UNKNOWN

        # 2. Enforce Severity
        raw_sev = str(data.get("severity", "medium")).lower().strip()
        try:
            severity = SeverityLevel(raw_sev)
        except ValueError:
            severity = SeverityLevel.MEDIUM

        # 3. Location Extraction
        location = data.get("location") or reported_location or "Campus Premises"
        if not location or str(location).strip().lower() in ("unknown", "null", "none"):
            location = reported_location or "Campus Grounds"

        # 4. Strict Safety on Injured Count (Preserve null if unknown!)
        raw_injured = data.get("injured_count")
        if raw_injured is None or str(raw_injured).lower().strip() in ("unknown", "null", "none"):
            injured_count = None
        else:
            try:
                injured_count = int(raw_injured)
                if injured_count < 0:
                    injured_count = None
            except (ValueError, TypeError):
                injured_count = None

        # Double check raw description safety:
        raw_desc_lower = raw_description.lower()
        has_explicit_zero = any(phrase in raw_desc_lower for phrase in [
            "no injuries", "nobody is injured", "nobody injured", "no one hurt", "no one injured", "0 injured", "zero casualties"
        ])
        if injured_count == 0 and not has_explicit_zero:
            # If the LLM returned 0 without explicit confirmation in the text, revert strictly to None
            injured_count = None

        # 5. Summary
        summary = data.get("summary")
        if not summary:
            status_text = (
                "Casualty status unconfirmed."
                if injured_count is None
                else f"Confirmed {injured_count} injured."
                if injured_count > 0
                else "Confirmed no injuries."
            )
            summary = f"{incident_type.value.capitalize()} emergency reported at {location}. {status_text}"

        # 6. Confidence
        try:
            confidence = float(data.get("confidence", 0.92))
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.88

        # 7. Recommended Agents
        agents = data.get("recommended_agents", [])
        if not isinstance(agents, list):
            agents = ["security", "communication"]
        else:
            valid_agents = {"security", "medical", "transport", "communication"}
            agents = [str(a).lower() for a in agents if str(a).lower() in valid_agents]
            if not agents:
                agents = ["security", "communication"]

        # 8. Key Observations
        observations = data.get("key_observations", [])
        if not isinstance(observations, list) or not observations:
            observations = [
                f"Classified primary category as {incident_type.value.upper()}",
                f"Assessed urgency level as {severity.value.upper()}",
                f"Casualty status: {'UNKNOWN (Preserved as null)' if injured_count is None else str(injured_count)}"
            ]

        return SupervisorAnalysisResult(
            incident_type=incident_type,
            severity=severity,
            location=str(location).strip(),
            injured_count=injured_count,
            summary=str(summary).strip(),
            confidence=round(confidence, 2),
            recommended_agents=agents,
            key_observations=observations
        )


supervisor_agent = SupervisorAgent()
