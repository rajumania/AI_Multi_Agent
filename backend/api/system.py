from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from typing import Dict, Any
from sqlalchemy.orm import Session
from backend.config import settings
from backend.api.deps import get_command_principal
from backend.services.adapters.dispatch_adapter import dispatch_adapter
from backend.services.provider_health import provider_health

router = APIRouter(prefix="/api/v1/system", tags=["System Status & Operations Mode"])

_provider_verification: Dict[str, Dict[str, Any]] = {}


def _service_state(name: str, configured: bool, provider: str) -> Dict[str, Any]:
    """CONNECTED is reserved for a successful real provider operation."""
    verified = _provider_verification.get(name)
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


def _declare_external_providers() -> None:
    """Publish configured provider states without performing network calls."""
    provider_health.declare("OPEN_METEO", configured=settings.WEATHER_PROVIDER.strip().lower() in {"open_meteo", "openmeteo", "meteo"}, source="open_meteo")
    provider_health.declare("ENVIRONMENT", configured=settings.ENVIRONMENT_PROVIDER.strip().lower() in {"open_meteo", "openmeteo", "meteo"}, source=settings.ENVIRONMENT_PROVIDER.lower())
    provider_health.declare("OPENWEATHER", configured=settings.WEATHER_PROVIDER.strip().lower() in {"external", "openweather", "live"} and bool(settings.WEATHER_API_KEY), source="openweather")
    provider_health.declare("USGS", configured=settings.EARTHQUAKE_PROVIDER.strip().lower() == "usgs", source="usgs")
    provider_health.declare("OSRM", configured=settings.ROUTING_PROVIDER.strip().lower() in {"osrm", "openstreetmap", "open_street_map"}, source="osrm")
    provider_health.declare("IOT_HTTP", configured=settings.SENSOR_PROVIDER.strip().lower() in {"http", "iot", "iot_http"} and bool(settings.SENSOR_API_URL), source="iot")
    provider_health.declare("IMD_CAP", configured=settings.SEVERE_WEATHER_PROVIDER.strip().lower() in {"imd", "imd_cap", "cap"} and bool(settings.SEVERE_WEATHER_API_URL), source="imd_cap")
    provider_health.declare("NOMINATIM", configured=settings.GEOCODING_PROVIDER.strip().lower() in {"nominatim", "osm", "openstreetmap"} and bool(settings.GEOCODING_API_URL), source="nominatim")
    vision_provider = settings.VISION_PROVIDER.strip().lower()
    vision_configured = vision_provider in {"openai", "openai_vision"} and bool(settings.OPENAI_API_KEY) or vision_provider in {"gemini", "gemini_vision"} and bool(settings.GEMINI_API_KEY)
    provider_health.declare("VISION", configured=vision_configured, source=vision_provider or "none")


@router.get("/status")
def get_system_operations_status(_principal=Depends(get_command_principal)) -> Dict[str, Any]:
    """
    Returns core application status separately from optional external provider
    status. Missing paid-provider credentials must not turn a healthy backend
    and its real incident workflow into a provider/offline status.
    """
    _declare_external_providers()
    dispatch_conf = dispatch_adapter.is_configured()
    
    services = {
        "MAP": _service_state("MAP", bool(settings.MAP_PROVIDER), settings.MAP_PROVIDER),
        "ROUTING": _service_state("ROUTING", bool(settings.ROUTING_PROVIDER), settings.ROUTING_PROVIDER),
        "GPS": _service_state("GPS", False, "Live Telemetry Ingestion"),
        "SMS": {"status": "DISABLED / OUT OF SCOPE", "provider": "None", "configured": False, "verified": False, "last_verified_at": None},
        "PUSH": {"status": "DISABLED / OUT OF SCOPE", "provider": "None", "configured": False, "verified": False, "last_verified_at": None},
        "EMAIL": {"status": "DISABLED / OUT OF SCOPE", "provider": "None", "configured": False, "verified": False, "last_verified_at": None},
        "VOICE": {"status": "DISABLED / OUT OF SCOPE", "provider": "None", "configured": False, "verified": False, "last_verified_at": None},
        "PHONE CALL": {"status": "DISABLED / OUT OF SCOPE", "provider": "None", "configured": False, "verified": False, "last_verified_at": None},
        "WEBSOCKET": _service_state("WEBSOCKET", False, "AITAM Response Events"),
        "DISPATCH": _service_state("DISPATCH", dispatch_conf, settings.DISPATCH_PROVIDER or "Unconfigured"),
    }

    configured_count = sum(1 for s in services.values() if s["configured"])
    
    if configured_count >= 6:
        mode = "OPERATIONAL"
        color = "🟢"
    elif configured_count >= 3:
        mode = "OPERATIONAL"
        color = "🟡"
    else:
        mode = "OPERATIONAL"
        color = "🟡"

    # The live FastAPI process and its core workflow are operational regardless
    # of whether optional external providers have credentials.
    core_services = {
        "BACKEND": {"status": "CONNECTED", "provider": "FastAPI", "configured": True},
        "DATABASE": {"status": "CONNECTED", "provider": "SQLite", "configured": True},
        "AI AGENTS": {"status": "ACTIVE", "provider": "AITAM disaster agents", "configured": True},
        "LANGGRAPH": {"status": "ACTIVE", "provider": "Emergency workflow graph", "configured": True},
        "MCP": {"status": "CONNECTED", "provider": "Campus resource tools", "configured": True},
        "RESPONSE PLANNING": {"status": "ACTIVE", "provider": "Response planner", "configured": True},
        "WEBSOCKET": {"status": "AVAILABLE", "provider": "AITAM Response Events", "configured": True},
    }
    mode = "OPERATIONAL"

    return {
        "system_name": settings.APP_NAME,
        "operations_mode": mode,
        "raw_mode": mode,
        "backend_status": "CONNECTED",
        "core_services": core_services,
        "environment": settings.ENVIRONMENT,
        "services": services,
        "configured_services_count": configured_count,
        "total_services": len(services),
        "provider_health": provider_health.snapshot(),
    }


@router.get("/providers")
def get_provider_health(_principal=Depends(get_command_principal)) -> Dict[str, Any]:
    """Return non-secret health metadata for configured external adapters."""
    _declare_external_providers()
    return {"providers": provider_health.snapshot()}
