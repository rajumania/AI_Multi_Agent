import json
import os
from typing import List, Dict, Any, Optional
from backend.config import settings
from backend.services.adapters.base_adapter import ProviderStatus, AdapterResult


class PushAdapter:
    """
    Real Push Notification Service Adapter (FCM / WebPush / APNS).
    Sends emergency notifications to registered mobile devices.
    """

    def __init__(self):
        self._registered_tokens: List[str] = []

    def is_configured(self) -> bool:
        return not self.configuration_issues()

    def configuration_issues(self) -> List[str]:
        issues = []
        if str(settings.PUSH_PROVIDER or "").lower() != "fcm": issues.append("PUSH_PROVIDER")
        if not settings.PUSH_CREDENTIALS: issues.append("PUSH_CREDENTIALS")
        if not settings.TEST_DEVICE_TOKEN: issues.append("TEST_DEVICE_TOKEN")
        if settings.PUSH_CREDENTIALS and not (os.path.isfile(settings.PUSH_CREDENTIALS) or str(settings.PUSH_CREDENTIALS).lstrip().startswith("{")):
            issues.append("PUSH_CREDENTIALS")
        return issues

    def _firebase_app(self):
        import firebase_admin
        from firebase_admin import credentials
        if firebase_admin._apps:
            return firebase_admin.get_app()
        raw = str(settings.PUSH_CREDENTIALS)
        credential = credentials.Certificate(json.loads(raw)) if raw.lstrip().startswith("{") else credentials.Certificate(raw)
        return firebase_admin.initialize_app(credential)

    def validate_configuration(self) -> AdapterResult:
        """Loads Firebase credentials locally; it never sends a push notification."""
        if not self.is_configured():
            return AdapterResult(False, ProviderStatus.NOT_CONFIGURED, "FCM", "Push Notification", details={"missing": self.configuration_issues()}, error="FCM provider not configured")
        try:
            self._firebase_app()
            return AdapterResult(True, ProviderStatus.ACCEPTED, "Firebase Cloud Messaging", "Push Notification")
        except Exception:
            return AdapterResult(False, ProviderStatus.FAILED, "FCM", "Push Notification", error="FCM credentials could not be loaded")

    def register_device_token(self, token: str):
        if token not in self._registered_tokens:
            self._registered_tokens.append(token)

    def send_push(self, title: str, body: str, target_tokens: Optional[List[str]] = None) -> AdapterResult:
        provider_name = settings.PUSH_PROVIDER or "FCM Push"
        tokens = target_tokens if target_tokens is not None else self._registered_tokens

        if not self.is_configured():
            return AdapterResult(
                success=False,
                status=ProviderStatus.NOT_CONFIGURED,
                provider=provider_name,
                channel="Push Notification",
                recipient_count=0,
                details={"reason": "Push Notification provider credentials missing in .env"},
                error="Push provider not configured"
            )

        if not tokens:
            return AdapterResult(
                success=False,
                status=ProviderStatus.NO_REGISTERED_DEVICES,
                provider=provider_name,
                channel="Push Notification",
                recipient_count=0,
                details={"reason": "No active device push tokens registered in emergency directory"},
                error="No registered devices"
            )

        try:
            if str(settings.PUSH_PROVIDER).lower() != "fcm":
                return AdapterResult(False, ProviderStatus.FAILED, provider_name, "Push Notification", error="Unsupported push provider")
            from firebase_admin import messaging
            self._firebase_app()
            responses = [messaging.send(messaging.Message(notification=messaging.Notification(title=title, body=body), token=token)) for token in tokens]
            return AdapterResult(
                success=True,
                status=ProviderStatus.SENT,
                provider="Firebase Cloud Messaging",
                channel="Push Notification",
                message_id=responses[-1] if responses else None,
                recipient_count=len(tokens),
                details={"title": title, "tokens_count": len(tokens)}
            )
        except Exception as e:
            return AdapterResult(
                success=False,
                status=ProviderStatus.FAILED,
                provider=provider_name,
                channel="Push Notification",
                recipient_count=0,
                error=str(e)
            )


push_adapter = PushAdapter()
