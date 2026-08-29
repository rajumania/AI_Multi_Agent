"""Dedicated LangGraph workflow for deterministic risk plus interpretation."""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.agents.risk_prediction import risk_prediction_agent
from backend.services.risk_engine import DeterministicRiskEngine, RiskFeatures


class RiskGraphState(TypedDict, total=False):
    disaster_type: str
    zone_name: str
    features: RiskFeatures
    result: Any
    explanation: str
    contributing_factors: list[str]
    recommendations: list[str]


def _deterministic_score(state: RiskGraphState) -> dict[str, Any]:
    result = DeterministicRiskEngine().score(state["disaster_type"], state["features"])
    return {"result": result}


def _interpret(state: RiskGraphState) -> dict[str, Any]:
    briefing = risk_prediction_agent.interpret(state["result"], state.get("zone_name", "the affected zone"))
    return briefing


def create_risk_graph():
    graph = StateGraph(RiskGraphState)
    graph.add_node("deterministic_risk_engine", _deterministic_score)
    graph.add_node("risk_prediction_agent", _interpret)
    graph.add_edge(START, "deterministic_risk_engine")
    graph.add_edge("deterministic_risk_engine", "risk_prediction_agent")
    graph.add_edge("risk_prediction_agent", END)
    return graph.compile()


risk_workflow = create_risk_graph()


def run_risk_workflow(disaster_type: str, zone_name: str, features: RiskFeatures) -> RiskGraphState:
    return risk_workflow.invoke({"disaster_type": disaster_type, "zone_name": zone_name, "features": features})
