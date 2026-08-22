import uuid
import urllib.request
import json
from typing import List, Dict, Any, Optional
from backend.config import settings
from backend.services.adapters.base_adapter import ProviderStatus, AdapterResult


class DispatchAdapter:
    """
    Real Authorized Campus Emergency Dispatch Adapter.
    Communicates directly with campus CAD (Computer-Aided Dispatch) or emergency webhook.
    Returns DISPATCH NOT CONNECTED if unconfigured.
    """

    def is_configured(self) -> bool:
        return bool(settings.DISPATCH_PROVIDER and settings.DISPATCH_API_URL)

    def dispatch_resources(self, incident_id: str, plan_id: str, resource_ids: List[str], target_location: str) -> AdapterResult:
        provider_name = settings.DISPATCH_PROVIDER or "Campus Dispatch System"

        if not self.is_configured():
            return AdapterResult(
                success=False,
                status=ProviderStatus.DISPATCH_NOT_CONNECTED,
                provider=provider_name,
                channel="Authorized Dispatch",
                recipient_count=0,
                details={
                    "notice": "External emergency dispatch requires integration with the campus emergency infrastructure.",
                    "configured": False
                },
                error="Dispatch API not connected"
            )

        try:
            payload = {
                "incident_id": incident_id,
                "plan_id": plan_id,
                "dispatched_units": resource_ids,
                "destination": target_location
            }

            req = urllib.request.Request(
                settings.DISPATCH_API_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {settings.DISPATCH_API_TOKEN or ''}"
                },
                method="POST"
            )

            try:
                with urllib.request.urlopen(req, timeout=5) as response:
                    resp_data = json.loads(response.read().decode("utf-8"))
                    disp_id = resp_data.get("dispatch_id", f"DISP-{uuid.uuid4().hex[:6]}")
                    return AdapterResult(
                        success=True,
                        status=ProviderStatus.ACCEPTED,
                        provider=provider_name,
                        channel="Authorized Dispatch",
                        message_id=disp_id,
                        recipient_count=len(resource_ids),
                        details=resp_data
                    )
            except Exception as http_err:
                # If webhook connection refused or timed out, report failure cleanly
                return AdapterResult(
                    success=False,
                    status=ProviderStatus.FAILED,
                    provider=provider_name,
                    channel="Authorized Dispatch",
                    recipient_count=0,
                    error=f"Campus CAD connection error: {str(http_err)}"
                )

        except Exception as e:
            return AdapterResult(
                success=False,
                status=ProviderStatus.FAILED,
                provider=provider_name,
                channel="Authorized Dispatch",
                recipient_count=0,
                error=str(e)
            )


dispatch_adapter = DispatchAdapter()
