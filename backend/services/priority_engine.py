"""Transparent rescue-request priority scoring."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)


def calculate_priority(request: Any, risk_score: float = 0.0, inaccessible: bool = False) -> dict[str, Any]:
    """Calculate a bounded priority score; no LLM participates in the score."""
    people = min(100.0, float(getattr(request, "people_count", 0)) * 4)
    injured = min(100.0, float(getattr(request, "injured_count", 0)) * 18)
    vulnerable = min(100.0, float(getattr(request, "children_count", 0)) * 10 + float(getattr(request, "elderly_count", 0)) * 10)
    medical = 100.0 if bool(getattr(request, "medical_emergency", False)) else 0.0
    hazard = {"critical": 100.0, "high": 75.0, "medium": 45.0, "low": 20.0}.get(str(getattr(request, "hazard_level", "unknown")).lower(), risk_score)
    created_at = getattr(request, "created_at", None) or datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    waiting = min(100.0, max(0.0, (datetime.now(timezone.utc) - created_at).total_seconds() / 360))
    access = 85.0 if inaccessible else 15.0
    score = _clamp(people * .15 + injured * .25 + vulnerable * .15 + medical * .20 + max(hazard, risk_score) * .15 + waiting * .05 + access * .05)
    level = "CRITICAL" if score >= 80 else "HIGH" if score >= 60 else "MEDIUM" if score >= 35 else "LOW"
    reasons = []
    if injured > 0: reasons.append("injured people reported")
    if medical: reasons.append("medical emergency")
    if vulnerable > 0: reasons.append("children or elderly people exposed")
    if max(hazard, risk_score) >= 75: reasons.append("severe hazard conditions")
    if inaccessible: reasons.append("location may be isolated or difficult to access")
    return {"request_id": getattr(request, "request_id", None), "priority_score": score, "priority_level": level, "reasoning": reasons or ["population exposure and current conditions"], "calculated_at": datetime.now(timezone.utc).isoformat()}
