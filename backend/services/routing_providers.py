"""External route-provider adapters returning the app's route contract."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from backend.config import settings
from backend.services.provider_health import provider_health

logger = logging.getLogger(__name__)


class RouteProviderUnavailable(RuntimeError):
    pass


class NormalizedRoute(BaseModel):
    coordinates: list[tuple[float, float]] = Field(..., min_length=2)
    distance_meters: int = Field(..., ge=0)
    eta_seconds: int = Field(..., ge=0)
    routing_engine: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    source: str = "OSRM"
    data_status: str = "LIVE"

    @field_validator("coordinates")
    @classmethod
    def valid_coordinates(cls, value):
        for latitude, longitude in value:
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise ValueError("route geometry contains invalid coordinates")
        return value


class OSRMProvider:
    name = "OSRM"

    def __init__(self, client_factory=httpx.Client):
        self.client_factory = client_factory

    def route(self, origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> dict[str, Any]:
        url = f"{settings.ROUTING_BASE_URL.rstrip('/')}/route/v1/driving/{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
        params = {"overview": "full", "geometries": "geojson", "steps": "true"}
        started = time.perf_counter()
        try:
            payload = self._request(url, params)
            if payload.get("code") != "Ok":
                raise RouteProviderUnavailable(str(payload.get("code") or "provider_error"))
            routes = payload.get("routes")
            primary = routes[0] if isinstance(routes, list) and routes else None
            geometry = (primary or {}).get("geometry", {}).get("coordinates", [])
            if not isinstance(geometry, list) or len(geometry) < 2:
                raise RouteProviderUnavailable("route_geometry_missing")
            coordinates = [(float(point[1]), float(point[0])) for point in geometry if isinstance(point, (list, tuple)) and len(point) >= 2]
            raw_steps = ((primary or {}).get("legs") or [{}])[0].get("steps", [])
            steps = []
            for step in raw_steps if isinstance(raw_steps, list) else []:
                maneuver = step.get("maneuver") or {}
                steps.append({"instruction": f"{str(maneuver.get('type', 'continue')).capitalize()} onto {step.get('name') or 'unnamed road'}", "distance_meters": int(step.get("distance", 0) or 0), "duration_seconds": int(step.get("duration", 0) or 0)})
            normalized = NormalizedRoute(coordinates=coordinates, distance_meters=int((primary or {}).get("distance", 0) or 0), eta_seconds=int((primary or {}).get("duration", 0) or 0), routing_engine="OSRM (OpenStreetMap)", steps=steps, source="OSRM", data_status="LIVE")
            provider_health.success(self.name, latency_ms=(time.perf_counter() - started) * 1000, source="osrm")
            return normalized.model_dump()
        except (RouteProviderUnavailable, ValidationError, ValueError, TypeError) as exc:
            provider_health.failure(self.name, latency_ms=(time.perf_counter() - started) * 1000, error_type=type(exc).__name__, source="osrm")
            logger.warning("routing provider failed provider=%s error_type=%s", self.name, type(exc).__name__)
            raise RouteProviderUnavailable(f"OSRM request failed: {type(exc).__name__}") from exc

    def _request(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        attempts = max(1, settings.ROUTING_RETRIES + 1)
        for attempt in range(attempts):
            try:
                with self.client_factory(timeout=settings.ROUTING_TIMEOUT_SECONDS) as client:
                    response = client.get(url, params=params, headers={"User-Agent": "AITAM-Disaster-Response/1.0"})
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt + 1 < attempts:
                        time.sleep(settings.ROUTING_RETRY_BACKOFF_SECONDS * (2 ** attempt))
                        continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise RouteProviderUnavailable("invalid_response")
                return payload
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt + 1 < attempts:
                    time.sleep(settings.ROUTING_RETRY_BACKOFF_SECONDS * (2 ** attempt))
                    continue
                raise RouteProviderUnavailable(type(exc).__name__) from exc
            except httpx.HTTPStatusError as exc:
                raise RouteProviderUnavailable(f"HTTP_{exc.response.status_code}") from exc
            except ValueError as exc:
                raise RouteProviderUnavailable("invalid_json") from exc
        raise RouteProviderUnavailable("provider_exhausted_retries")
