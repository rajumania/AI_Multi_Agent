import json
import re
import os
from typing import Optional, Dict, Any
from backend.config import settings

# Attempt import of Gemini and OpenAI SDKs
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class LLMService:
    def __init__(self):
        self.provider = (settings.LLM_PROVIDER or "gemini").lower()
        self.gemini_api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
        self.openai_api_key = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")

        if self.gemini_api_key and HAS_GEMINI:
            genai.configure(api_key=self.gemini_api_key)

    def is_gemini_available(self) -> bool:
        return bool(self.gemini_api_key and HAS_GEMINI)

    def is_openai_available(self) -> bool:
        return bool(self.openai_api_key and HAS_OPENAI)

    def generate_json_response(self, system_instruction: str, user_prompt: str) -> Dict[str, Any]:
        """
        Executes an LLM call with structured JSON enforcement.
        Falls back cleanly to heuristic extraction if external APIs are not configured.
        """
        # 1. Try Google Gemini if configured
        if self.provider == "gemini" and self.is_gemini_available():
            try:
                model = genai.GenerativeModel(
                    model_name="gemini-2.5-flash" if "2.5" in str(genai) else "gemini-1.5-flash",
                    system_instruction=system_instruction,
                    generation_config={"response_mime_type": "application/json"}
                )
                response = model.generate_content(user_prompt)
                raw_text = response.text
                return self._parse_json(raw_text)
            except Exception as e:
                print(f"[LLMService] Gemini call failed: {e}. Falling back to heuristic model.")

        # 2. Try OpenAI if configured
        if (self.provider == "openai" or self.is_openai_available()) and self.openai_api_key:
            try:
                client = openai.OpenAI(api_key=self.openai_api_key)
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1
                )
                raw_text = response.choices[0].message.content or "{}"
                return self._parse_json(raw_text)
            except Exception as e:
                print(f"[LLMService] OpenAI call failed: {e}. Falling back to heuristic model.")

        # 3. Deterministic Safety-Aligned Heuristic Fallback
        return self._heuristic_fallback(user_prompt)

    def _parse_json(self, raw_text: str) -> Dict[str, Any]:
        cleaned = raw_text.strip()
        # Remove markdown fences if present
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        return json.loads(cleaned)

    def _heuristic_fallback(self, user_prompt: str) -> Dict[str, Any]:
        """
        Deterministic, zero-hallucination heuristic analysis conforming strictly to safety rules.
        """
        text = user_prompt.lower()

        # 1. Incident Type
        if any(w in text for w in ["fire", "smoke", "flame", "burning", "blaze"]):
            incident_type = "fire"
        elif any(w in text for w in ["unconscious", "heart", "bleed", "burn", "choking", "injured", "medical", "collapse", "paramedic"]):
            incident_type = "medical"
        elif any(w in text for w in ["intruder", "theft", "fight", "weapon", "suspicious", "threat", "robbery", "break-in", "security"]):
            incident_type = "security"
        elif any(w in text for w in ["crash", "collision", "vehicle", "car", "bus", "pedestrian hit", "traffic"]):
            incident_type = "accident"
        elif any(w in text for w in ["leak", "pipe", "power outage", "elevator", "blackout", "flooding", "structural"]):
            incident_type = "facility"
        elif any(w in text for w in ["crowd", "surge", "stampede", "riot", "gathering"]):
            incident_type = "crowd"
        elif any(w in text for w in ["storm", "cyclone", "heavy rain", "thunderstorm", "weather"]):
            incident_type = "weather"
        else:
            incident_type = "unknown"

        # 2. Location Extraction (Specific campus buildings prioritized over generic terms)
        location = "Campus Premises"
        if "cse" in text:
            location = "CSE Block"
        elif "medical center" in text or "health center" in text:
            location = "Central Medical Center"
        elif "auditorium" in text:
            location = "North Auditorium"
        elif "sports" in text or "arena" in text or "stadium" in text:
            location = "Sports Complex Arena"
        elif "science" in text or "lab" in text or "chemistry" in text:
            location = "Science & Tech Hub"
        elif "hostel" in text or "dorm" in text or "residence" in text:
            location = "Student Residential Quarters"
        elif "data center" in text or "server room" in text:
            location = "Data Center"
        elif "gate" in text or "entrance" in text:
            location = "Main Entrance Gate"

        # 3. Casualties / Injured Count (Strict Safety: Never force 0 if unknown!)
        injured_count = None
        if any(w in text for w in ["no injuries", "nobody is injured", "nobody injured", "no one hurt", "no one injured", "0 injured", "zero casualties"]):
            injured_count = 0
        else:
            # Check for numbers associated with casualties / injured
            match = re.search(r'(\d+)\s*(?:people|persons|students|staff|individuals|workers)?\s*(?:injured|hurt|casualties|unconscious|collapsed|victims|patients|trapped)', text)
            if match:
                injured_count = int(match.group(1))
            else:
                # Strictly unknown
                injured_count = None

        # 4. Severity Assessment
        if any(w in text for w in ["explosion", "active shooter", "massive", "unconscious", "trapped", "critical", "major fire"]):
            severity = "critical"
        elif any(w in text for w in ["fire", "smoke", "flames", "high", "bleed", "structural failure", "violent", "urgent"]):
            severity = "high"
        elif any(w in text for w in ["leak", "power", "minor", "spill", "medium"]):
            severity = "medium"
        else:
            severity = "low" if incident_type in ["facility", "other"] else "medium"

        # 5. Summary
        injured_str = "Injuries have not been confirmed." if injured_count is None else (
            "Confirmed no injuries reported." if injured_count == 0 else f"{injured_count} casualties reported."
        )
        summary = f"{incident_type.capitalize()} incident reported at {location}. {injured_str}"

        # 6. Recommended Specialized Agents
        agents = []
        if incident_type in ["fire", "security", "crowd"]:
            agents.append("security")
        if incident_type in ["medical", "fire", "accident"] or (injured_count and injured_count > 0):
            agents.append("medical")
        if incident_type in ["accident", "fire", "crowd"] or severity in ["high", "critical"]:
            agents.append("transport")
        agents.append("communication")

        return {
            "incident_type": incident_type,
            "severity": severity,
            "location": location,
            "injured_count": injured_count,
            "summary": summary,
            "confidence": 0.94 if incident_type != "unknown" else 0.50,
            "recommended_agents": agents,
            "key_observations": [
                f"Classified primary category as {incident_type.upper()}",
                f"Assessed urgency level as {severity.upper()}",
                f"Preserved casualty status: {'UNKNOWN (null)' if injured_count is None else str(injured_count)}"
            ]
        }


llm_service = LLMService()
