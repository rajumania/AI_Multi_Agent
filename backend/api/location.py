"""Best-effort reverse geocoding for user-selected coordinates."""

from fastapi import APIRouter, Depends, Query

from backend.api.deps import get_optional_principal
from backend.services.geocoding_provider import GeocodingProviderUnavailable, reverse_geocode

router = APIRouter(prefix="/api/v1/location", tags=["Location"])


@router.get("/reverse-geocode")
def reverse_location(latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180), _principal=Depends(get_optional_principal)):
    try:
        return reverse_geocode(latitude, longitude)
    except GeocodingProviderUnavailable:
        return {"label": f"Coordinates {latitude:.6f}, {longitude:.6f}", "source": "COORDINATES", "status": "OFFLINE", "latitude": latitude, "longitude": longitude}
