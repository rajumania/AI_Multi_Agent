"""Structured risk interpretation agent used by the Phase 2 risk graph."""

from __future__ import annotations

from typing import Any


class RiskPredictionAgent:
    """Convert deterministic risk evidence into an operational briefing.

    The agent receives the score and evidence produced by the deterministic
    engine. It does not calculate or override numerical risk.
    """

    name = "risk_prediction"

    def interpret(self, result: Any, zone_name: str) -> dict[str, Any]:
        level = result.level.value.upper()
        factors = list(result.contributing_factors)
        factor_text = "; ".join(factors[:3]) if factors else "limited available evidence"
        explanation = (
            f"{level} risk briefing for {zone_name}: "
            f"risk score {result.score:g}/100 with {result.confidence:g}% confidence. "
            f"Primary evidence: {factor_text}."
        )
        return {
            "explanation": explanation,
            "contributing_factors": factors,
            "recommendations": list(result.recommendations),
        }


risk_prediction_agent = RiskPredictionAgent()
