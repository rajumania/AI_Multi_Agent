from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any, Dict


class ProviderStatus(str, Enum):
    CONFIGURED = "configured"
    NOT_CONFIGURED = "not_configured"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    ACCEPTED = "accepted"
    RINGING = "ringing"
    ANSWERED = "answered"
    NO_ANSWER = "no_answer"
    FAILED = "failed"
    DELIVERY_UNKNOWN = "delivery_unknown"
    DISPATCH_NOT_CONNECTED = "dispatch_not_connected"
    NO_REGISTERED_DEVICES = "no_registered_devices"


@dataclass
class AdapterResult:
    success: bool
    status: ProviderStatus
    provider: str
    channel: str
    message_id: Optional[str] = None
    recipient_count: int = 0
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status.value,
            "provider": self.provider,
            "channel": self.channel,
            "message_id": self.message_id,
            "recipient_count": self.recipient_count,
            "details": self.details,
            "error": self.error,
            "timestamp": self.timestamp.isoformat()
        }
