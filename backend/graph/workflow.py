from langgraph.graph import StateGraph, START, END
from backend.graph.state import EmergencyGraphState
from backend.graph.nodes import (
    supervisor_node,
    security_node,
    medical_node,
    transport_node,
    communication_node,
    synthesizer_node,
)


def create_emergency_graph():
    """
    Constructs the LangGraph orchestration graph for CAMPUSFLOW AI.
    
    Graph Topology:
    START
      ↓
    Supervisor (Classifies, summarizes, determines delegated agents)
      ↓
    Security Agent ──┐
    Medical Agent   ──┼──> Synthesizer (Consolidates multi-agent plan & approvals) ──> END
    Transport Agent ─┤
    Communication ───┘
    """
    workflow = StateGraph(EmergencyGraphState)

    # 1. Register Graph Nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("security", security_node)
    workflow.add_node("medical", medical_node)
    workflow.add_node("transport", transport_node)
    workflow.add_node("communication", communication_node)
    workflow.add_node("synthesizer", synthesizer_node)

    # 2. Define Flow Edges
    workflow.add_edge(START, "supervisor")
    
    # Sequential orchestration pipeline across specialized agents
    workflow.add_edge("supervisor", "security")
    workflow.add_edge("security", "medical")
    workflow.add_edge("medical", "transport")
    workflow.add_edge("transport", "communication")
    workflow.add_edge("communication", "synthesizer")
    workflow.add_edge("synthesizer", END)

    return workflow.compile()


# Compile reusable singleton workflow instance
emergency_workflow = create_emergency_graph()


def run_emergency_workflow(initial_state: EmergencyGraphState) -> EmergencyGraphState:
    """
    Helper function to invoke the compiled LangGraph workflow synchronously.
    """
    if "audit_trail" not in initial_state:
        initial_state["audit_trail"] = []
    
    return emergency_workflow.invoke(initial_state)
