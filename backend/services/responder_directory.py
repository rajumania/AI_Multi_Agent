from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any


@dataclass
class ResponderContact:
    responder_id: str
    name: str
    role: str
    phone: str
    email: str
    push_token: Optional[str]
    notification_preferences: List[str]
    authorized_actions: List[str]
    availability: str = "available"
    last_contact: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "responder_id": self.responder_id,
            "name": self.name,
            "role": self.role,
            "phone": self.phone,
            "email": self.email,
            "push_token": self.push_token,
            "notification_preferences": self.notification_preferences,
            "authorized_actions": self.authorized_actions,
            "availability": self.availability,
            "last_contact": self.last_contact
        }


class ResponderDirectory:
    """
    Real Responder Contact Directory.
    Maintains verified contact details and authorization levels for emergency responders.
    """

    def __init__(self):
        self._directory: Dict[str, ResponderContact] = {
            "RESP-001": ResponderContact(
                responder_id="RESP-001",
                name="Commander K. Sharma",
                role="Campus Safety Commander",
                phone="+919876543210",
                email="security.commander@aitam.local",
                push_token="token_responder_001",
                notification_preferences=["SMS", "PUSH", "VOICE", "EMAIL"],
                authorized_actions=["DISPATCH_SECURITY", "CAMPUS_ALERT", "EVACUATION_ORDER"],
                availability="available"
            ),
            "RESP-002": ResponderContact(
                responder_id="RESP-002",
                name="Dr. V. Rao",
                role="Medical Coordinator",
                phone="+919876543211",
                email="medical.head@aitam.local",
                push_token="token_responder_002",
                notification_preferences=["SMS", "PUSH", "EMAIL"],
                authorized_actions=["DISPATCH_AMBULANCE", "TRIAGE_ORDER"],
                availability="available"
            ),
            "RESP-003": ResponderContact(
                responder_id="RESP-003",
                name="Officer P. Verma",
                role="Transport & Fleet Coordinator",
                phone="+919876543212",
                email="transport.officer@aitam.local",
                push_token=None,
                notification_preferences=["SMS", "EMAIL"],
                authorized_actions=["REROUTE_TRAFFIC", "DISPATCH_VEHICLE"],
                availability="available"
            ),
            "RESP-004": ResponderContact(
                responder_id="RESP-004",
                name="Engineer M. Reddy",
                role="Facilities & Safety Officer",
                phone="+919876543213",
                email="facilities.officer@aitam.local",
                push_token=None,
                notification_preferences=["EMAIL", "SMS"],
                authorized_actions=["ISOLATE_UTILITIES", "HAZARD_CONTAINMENT"],
                availability="available"
            )
        }

    def get_responder(self, responder_id: str) -> Optional[ResponderContact]:
        return self._directory.get(responder_id)

    def list_responders(self, role_filter: Optional[str] = None) -> List[ResponderContact]:
        if role_filter:
            return [r for r in self._directory.values() if role_filter.lower() in r.role.lower()]
        return list(self._directory.values())

    def get_phones_for_group(self, group: str) -> List[str]:
        return [r.phone for r in self._directory.values() if r.phone]

    def get_emails_for_group(self, group: str) -> List[str]:
        return [r.email for r in self._directory.values() if r.email]

    def get_push_tokens_for_group(self, group: str) -> List[str]:
        return [r.push_token for r in self._directory.values() if r.push_token]


responder_directory = ResponderDirectory()
