"""
CampusFlow AI - Specialized Multi-Agent Intelligence Package
"""
from backend.agents.supervisor import SupervisorAgent, supervisor_agent
from backend.agents.security import SecurityAgent, security_agent
from backend.agents.medical import MedicalAgent, medical_agent
from backend.agents.transport import TransportAgent, transport_agent
from backend.agents.communication import CommunicationAgent, communication_agent
from backend.agents.fire import FireAgent, fire_agent
from backend.agents.facilities import FacilitiesAgent, facilities_agent

__all__ = [
    "SupervisorAgent",
    "supervisor_agent",
    "SecurityAgent",
    "security_agent",
    "MedicalAgent",
    "medical_agent",
    "TransportAgent",
    "transport_agent",
    "CommunicationAgent",
    "communication_agent",
    "FireAgent",
    "fire_agent",
    "FacilitiesAgent",
    "facilities_agent",
]

