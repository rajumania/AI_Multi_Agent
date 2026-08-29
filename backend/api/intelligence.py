"""Location-driven external intelligence endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.deps import get_current_principal, get_optional_principal
from backend.database.database import get_db
from backend.models.intelligence import IntelligencePreviewRequest, IntelligencePreviewResponse
from backend.services.geocoding_provider import GeocodingProviderUnavailable, reverse_geocode
from backend.api.evidence import validate_reference_access
from backend.services.intelligence_service import analyze_location
from backend.services.severe_weather_providers import SevereWeatherProviderUnavailable, get_severe_weather_provider

router = APIRouter(prefix="/api/v1/intelligence", tags=["External Disaster Intelligence"])


@router.post("/preview", response_model=IntelligencePreviewResponse)
def preview_intelligence(payload: IntelligencePreviewRequest, db: Session = Depends(get_db), principal=Depends(get_current_principal)):
    validate_reference_access(payload.image_url, principal)
    result = analyze_location(db, payload)
    try:
        result["reverse_geocode"] = reverse_geocode(payload.latitude, payload.longitude)
    except GeocodingProviderUnavailable:
        result["reverse_geocode"] = {"label": f"Coordinates {payload.latitude:.6f}, {payload.longitude:.6f}", "source": "COORDINATES", "status": "OFFLINE", "latitude": payload.latitude, "longitude": payload.longitude}
    return result


@router.get("/reverse-geocode")
def reverse_location(latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180), _principal=Depends(get_optional_principal)):
    try:
        return reverse_geocode(latitude, longitude)
    except GeocodingProviderUnavailable:
        return {"label": f"Coordinates {latitude:.6f}, {longitude:.6f}", "source": "COORDINATES", "status": "OFFLINE", "latitude": latitude, "longitude": longitude}


@router.get("/severe-weather/alerts")
def severe_weather_alerts(latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180), radius_km: float | None = Query(None, gt=0, le=2000), _principal=Depends(get_optional_principal)):
    provider = get_severe_weather_provider()
    if provider is None:
        return {"provider": "IMD_CAP", "status": "NOT_CONFIGURED", "alerts": [], "message": "No authoritative severe-weather provider is configured."}
    try:
        alerts = provider.fetch_alerts(latitude, longitude, radius_km)
        return {"provider": "IMD_CAP", "status": "LIVE" if alerts else "NO_ACTIVE_WARNING", "alerts": [item.model_dump(mode="json") for item in alerts], "message": None if alerts else "No active severe-weather warning found for the selected coordinates."}
    except SevereWeatherProviderUnavailable:
        return {"provider": "IMD_CAP", "status": "OFFLINE", "alerts": [], "message": "Authoritative severe-weather provider is unavailable."}
