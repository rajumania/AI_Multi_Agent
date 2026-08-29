"""Authoritative severe-weather and cyclone warning adapters.

The default provider is the India Meteorological Department CAP RSS feed
published through the WMO alerting ecosystem.  CAP alerts are treated as
authoritative warning evidence; reporter photos/text can corroborate local
conditions but never create a cyclone warning.
"""

from __future__ import annotations

import math
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from backend.config import settings
from backend.services.provider_health import provider_health


class SevereWeatherProviderUnavailable(RuntimeError):
    pass


class SevereWeatherAlert(BaseModel):
    alert_id: str = Field(..., min_length=1, max_length=240)
    title: str
    event: str = "Severe weather"
    description: str = ""
    affected_area: str = "Unspecified area"
    severity: str = "unknown"
    urgency: str = "unknown"
    certainty: str = "unknown"
    issued_at: datetime
    expires_at: datetime | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    distance_km: float | None = Field(default=None, ge=0)
    source: str = "IMD_CAP"
    status: str = "LIVE"
    freshness_seconds: float | None = None
    geometry: dict[str, Any] | None = None

    @field_validator("latitude", "longitude", "distance_km")
    @classmethod
    def finite(cls, value):
        if value is not None and not math.isfinite(value):
            raise ValueError("alert coordinates must be finite")
        return value


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _text(element: ET.Element | None, name: str) -> str | None:
    if element is None:
        return None
    for child in element.iter():
        if _local_name(child.tag) == name.lower() and child.text:
            return child.text.strip()
    return None


def _parse_time(value: str | None, fallback: datetime) -> datetime:
    if not value:
        return fallback
    raw = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return fallback
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))


def _points(value: str | None) -> list[tuple[float, float]]:
    if not value:
        return []
    result = []
    for token in value.replace(";", " ").split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            result.append((float(parts[0]), float(parts[1])))
        except ValueError:
            continue
    return result


def _geometry(alert: ET.Element) -> tuple[dict[str, Any] | None, list[tuple[float, float]]]:
    circle = _text(alert, "circle")
    points = _points(circle)
    if points:
        # CAP circle is "lat,lon radius-km".  Keep the radius in the
        # normalized geometry; the matching point is the circle centre.
        radius = None
        try:
            radius = float(circle.split()[-1])
        except (ValueError, IndexError):
            pass
        return {"type": "Circle", "center": points[0], "radius_km": radius}, points[:1]
    polygon = _text(alert, "polygon")
    points = _points(polygon)
    if points:
        return {"type": "Polygon", "coordinates": points}, points
    point = _text(alert, "point") or _text(alert, "georss:point")
    points = _points(point)
    if points:
        return {"type": "Point", "coordinates": points[0]}, points
    return None, []


def _severity(value: str | None) -> str:
    raw = (value or "").strip().lower()
    return raw if raw in {"extreme", "severe", "moderate", "minor", "unknown"} else "unknown"


class IMDCAPProvider:
    name = "IMD_CAP"

    def __init__(self, client_factory=httpx.Client):
        self.client_factory = client_factory

    def fetch_alerts(self, latitude: float | None = None, longitude: float | None = None, radius_km: float | None = None) -> list[SevereWeatherAlert]:
        if (latitude is None) != (longitude is None):
            raise SevereWeatherProviderUnavailable("coordinates must be supplied together")
        started = time.perf_counter()
        now = datetime.now(timezone.utc)
        try:
            payload = self._request()
            root = ET.fromstring(payload)
            alerts: list[SevereWeatherAlert] = []
            entries = [entry for entry in root.iter() if _local_name(entry.tag) in {"item", "entry", "alert"}]
            for entry in entries:
                info = next((child for child in entry.iter() if _local_name(child.tag) == "info"), entry)
                geometry, points = _geometry(entry)
                issued = _parse_time(_text(info, "sent") or _text(entry, "pubdate") or _text(entry, "updated"), now)
                expires = _parse_time(_text(info, "expires"), now)
                if expires <= now:
                    continue
                distance = None
                if latitude is not None and longitude is not None:
                    if not points:
                        # No geographic geometry means the alert cannot be
                        # safely attributed to an exact user point.
                        continue
                    distance = min(_distance_km(latitude, longitude, p[0], p[1]) for p in points)
                    limit = radius_km if radius_km is not None else settings.SEVERE_WEATHER_RADIUS_KM
                    if distance > limit:
                        continue
                identifier = _text(entry, "identifier") or _text(entry, "guid") or _text(entry, "id")
                if not identifier:
                    identifier = f"IMD-{issued.strftime('%Y%m%dT%H%M%SZ')}-{len(alerts) + 1}"
                alert = SevereWeatherAlert(
                    alert_id=identifier,
                    title=_text(info, "headline") or _text(entry, "title") or "IMD severe weather warning",
                    event=_text(info, "event") or "Severe weather",
                    description=_text(info, "description") or _text(entry, "description") or "",
                    affected_area=_text(info, "areadesc") or "Unspecified area",
                    severity=_severity(_text(info, "severity")),
                    urgency=(_text(info, "urgency") or "unknown").lower(),
                    certainty=(_text(info, "certainty") or "unknown").lower(),
                    issued_at=issued,
                    expires_at=expires,
                    latitude=points[0][0] if points else None,
                    longitude=points[0][1] if points else None,
                    distance_km=distance,
                    source="IMD_CAP",
                    status="STALE" if (now - issued).total_seconds() > settings.SEVERE_WEATHER_STALE_AFTER_MINUTES * 60 else "LIVE",
                    freshness_seconds=max(0.0, (now - issued).total_seconds()),
                    geometry=geometry,
                )
                alerts.append(alert)
            provider_health.success(self.name, latency_ms=(time.perf_counter() - started) * 1000, source="imd_cap")
            return alerts
        except (ET.ParseError, SevereWeatherProviderUnavailable, ValidationError, ValueError, TypeError) as exc:
            provider_health.failure(self.name, latency_ms=(time.perf_counter() - started) * 1000, error_type=type(exc).__name__, source="imd_cap")
            raise SevereWeatherProviderUnavailable(f"IMD CAP request failed: {type(exc).__name__}") from exc

    def _request(self) -> bytes:
        attempts = max(1, settings.SEVERE_WEATHER_RETRIES + 1)
        for attempt in range(attempts):
            try:
                with self.client_factory(timeout=settings.SEVERE_WEATHER_TIMEOUT_SECONDS) as client:
                    response = client.get(settings.SEVERE_WEATHER_API_URL, headers={"User-Agent": "AITAM-Disaster-Response/1.0"})
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt + 1 < attempts:
                        time.sleep(settings.SEVERE_WEATHER_RETRY_BACKOFF_SECONDS * (2 ** attempt))
                        continue
                response.raise_for_status()
                return response.content
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt + 1 < attempts:
                    time.sleep(settings.SEVERE_WEATHER_RETRY_BACKOFF_SECONDS * (2 ** attempt))
                    continue
                raise SevereWeatherProviderUnavailable(type(exc).__name__) from exc
            except httpx.HTTPStatusError as exc:
                raise SevereWeatherProviderUnavailable(f"HTTP_{exc.response.status_code}") from exc
        raise SevereWeatherProviderUnavailable("provider_exhausted_retries")


def get_severe_weather_provider() -> IMDCAPProvider | None:
    if settings.SEVERE_WEATHER_PROVIDER.strip().lower() in {"imd", "imd_cap", "cap", "india_meteorological_department"}:
        return IMDCAPProvider()
    return None
