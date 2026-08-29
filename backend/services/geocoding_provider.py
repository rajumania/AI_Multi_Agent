"""Best-effort reverse geocoding for human-readable location labels."""

from __future__ import annotations

import time
from typing import Any

import httpx

from backend.config import settings
from backend.services.provider_health import provider_health


class GeocodingProviderUnavailable(RuntimeError):
    pass


class NominatimProvider:
    name = "NOMINATIM"

    def __init__(self, client_factory=httpx.Client):
        self.client_factory = client_factory

    def reverse(self, latitude: float, longitude: float) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            attempts = max(1, settings.GEOCODING_RETRIES + 1)
            for attempt in range(attempts):
                try:
                    with self.client_factory(timeout=settings.GEOCODING_TIMEOUT_SECONDS) as client:
                        response = client.get(
                            settings.GEOCODING_API_URL,
                            params={"lat": latitude, "lon": longitude, "format": "jsonv2", "zoom": 18, "addressdetails": 1},
                            headers={"User-Agent": "AITAM-Disaster-Response/1.0 (location intelligence)"},
                        )
                    if response.status_code == 429 or response.status_code >= 500:
                        if attempt + 1 < attempts:
                            time.sleep(settings.GEOCODING_RETRY_BACKOFF_SECONDS * (2 ** attempt))
                            continue
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict) or not payload.get("display_name"):
                        raise GeocodingProviderUnavailable("reverse_geocoder returned no label")
                    provider_health.success(self.name, latency_ms=(time.perf_counter() - started) * 1000, source="nominatim")
                    return {"label": str(payload["display_name"]), "source": "NOMINATIM", "status": "LIVE", "latitude": latitude, "longitude": longitude}
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt + 1 < attempts:
                        time.sleep(settings.GEOCODING_RETRY_BACKOFF_SECONDS * (2 ** attempt))
                        continue
                    raise GeocodingProviderUnavailable(type(exc).__name__) from exc
                except httpx.HTTPStatusError as exc:
                    raise GeocodingProviderUnavailable(f"HTTP_{exc.response.status_code}") from exc
            raise GeocodingProviderUnavailable("provider_exhausted_retries")
        except (GeocodingProviderUnavailable, ValueError, TypeError) as exc:
            provider_health.failure(self.name, latency_ms=(time.perf_counter() - started) * 1000, error_type=type(exc).__name__, source="nominatim")
            raise GeocodingProviderUnavailable(str(exc)) from exc


def reverse_geocode(latitude: float, longitude: float) -> dict[str, Any]:
    if settings.GEOCODING_PROVIDER.strip().lower() not in {"nominatim", "osm", "openstreetmap"}:
        raise GeocodingProviderUnavailable("reverse geocoding provider is not configured")
    return NominatimProvider().reverse(latitude, longitude)
