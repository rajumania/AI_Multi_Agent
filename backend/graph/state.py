from typing import Annotated, TypedDict, Optional, List, Dict, Any


def merge_audit_trail(existing: List[str], update: List[str]) -> List[str]:
    """Merge branch audit updates without duplicating shared prefixes."""
    merged = list(existing or [])
    for entry in update or []:
        if entry not in merged:
            merged.append(entry)
    return merged


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
    supervisor_analysis: Optional[Dict[str, Any]]

    # Specialized Agent Results
    security_result: Optional[Dict[str, Any]]
    medical_result: Optional[Dict[str, Any]]
    transport_result: Optional[Dict[str, Any]]
    communication_result: Optional[Dict[str, Any]]
    fire_result: Optional[Dict[str, Any]]
    facilities_result: Optional[Dict[str, Any]]

    # MCP Discovered Resources
    mcp_resources: List[Dict[str, Any]]

    # Consolidated Recommendations
    all_recommendations: List[str]
    required_approvals: List[str]
    audit_trail: Annotated[List[str], merge_audit_trail]
    execution_status: str

