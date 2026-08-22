import uuid
import re
from typing import List, Dict, Any, Optional
from backend.config import settings
from backend.services.adapters.base_adapter import ProviderStatus, AdapterResult


class SMSAdapter:
    """
    Real SMS Service Adapter.
    Communicates with configured SMS provider (Twilio API Key SID + Secret OR Account SID + Auth Token).
    If credentials are missing or placeholders, reports NOT CONFIGURED explicitly without faking success.
    """

    PLACEHOLDERS = {
        "your_account_sid", "your_auth_token", "+1234567890", "+19876543210",
        "account_sid", "auth_token", "your_twilio_number", "your_api_key_sid", "your_api_key_secret"
    }

    def _is_valid(self, val: Optional[str]) -> bool:
        if not val:
            return False
        return str(val).strip().lower() not in self.PLACEHOLDERS

    def configuration_issues(self) -> List[str]:
        """Return safe, non-secret configuration diagnostics for the SMS provider."""
        issues: List[str] = []
        provider = str(settings.SMS_PROVIDER or "").strip().lower()
        if provider != "twilio":
            issues.append("SMS_PROVIDER must be twilio")
        if not re.fullmatch(r"AC[0-9a-fA-F]{32}", str(settings.SMS_ACCOUNT_ID or "")):
            issues.append("SMS_ACCOUNT_ID must be a Twilio Account SID")
        if not re.fullmatch(r"\+[1-9]\d{7,14}", str(settings.SMS_FROM_NUMBER or "")):
            issues.append("SMS_FROM_NUMBER must be an E.164 Twilio phone number")
        if not re.fullmatch(r"\+[1-9]\d{7,14}", str(settings.TEST_PHONE_NUMBER or "")):
            issues.append("TEST_PHONE_NUMBER must be an E.164 controlled test phone number")

        has_api_key = self._is_valid(settings.SMS_API_KEY_SID) and self._is_valid(settings.SMS_API_KEY_SECRET)
        has_auth_token = self._is_valid(settings.SMS_AUTH_TOKEN)
        if has_api_key:
            if not re.fullmatch(r"SK[0-9a-fA-F]{32}", str(settings.SMS_API_KEY_SID)):
                issues.append("SMS_API_KEY_SID must be a Twilio API Key SID")
            # Twilio API Key secrets are 32-character values. Never include one in diagnostics.
            if len(str(settings.SMS_API_KEY_SECRET)) != 32:
                issues.append("SMS_API_KEY_SECRET has an invalid Twilio API Key secret length")
        elif not has_auth_token:
            issues.append("SMS_AUTH_TOKEN or SMS_API_KEY_SID plus SMS_API_KEY_SECRET is required")
        return issues

    def is_configured(self) -> bool:
        return not self.configuration_issues()

    def _get_twilio_client(self):
        from twilio.rest import Client
        if self._is_valid(settings.SMS_API_KEY_SID) and self._is_valid(settings.SMS_API_KEY_SECRET) and self._is_valid(settings.SMS_ACCOUNT_ID):
            return Client(settings.SMS_API_KEY_SID, settings.SMS_API_KEY_SECRET, account_sid=settings.SMS_ACCOUNT_ID), "API Key"
        elif self._is_valid(settings.SMS_ACCOUNT_ID) and self._is_valid(settings.SMS_AUTH_TOKEN):
            return Client(settings.SMS_ACCOUNT_ID, settings.SMS_AUTH_TOKEN), "Auth Token"
        else:
            raise ValueError("Incomplete Twilio credentials")

    def send_sms(self, recipients: List[str], message: str) -> AdapterResult:
        provider_name = settings.SMS_PROVIDER or "Twilio SMS"

        if not self.is_configured():
            return AdapterResult(
                success=False,
                status=ProviderStatus.NOT_CONFIGURED,
                provider=provider_name,
                channel="SMS",
                recipient_count=0,
                details={"reason": "SMS Provider credentials missing or incomplete in .env"},
                error="SMS Provider not configured"
            )

        if not recipients:
            return AdapterResult(
                success=False,
                status=ProviderStatus.FAILED,
                provider=provider_name,
                channel="SMS",
                recipient_count=0,
                error="No SMS recipients specified"
            )

        try:
            if str(settings.SMS_PROVIDER).lower() == "twilio":
                client, auth_mode = self._get_twilio_client()
                
                last_sid = None
                last_status = "queued"
                sent_count = 0

                for phone in recipients:
                    if not self._is_valid(phone):
                        continue
                    res = client.messages.create(
                        body=message,
                        from_=settings.SMS_FROM_NUMBER,
                        to=phone
                    )
                    last_sid = res.sid
                    last_status = res.status
                    sent_count += 1

                if sent_count == 0:
                    return AdapterResult(
                        success=False,
                        status=ProviderStatus.FAILED,
                        provider="Twilio SMS",
                        channel="SMS",
                        recipient_count=0,
                        error="All specified recipient numbers were invalid or placeholders"
                    )

                status_enum = ProviderStatus.SENT if last_status in ("sent", "delivered") else ProviderStatus.QUEUED
                return AdapterResult(
                    success=True,
                    status=status_enum,
                    provider="Twilio SMS",
                    channel="SMS",
                    message_id=last_sid or f"SM{uuid.uuid4().hex[:8]}",
                    recipient_count=sent_count,
                    details={
                        "from": settings.SMS_FROM_NUMBER,
                        "recipients_count": sent_count,
                        "twilio_status": last_status,
                        "auth_mode": auth_mode
                    }
                )

            # A provider-specific implementation is required before any non-Twilio
            # message can be sent.  Never manufacture a provider result.
            return AdapterResult(
                success=False,
                status=ProviderStatus.FAILED,
                provider=provider_name,
                channel="SMS",
                recipient_count=0,
                error=f"Unsupported SMS provider: {settings.SMS_PROVIDER}"
            )

        except Exception as e:
            return AdapterResult(
                success=False,
                status=ProviderStatus.FAILED,
                provider=provider_name,
                channel="SMS",
                recipient_count=0,
                error=f"Twilio API Error: {str(e)}"
            )

    def get_delivery_status(self, message_id: str) -> Dict[str, Any]:
        """
        Retrieves live delivery status for a Twilio message SID.
        """
        if not self.is_configured() or not message_id or not message_id.startswith("SM"):
            return {"status": "UNKNOWN", "message_id": message_id}

        try:
            client, auth_mode = self._get_twilio_client()
            msg = client.messages(message_id).fetch()
            return {
                "message_id": msg.sid,
                "status": msg.status,
                "error_code": msg.error_code,
                "error_message": msg.error_message,
                "date_sent": str(msg.date_sent) if msg.date_sent else None,
                "auth_mode": auth_mode
            }
        except Exception as e:
            return {"status": "FAILED", "error": str(e), "message_id": message_id}


sms_adapter = SMSAdapter()
