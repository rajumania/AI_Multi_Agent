"""USGS earthquake feed adapter and geographic relevance filtering."""

from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from backend.config import settings
from backend.services.provider_health import provider_health

logger = logging.getLogger(__name__)


class EarthquakeProviderUnavailable(RuntimeError):
    pass


class EarthquakeEvent(BaseModel):
    event_id: str = Field(..., min_length=1, max_length=100)
    time: datetime
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    magnitude: float = Field(..., ge=-2, le=12)
    depth_km: float | None = Field(default=None, ge=-20, le=1000)
    event_type: str = "earthquake"
    source: str = "USGS"
    place: str = "Unknown location"
    distance_km: float | None = Field(default=None, ge=0)
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    freshness_seconds: float | None = Field(default=None, ge=0)
    status: str = "LIVE"

    @field_validator("magnitude", "latitude", "longitude", "depth_km", "distance_km")
    @classmethod
    def finite(cls, value):
        if value is not None and not math.isfinite(value):
            raise ValueError("earthquake values must be finite")
        return value


def _distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    value = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(max(0.0, 1 - value)))


class USGSEarthquakeProvider:
    name = "USGS"

    def __init__(self, client_factory=httpx.Client):
        self.client_factory = client_factory

    def fetch_recent(
        self,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_km: float | None = None,
        lookback_hours: int | None = None,
        min_magnitude: float | None = None,
    ) -> list[EarthquakeEvent]:
        if (latitude is None) != (longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        radius = settings.EARTHQUAKE_RADIUS_KM if radius_km is None else radius_km
        lookback = settings.EARTHQUAKE_LOOKBACK_HOURS if lookback_hours is None else lookback_hours
        minimum = settings.EARTHQUAKE_MIN_MAGNITUDE if min_magnitude is None else min_magnitude
        if radius <= 0 or radius > 2000 or lookback <= 0 or lookback > 720 or minimum < -2 or minimum > 12:
            raise ValueError("invalid earthquake query limits")
        now = datetime.now(timezone.utc)
        params: dict[str, Any] = {
            "format": "geojson",
            "eventtype": "earthquake",
            "starttime": (now - timedelta(hours=lookback)).isoformat(),
            "endtime": now.isoformat(),
            "minmagnitude": minimum,
            "orderby": "time",
            "limit": 200,
        }
        if latitude is not None and longitude is not None:
            params.update({"latitude": latitude, "longitude": longitude, "maxradiuskm": radius})
        started = time.perf_counter()
        try:
            payload = self._request(params)
            features = payload.get("features")
            if not isinstance(features, list):
                raise EarthquakeProviderUnavailable("USGS response did not contain features")
            events = [self._normalize(feature, latitude, longitude, now) for feature in features]
            events = [event for event in events if event is not None]
            provider_health.success(self.name, latency_ms=(time.perf_counter() - started) * 1000, source="usgs")
            return events
        except (EarthquakeProviderUnavailable, ValidationError, ValueError, TypeError) as exc:
            provider_health.failure(self.name, latency_ms=(time.perf_counter() - started) * 1000, error_type=type(exc).__name__, source="usgs")
            logger.warning("earthquake provider failed provider=%s error_type=%s", self.name, type(exc).__name__)
            raise EarthquakeProviderUnavailable(f"USGS request failed: {type(exc).__name__}") from exc

    @staticmethod
    def _normalize(feature: Any, latitude: float | None, longitude: float | None, received_at: datetime | None = None) -> EarthquakeEvent | None:
        if not isinstance(feature, dict):
            return None
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if not isinstance(coordinates, list) or len(coordinates) < 2 or properties.get("time") is None or properties.get("mag") is None:
            return None
        event_lat, event_lng = float(coordinates[1]), float(coordinates[0])
        distance = _distance_km(latitude, longitude, event_lat, event_lng) if latitude is not None and longitude is not None else None
        timestamp = datetime.fromtimestamp(float(properties["time"]) / 1000, timezone.utc)
        received_at = received_at or datetime.now(timezone.utc)
        freshness = max(0.0, (received_at - timestamp).total_seconds())
        stale_after = max(1, int(settings.EARTHQUAKE_STALE_AFTER_MINUTES)) * 60
        return EarthquakeEvent(event_id=str(feature.get("id") or properties.get("ids") or "unknown"), time=timestamp, latitude=event_lat, longitude=event_lng, magnitude=float(properties["mag"]), depth_km=float(coordinates[2]) if len(coordinates) > 2 and coordinates[2] is not None else None, event_type=str(properties.get("type") or "earthquake"), source="USGS", place=str(properties.get("place") or "Unknown location"), distance_km=distance, received_at=received_at, freshness_seconds=freshness, status="STALE" if freshness > stale_after else "LIVE")

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        attempts = max(1, settings.EARTHQUAKE_RETRIES + 1)
        for attempt in range(attempts):
            try:
                with self.client_factory(timeout=settings.EARTHQUAKE_TIMEOUT_SECONDS) as client:
                    response = client.get(settings.EARTHQUAKE_API_URL, params=params, headers={"User-Agent": "AITAM-Disaster-Response/1.0"})
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt + 1 < attempts:
                        time.sleep(settings.EARTHQUAKE_RETRY_BACKOFF_SECONDS * (2 ** attempt))
                        continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise EarthquakeProviderUnavailable("invalid_response")
                return payload
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt + 1 < attempts:
                    time.sleep(settings.EARTHQUAKE_RETRY_BACKOFF_SECONDS * (2 ** attempt))
                    continue
                raise EarthquakeProviderUnavailable(type(exc).__name__) from exc
            except httpx.HTTPStatusError as exc:
                raise EarthquakeProviderUnavailable(f"HTTP_{exc.response.status_code}") from exc
            except ValueError as exc:
                raise EarthquakeProviderUnavailable("invalid_json") from exc
        raise EarthquakeProviderUnavailable("provider_exhausted_retries")
