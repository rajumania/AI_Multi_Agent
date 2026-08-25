from langgraph.graph import StateGraph, START, END
from backend.graph.state import EmergencyGraphState
from backend.graph.instrumentation import instrument_node
from backend.graph.nodes import (
    supervisor_node,
    security_node,
    medical_node,
    transport_node,
    communication_node,
    fire_node,
    facilities_node,
    synthesizer_node,
)
from backend.services.performance import perf_stage


def create_emergency_graph():
    """
    Constructs the LangGraph orchestration graph for CAMPUSFLOW AI.

    Graph Topology:
    START
      ↓
    Supervisor (Classifies, summarizes, determines delegated agents)
      ↓
    Security → Medical → Transport → Communication → Fire → Facilities
      ↓
    Synthesizer (Consolidates multi-agent plan & approvals)
      ↓
    END
    """
    workflow = StateGraph(EmergencyGraphState)

    # 1. Register Graph Nodes
    # Each node is wrapped with instrument_node so its REAL execution emits
    # agent_started / agent_completed / agent_failed events over the existing
    # event engine. The wrapper returns the node result unchanged, so state
    # merging and behavior are identical to before.
    workflow.add_node("supervisor", instrument_node(supervisor_node, "supervisor"))
    workflow.add_node("security", instrument_node(security_node, "security"))
    workflow.add_node("medical", instrument_node(medical_node, "medical"))
    workflow.add_node("transport", instrument_node(transport_node, "transport"))
    workflow.add_node("communication", instrument_node(communication_node, "communication"))
    workflow.add_node("fire", instrument_node(fire_node, "fire"))
    workflow.add_node("facilities", instrument_node(facilities_node, "facilities"))
    workflow.add_node("synthesizer", instrument_node(synthesizer_node, "synthesizer"))

    # 2. Define Flow Edges. The supervisor's real recommendations determine
    # which specialized agents run. Selected branches still fan out in
    # parallel and fan back into the existing synthesizer; this graph never
    # dispatches teams or notifies departments.
    workflow.add_edge(START, "supervisor")

    specialized_agents = ("security", "medical", "transport", "communication", "fire", "facilities")
    workflow.add_conditional_edges(
        "supervisor",
        lambda state: [
            agent for agent in specialized_agents
            if agent in set(state.get("delegated_agents", []))
        ] or ["communication"],
        path_map=list(specialized_agents),
    )
    for agent in specialized_agents:
        workflow.add_edge(agent, "synthesizer")
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
    
    incident_id = initial_state.get("incident_id")
    with perf_stage("total_workflow", incident_id=incident_id):
        return emergency_workflow.invoke(initial_state)
