from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from typing import Dict, Any
from sqlalchemy.orm import Session
from backend.config import settings
from backend.database.database import get_db
from backend.database.database import SessionLocal
from backend.database.models import AuditLogDB
from backend.services.audit_service import audit_service
from backend.services.event_engine import event_engine
from backend.services.adapters.sms_adapter import sms_adapter
from backend.services.adapters.push_adapter import push_adapter
from backend.services.adapters.email_adapter import email_adapter
from backend.services.adapters.voice_adapter import voice_adapter
from backend.services.adapters.dispatch_adapter import dispatch_adapter

router = APIRouter(prefix="/api/v1/system", tags=["System Status & Operations Mode"])

_provider_verification: Dict[str, Dict[str, Any]] = {}


def _service_state(name: str, configured: bool, provider: str) -> Dict[str, Any]:
    """CONNECTED is reserved for a successful real provider operation."""
    verified = _provider_verification.get(name) or _persisted_verification(name)
    if verified:
        return {"status": verified["status"], "provider": provider, "configured": configured,
                "verified": True, "last_verified_at": verified["timestamp"]}
    return {"status": "DEGRADED" if configured else "NOT CONFIGURED", "provider": provider,
            "configured": configured, "verified": False, "last_verified_at": None}


def record_provider_verification(name: str, success: bool) -> None:
    _provider_verification[name] = {
        "status": "CONNECTED" if success else "FAILED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _persisted_verification(name: str) -> Dict[str, Any] | None:
    """Keep verified/failed SMS state after an API process restart without storing secrets."""
    action_map = {
        "SMS": ("sms_verification_succeeded", "sms_verification_failed"),
    }
    actions = action_map.get(name)
    if not actions:
        return None
    db = SessionLocal()
    try:
        entry = db.query(AuditLogDB).filter(AuditLogDB.action_type.in_(actions)).order_by(AuditLogDB.timestamp.desc()).first()
        if not entry:
            return None
        return {"status": "CONNECTED" if entry.action_type.endswith("succeeded") else "FAILED",
                "timestamp": entry.timestamp.isoformat()}
    finally:
        db.close()


@router.get("/status")
def get_system_operations_status() -> Dict[str, Any]:
    """
    Returns real-time system operational status, provider connectivity, and active operations mode.
    Mode is LIVE CONNECTED if at least key services are configured, DEMO MODE if running in dev simulation, or DEGRADED.
    """
    push_conf = push_adapter.is_configured()
    email_conf = email_adapter.is_configured()
    voice_conf = voice_adapter.is_telephony_configured()
    dispatch_conf = dispatch_adapter.is_configured()
    
    services = {
        "MAP": _service_state("MAP", bool(settings.MAP_PROVIDER), settings.MAP_PROVIDER),
        "ROUTING": _service_state("ROUTING", bool(settings.ROUTING_PROVIDER), settings.ROUTING_PROVIDER),
        "GPS": _service_state("GPS", False, "Live Telemetry Ingestion"),
        "SMS": {"status": "OPTIONAL / NOT CONFIGURED", "provider": "Optional", "configured": False, "verified": False, "last_verified_at": None},
        "PUSH": _service_state("PUSH", push_conf, settings.PUSH_PROVIDER or "Unconfigured"),
        "EMAIL": _service_state("EMAIL", email_conf, f"SMTP ({settings.SMTP_HOST})" if email_conf else "Unconfigured"),
        "VOICE": {"status": "BROWSER READY (CLIENT VALIDATION PENDING)", "provider": "Web Speech API", "configured": True, "verified": False, "last_verified_at": None},
        "PHONE CALL": _service_state("PHONE CALL", voice_conf, settings.VOICE_PROVIDER or "Unconfigured"),
        "WEBSOCKET": _service_state("WEBSOCKET", False, "CampusFlow Events"),
        "DISPATCH": _service_state("DISPATCH", dispatch_conf, settings.DISPATCH_PROVIDER or "Unconfigured"),
    }

    configured_count = sum(1 for s in services.values() if s["configured"])
    
    if configured_count >= 6:
        mode = "LIVE CONNECTED"
        color = "🟢"
    elif configured_count >= 3:
        mode = "DEMO MODE (HYBRID)"
        color = "🟡"
    else:
        mode = "DEMO MODE"
        color = "🟡"

    return {
        "system_name": settings.APP_NAME,
        "operations_mode": f"{color} {mode}",
        "raw_mode": mode,
        "environment": settings.ENVIRONMENT,
        "services": services,
        "configured_services_count": configured_count,
        "total_services": len(services)
    }


@router.post("/test-sms")
def test_sms_integration(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Triggers controlled real SMS verification test using configured TEST_PHONE_NUMBER.
    Records provider response, Message SID, and audit log. Never exposes secrets.
    """
    configured = sms_adapter.is_configured()
    missing = []
    if not sms_adapter._is_valid(settings.SMS_PROVIDER): missing.append("SMS_PROVIDER")
    if not sms_adapter._is_valid(settings.SMS_ACCOUNT_ID): missing.append("SMS_ACCOUNT_ID")
    if not sms_adapter._is_valid(settings.SMS_FROM_NUMBER): missing.append("SMS_FROM_NUMBER")
    if not sms_adapter._is_valid(settings.TEST_PHONE_NUMBER): missing.append("TEST_PHONE_NUMBER")
    
    has_api_key = sms_adapter._is_valid(settings.SMS_API_KEY_SID) and sms_adapter._is_valid(settings.SMS_API_KEY_SECRET)
    has_auth_token = sms_adapter._is_valid(settings.SMS_AUTH_TOKEN)
    if not (has_api_key or has_auth_token):
        missing.append("SMS_AUTH_TOKEN or (SMS_API_KEY_SID and SMS_API_KEY_SECRET)")

    if missing or not configured:
        record_provider_verification("SMS", False)
        audit_service.log("sms_verification_failed", "Controlled SMS verification was not sent because configuration is incomplete.", actor="system", details={"missing": missing}, db=db)
        return {
            "status": "NOT CONFIGURED",
            "success": False,
            "provider": "Twilio SMS",
            "missing": missing,
            "error": "SMS Provider credentials missing or incomplete in .env"
        }

    res = sms_adapter.send_sms(
        recipients=[settings.TEST_PHONE_NUMBER],
        message="CAMPUSFLOW AI: Controlled Real-Time Twilio SMS Test"
    )

    delivery_status = "UNKNOWN"
    if res.success and res.message_id:
        deliv_res = sms_adapter.get_delivery_status(res.message_id)
        delivery_status = deliv_res.get("status", "queued")

    record_provider_verification("SMS", res.success)
    event_name = "provider_connected" if res.success else "provider_failed"
    audit_service.log(
        "sms_verification_succeeded" if res.success else "sms_verification_failed",
        "Controlled SMS verification received a provider response.",
        actor="system",
        details={"provider": res.provider, "success": res.success, "message_id": res.message_id,
                 "provider_status": res.status.value, "delivery_status": delivery_status, "error": res.error},
        db=db,
    )
    event_engine.publish_event(event_name, "system", {
        "event_name": event_name, "provider": res.provider, "channel": "SMS",
        "status": res.status.value, "message_id": res.message_id, "delivery_status": delivery_status,
    }, db=db)

    return {
        "status": "CONNECTED" if res.success else "FAILED",
        "success": res.success,
        "provider": res.provider,
        "auth_mode": res.details.get("auth_mode") if res.details else None,
        "message_id": res.message_id,
        "delivery_status": delivery_status,
        "details": res.details,
        "error": res.error
    }
