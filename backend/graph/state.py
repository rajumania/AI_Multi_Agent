from typing import TypedDict, Optional, List, Dict, Any


class EmergencyGraphState(TypedDict, total=False):
    """
    Typed dictionary holding the state throughout the LangGraph multi-agent orchestration lifecycle.
    """
    incident_id: str
    description: str
    location: str
    incident_type: str
    severity: str
    injured_count: Optional[int]  # Strictly preserved as None (null) if unknown
    evidence_source: Optional[str]
    reported_by: Optional[str]
    
    # Supervisor Classification outputs
    summary: str
    confidence: float
    delegated_agents: List[str]
    key_observations: List[str]

    # Specialized Agent Results
    security_result: Optional[Dict[str, Any]]
    medical_result: Optional[Dict[str, Any]]
    transport_result: Optional[Dict[str, Any]]
    communication_result: Optional[Dict[str, Any]]

    # MCP Discovered Resources
    mcp_resources: List[Dict[str, Any]]

    # Consolidated Recommendations
    all_recommendations: List[str]
    required_approvals: List[str]
    audit_trail: List[str]
    execution_status: str

