from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class SeverityEvaluationResult:
    level: str  # "critical", "high", "medium", "low"
    score: int  # 0 - 100
    confidence: float  # 0.0 - 1.0
    breakdown: List[Dict[str, Any]]
    explanation: str


class SeverityEngine:
    """
    Deterministic & Auditable Severity Evaluation Engine for Disaster Emergencies.
    Replaces opaque LLM outputs with a rule-based, auditable scoring policy.
    """

    def evaluate(
        self,
        incident_type: str,
        description: str,
        location: str,
        injured_count: Optional[int],
        corroboration_count: int = 1
    ) -> SeverityEvaluationResult:
        score = 0
        breakdown = []
        desc_lower = description.lower()
        loc_lower = location.lower()
        inc_type = incident_type.lower()

        # 1. Base Score by Incident Type (Max 35)
        type_scores = {
            "fire": 35,
            "explosion": 40,
            "chemical": 40,
            "medical": 30,
            "security": 25,
            "accident": 25,
            "facility": 15,
            "weather": 20,
            "unknown": 10,
        }
        base_pts = type_scores.get(inc_type, 15)
        score += base_pts
        breakdown.append({
            "factor": f"Incident Classification ({inc_type.upper()})",
            "points": base_pts,
            "rationale": f"Base threat rating for {inc_type} emergency."
        })

        # 2. Building Occupancy & Location Sensitivity (Max 25)
        is_dense_academic = any(k in loc_lower for k in ["u-block", "cse", "a-block", "h-block", "v-block", "library", "convocation", "sac"])
        is_hostel = any(k in loc_lower for k in ["hostel", "dorm", "mahalakshmi", "vasishta"])
        if is_dense_academic:
            score += 20
            breakdown.append({
                "factor": "High-Density Academic Facility",
                "points": 20,
                "rationale": f"Located at {location}, a high-occupancy community facility."
            })
        elif is_hostel:
            score += 25
            breakdown.append({
                "factor": "Residential Hostel Zone",
                "points": 25,
                "rationale": f"Located at {location}, high-density 24/7 residential zone."
            })
        else:
            score += 10
            breakdown.append({
                "factor": "Open Response Zone",
                "points": 10,
                "rationale": f"Located in general response area ({location})."
            })

        # 3. Casualty & Injury Assessment (Max 25)
        if injured_count is not None and injured_count > 0:
            casualty_pts = min(25, 15 + (injured_count * 5))
            score += casualty_pts
            breakdown.append({
                "factor": f"Confirmed Casualties ({injured_count} injured)",
                "points": casualty_pts,
                "rationale": f"Emergency triage required for {injured_count} confirmed individual(s)."
            })
        elif injured_count is None and any(w in desc_lower for w in ["trapped", "injured", "screaming", "unconscious", "collapse", "blood", "breathing", "respiratory"]):
            score += 15
            breakdown.append({
                "factor": "Unverified Casualty Signals Detected",
                "points": 15,
                "rationale": "Description keywords indicate potential trapped or injured individuals."
            })
        else:
            score += 0
            breakdown.append({
                "factor": "Zero Casualties Confirmed",
                "points": 0,
                "rationale": "No immediate human injury reported."
            })

        # 4. Immediate Escalation / Active Hazard Indicators (Max 15)
        if any(w in desc_lower for w in ["spreading", "dense smoke", "explosion", "active flame", "weapon", "gas leak", "chemical"]):
            score += 15
            breakdown.append({
                "factor": "Active Spreading Hazard",
                "points": 15,
                "rationale": "Signs of rapid situational escalation (flames, smoke, hazardous vapors)."
            })

        # 5. Multi-Source Corroboration Velocity (Max 10)
        if corroboration_count >= 3:
            score += 10
            breakdown.append({
                "factor": f"High Corroboration Velocity ({corroboration_count} reports)",
                "points": 10,
                "rationale": f"{corroboration_count} independent community/staff reports confirm situation."
            })
        elif corroboration_count >= 2:
            score += 5
            breakdown.append({
                "factor": "Multi-Witness Corroboration (2 reports)",
                "points": 5,
                "rationale": "Secondary witness confirmation received."
            })

        # Final Score Clamping & Level Mapping
        final_score = min(100, max(0, score))

        if final_score >= 70:
            level = "critical"
        elif final_score >= 45:
            level = "high"
        elif final_score >= 25:
            level = "medium"
        else:
            level = "low"

        # Calculate confidence based on data completeness
        confidence = 0.85
        if injured_count is not None:
            confidence += 0.05
        if corroboration_count > 1:
            confidence += 0.05
        confidence = min(0.98, confidence)

        explanation = f"Evaluated threat level as {level.upper()} (Score: {final_score}/100, Confidence: {int(confidence*100)}%). " + "; ".join(
            [f"{b['factor']} (+{b['points']} pts)" for b in breakdown if b['points'] > 0]
        )

        return SeverityEvaluationResult(
            level=level,
            score=final_score,
            confidence=confidence,
            breakdown=breakdown,
            explanation=explanation
        )


severity_engine = SeverityEngine()
