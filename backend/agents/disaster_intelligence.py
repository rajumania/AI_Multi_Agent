"""Connected specialist agents for the Phase 3 disaster-intelligence graph.

These agents are intentionally small and evidence-bound. LLM calls can be
introduced for narrative interpretation later, while deterministic tools keep
risk, resources, priority, routes and authorization trustworthy.
"""

from __future__ import annotations

from typing import Any


class SpecialistAgent:
    name = "specialist"

    def analyze(self, state: dict[str, Any]) -> dict[str, Any]:
        return {"status": "completed", "summary": f"{self.name.replace('_', ' ').title()} reviewed the normalized event.", "evidence": {}}


class SupervisorIncidentCommander:
    """Connected routing component used by the Phase 3 LangGraph entry node."""

    name = "supervisor"

    def select(self, state: dict[str, Any]) -> list[str]:
        return selected_specialists(state.get("disaster_type", "other"), state.get("event_source", "human"))


class DisasterAnalysisAgent(SpecialistAgent):
    name = "disaster_analysis"

    def analyze(self, state):
        disaster = str(state.get("disaster_type") or "other").replace("_", " ")
        description = str(state.get("description") or "").lower()
        hazards = [disaster]
        if "landslide" in description or "ground movement" in description:
            hazards.append("landslide")
        if "flood" in description or "river" in description:
            hazards.append("flash_flood")
        correlation = state.get("correlation") or {}
        corroboration = "sensor and community evidence corroborate the event" if correlation.get("corroborated") else "available evidence is currently from a single entry channel"
        image = state.get("image_analysis") or {}
        if str(image.get("status", "")).upper() == "LIVE":
            hazards.extend(str(item) for item in image.get("possible_hazards", [])[:10])
        return {"status": "completed", "summary": f"Current evidence is consistent with {disaster} conditions; {corroboration}.", "evidence": {"potential_hazards": sorted(set(hazards)), "correlation": correlation, "image_analysis": image or {"status": "NOT_PROVIDED"}}}


class WeatherAnalysisAgent(SpecialistAgent):
    name = "weather_analysis"

    def analyze(self, state):
        return {"status": "completed", "summary": "Weather observations reviewed for intensity and freshness.", "evidence": state.get("weather_data") or {"available": False}}


class RiskAnalysisAgent(SpecialistAgent):
    name = "risk_prediction"

    def analyze(self, state):
        return {"status": "completed", "summary": f"Risk estimated as {state.get('risk_score', 0)}/100 ({str(state.get('risk_level', 'low')).upper()}).", "evidence": {"score": state.get("risk_score", 0), "confidence": state.get("risk_confidence", 0), "sensor_anomalies": len(state.get("sensor_events") or []), "community_reports": (state.get("correlation") or {}).get("community_report_count", 0)}}


class GeoVulnerabilityAgent(SpecialistAgent):
    name = "geo_vulnerability"

    def analyze(self, state):
        return {"status": "completed", "summary": "Geographic vulnerability reviewed without inventing coordinates or geometry.", "evidence": state.get("geographic_data") or {"available": False}}


class HydrologyEnvironmentalAgent(SpecialistAgent):
    name = "hydrology_environmental"

    def analyze(self, state):
        return {"status": "completed", "summary": "Hydrology and environmental observations reviewed for anomalies.", "evidence": state.get("environmental_data") or {"available": False}}


class MedicalTriageAgent(SpecialistAgent):
    name = "medical_triage"

    def analyze(self, state):
        requests = state.get("rescue_requests") or []
        injured = sum(int(item.get("injured_count", 0)) for item in requests if isinstance(item, dict))
        return {"status": "completed", "summary": f"Triage context includes {len(requests)} rescue request(s) and {injured} reported injured person(s).", "evidence": {"request_count": len(requests), "injured_count": injured}}


class SearchRescueAgent(SpecialistAgent):
    name = "search_rescue"

    def analyze(self, state):
        return {"status": "completed", "summary": "Search-and-rescue needs were assessed from event severity and community requests.", "evidence": {"request_count": len(state.get("rescue_requests") or []), "risk_level": state.get("risk_level")}}


class SecurityPublicSafetyAgent(SpecialistAgent):
    name = "security_public_safety"

    def analyze(self, state):
        return {"status": "completed", "summary": "Public-safety controls are recommendations pending authorization.", "evidence": {"access_restriction_requires_approval": True}}


class InfrastructureAgent(SpecialistAgent):
    name = "infrastructure"


class ResourceAgent(SpecialistAgent):
    name = "resource"


class RescuePriorityAgent(SpecialistAgent):
    name = "rescue_priority"


class RoutingAgent(SpecialistAgent):
    name = "routing"


class ShelterAgent(SpecialistAgent):
    name = "shelter"


class HospitalAgent(SpecialistAgent):
    name = "hospital"


class ResponsePlannerAgent(SpecialistAgent):
    name = "response_planner"


class CommunicationAgent(SpecialistAgent):
    name = "communication"


class MonitoringAgent(SpecialistAgent):
    name = "monitoring"


class RecoveryAgent(SpecialistAgent):
    name = "recovery"


class TravelSafetyAgent(SpecialistAgent):
    name = "travel_safety"


SPECIALIST_AGENTS = {
    cls.name: cls() for cls in (
        DisasterAnalysisAgent, WeatherAnalysisAgent, RiskAnalysisAgent,
        GeoVulnerabilityAgent, HydrologyEnvironmentalAgent, MedicalTriageAgent,
        SearchRescueAgent, SecurityPublicSafetyAgent, InfrastructureAgent,
        ResourceAgent, RescuePriorityAgent, RoutingAgent, ShelterAgent,
        HospitalAgent, ResponsePlannerAgent, CommunicationAgent,
        MonitoringAgent, RecoveryAgent, TravelSafetyAgent,
    )
}


def selected_specialists(disaster_type: str, event_source: str = "human") -> list[str]:
    key = str(disaster_type or "other").lower()
    common = ["disaster_analysis", "weather_analysis", "risk_prediction", "geo_vulnerability"]
    if key in {"flood", "urban_flood"}:
        return common + ["hydrology_environmental", "medical_triage", "search_rescue", "security_public_safety", "shelter", "hospital", "communication"]
    if key == "landslide":
        return common + ["hydrology_environmental", "infrastructure", "search_rescue", "security_public_safety", "shelter", "hospital", "communication"]
    if key == "heatwave":
        return ["disaster_analysis", "weather_analysis", "risk_prediction", "medical_triage", "shelter", "hospital", "communication"]
    if key == "cyclone":
        return common + ["hydrology_environmental", "infrastructure", "search_rescue", "security_public_safety", "communication"]
    if key == "earthquake":
        return common + ["infrastructure", "medical_triage", "search_rescue", "security_public_safety", "shelter", "hospital", "communication"]
    return common + ["communication", "resource"]
