"""Weather provider adapters with one normalized application contract."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from backend.config import settings
from backend.services.provider_health import provider_health

logger = logging.getLogger(__name__)


class ProviderUnavailable(RuntimeError):
    pass


class NormalizedWeather(BaseModel):
    location: str = "unknown"
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    temperature_c: float | None = Field(default=None, ge=-100, le=70)
    humidity: float | None = Field(default=None, ge=0, le=100)
    rainfall_mm: float | None = Field(default=None, ge=0, le=10000)
    rainfall_intensity: float | None = Field(default=None, ge=0, le=1000)
    wind_speed_kph: float | None = Field(default=None, ge=0, le=500)
    wind_direction: float | None = Field(default=None, ge=0, le=360)
    # High-altitude locations can have valid surface pressure well below
    # 800 hPa (for example, Himalayan coordinates). Keep the bound broad
    # enough for real Open-Meteo observations without accepting nonsense.
    pressure: float | None = Field(default=None, ge=100, le=1200)
    precipitation_probability: float | None = Field(default=None, ge=0, le=100)
    condition: str = "unknown"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "demo"
    status: str = "FALLBACK"
    freshness_seconds: float | None = None

    @field_validator("temperature_c", "rainfall_mm", "rainfall_intensity", "wind_speed_kph", "pressure")
    @classmethod
    def finite(cls, value):
        if value is not None and (value != value or value in (float("inf"), float("-inf"))):
            raise ValueError("weather measurements must be finite")
        return value


class WeatherProvider(Protocol):
    def fetch_current(self, latitude: float | None = None, longitude: float | None = None, location: str = "unknown") -> NormalizedWeather: ...


def _freshness(observed: datetime, received: datetime) -> float:
    value = observed if observed.tzinfo else observed.replace(tzinfo=timezone.utc)
    return max(0.0, (received - value).total_seconds())


def _condition_from_code(code: Any) -> str:
    try:
        code = int(code)
    except (TypeError, ValueError):
        return "unknown"
    if code == 0:
        return "clear"
    if code in {1, 2, 3}:
        return "cloudy"
    if code in {45, 48}:
        return "fog"
    if code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}:
        return "rain"
    if code in {71, 73, 75, 77, 85, 86}:
        return "snow"
    if code in {95, 96, 99}:
        return "thunderstorm"
    return "unknown"


class DemoWeatherProvider:
    """Stable simulated telemetry; never labelled as live."""

    def fetch_current(self, latitude: float | None = None, longitude: float | None = None, location: str = "unknown") -> NormalizedWeather:
        now = datetime.now(timezone.utc)
        return NormalizedWeather(
            location=location, latitude=latitude, longitude=longitude,
            temperature_c=29.0, humidity=72.0, rainfall_mm=18.0,
            rainfall_intensity=5.0, wind_speed_kph=22.0, wind_direction=180.0,
            pressure=1008.0, precipitation_probability=60.0,
            condition="showers", timestamp=now, received_at=now,
            source="DEMO", status="FALLBACK", freshness_seconds=None,
        )


class OpenMeteoWeatherProvider:
    """Open-Meteo current-weather adapter.

    Open-Meteo does not require an API key for the public endpoint. Its model
    response is validated and translated before it enters risk processing.
    """

    name = "OPEN_METEO"

    def __init__(self, client_factory=httpx.Client):
        self.client_factory = client_factory

    def fetch_current(self, latitude: float | None = None, longitude: float | None = None, location: str = "unknown") -> NormalizedWeather:
        if latitude is None or longitude is None:
            raise ProviderUnavailable("Open-Meteo requires coordinates")
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,precipitation,rain,wind_speed_10m,wind_direction_10m,surface_pressure,weather_code",
            "timezone": "UTC",
        }
        started = time.perf_counter()
        try:
            payload = self._request(params)
            current = payload.get("current")
            if not isinstance(current, dict) or not current.get("time"):
                raise ProviderUnavailable("Open-Meteo response did not contain current weather")
            observed = datetime.fromisoformat(str(current["time"]).replace("Z", "+00:00"))
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            received = datetime.now(timezone.utc)
            freshness = _freshness(observed, received)
            result = NormalizedWeather(
                location=location, latitude=latitude, longitude=longitude,
                temperature_c=current.get("temperature_2m"),
                humidity=current.get("relative_humidity_2m"),
                rainfall_mm=current.get("precipitation"),
                rainfall_intensity=current.get("rain"),
                wind_speed_kph=current.get("wind_speed_10m"),
                wind_direction=current.get("wind_direction_10m"),
                pressure=current.get("surface_pressure"),
                condition=_condition_from_code(current.get("weather_code")),
                timestamp=observed, received_at=received, source="OPEN_METEO",
                status="STALE" if freshness > settings.WEATHER_STALE_AFTER_MINUTES * 60 else "LIVE",
                freshness_seconds=freshness,
            )
            provider_health.success(self.name, latency_ms=(time.perf_counter() - started) * 1000, freshness_seconds=freshness, source="open_meteo")
            return result
        except (ProviderUnavailable, ValidationError, ValueError, TypeError) as exc:
            provider_health.failure(self.name, latency_ms=(time.perf_counter() - started) * 1000, error_type=type(exc).__name__, source="open_meteo")
            logger.warning("weather provider failed provider=%s error_type=%s", self.name, type(exc).__name__)
            raise ProviderUnavailable(f"Open-Meteo request failed: {type(exc).__name__}") from exc

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        url = settings.WEATHER_API_URL or "https://api.open-meteo.com/v1/forecast"
        attempts = max(1, settings.WEATHER_RETRIES + 1)
        for attempt in range(attempts):
            try:
                with self.client_factory(timeout=settings.WEATHER_TIMEOUT_SECONDS) as client:
                    response = client.get(url, params=params, headers={"User-Agent": "AITAM-Disaster-Response/1.0"})
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt + 1 < attempts:
                        time.sleep(settings.WEATHER_RETRY_BACKOFF_SECONDS * (2 ** attempt))
                        continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ProviderUnavailable("Open-Meteo response was not an object")
                return payload
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt + 1 < attempts:
                    time.sleep(settings.WEATHER_RETRY_BACKOFF_SECONDS * (2 ** attempt))
                    continue
                raise ProviderUnavailable(type(exc).__name__) from exc
            except httpx.HTTPStatusError as exc:
                raise ProviderUnavailable(f"HTTP_{exc.response.status_code}") from exc
            except ValueError as exc:
                raise ProviderUnavailable("invalid_json") from exc
        raise ProviderUnavailable("provider_exhausted_retries")


class ExternalWeatherProvider:
    """Backward-compatible OpenWeather-compatible adapter."""

    def fetch_current(self, latitude: float | None = None, longitude: float | None = None, location: str = "unknown") -> NormalizedWeather:
        if not settings.WEATHER_API_URL or not settings.WEATHER_API_KEY:
            raise ProviderUnavailable("external weather provider is not configured")
        if latitude is None or longitude is None:
            raise ProviderUnavailable("external weather provider requires coordinates")
        started = time.perf_counter()
        try:
            payload = self._request({"lat": latitude, "lon": longitude, "appid": settings.WEATHER_API_KEY, "units": "metric"})
            main, wind, rain = payload.get("main") or {}, payload.get("wind") or {}, payload.get("rain") or {}
            observed = datetime.fromtimestamp(payload["dt"], timezone.utc) if payload.get("dt") else datetime.now(timezone.utc)
            received = datetime.now(timezone.utc)
            freshness = _freshness(observed, received)
            result = NormalizedWeather(location=location, latitude=latitude, longitude=longitude, temperature_c=main.get("temp"), humidity=main.get("humidity"), pressure=main.get("pressure"), rainfall_mm=rain.get("1h", rain.get("3h")), wind_speed_kph=(wind.get("speed", 0) or 0) * 3.6, wind_direction=wind.get("deg"), condition=(payload.get("weather") or [{}])[0].get("description") or "unknown", timestamp=observed, received_at=received, source="OPENWEATHER", status="STALE" if freshness > settings.WEATHER_STALE_AFTER_MINUTES * 60 else "LIVE", freshness_seconds=freshness)
            provider_health.success("OPENWEATHER", latency_ms=(time.perf_counter() - started) * 1000, freshness_seconds=freshness, source="openweather")
            return result
        except (ProviderUnavailable, httpx.HTTPError, ValueError, ValidationError, KeyError, TypeError) as exc:
            provider_health.failure("OPENWEATHER", latency_ms=(time.perf_counter() - started) * 1000, error_type=type(exc).__name__, source="openweather")
            raise ProviderUnavailable(f"external weather provider failed: {type(exc).__name__}") from exc

    @staticmethod
    def _request(params: dict[str, Any]) -> dict[str, Any]:
        attempts = max(1, settings.WEATHER_RETRIES + 1)
        for attempt in range(attempts):
            try:
                with httpx.Client(timeout=settings.WEATHER_TIMEOUT_SECONDS) as client:
                    response = client.get(settings.WEATHER_API_URL, params=params, headers={"User-Agent": "AITAM-Disaster-Response/1.0"})
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt + 1 < attempts:
                        time.sleep(settings.WEATHER_RETRY_BACKOFF_SECONDS * (2 ** attempt))
                        continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ProviderUnavailable("invalid_response")
                return payload
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt + 1 < attempts:
                    time.sleep(settings.WEATHER_RETRY_BACKOFF_SECONDS * (2 ** attempt))
                    continue
                raise ProviderUnavailable(type(exc).__name__) from exc
            except httpx.HTTPStatusError as exc:
                raise ProviderUnavailable(f"HTTP_{exc.response.status_code}") from exc
            except ValueError as exc:
                raise ProviderUnavailable("invalid_json") from exc
        raise ProviderUnavailable("provider_exhausted_retries")


def get_weather_provider() -> WeatherProvider:
    provider = settings.WEATHER_PROVIDER.strip().lower()
    if provider in {"open_meteo", "openmeteo", "meteo"}:
        return OpenMeteoWeatherProvider()
    if provider in {"external", "openweather", "live"}:
        return ExternalWeatherProvider()
    return DemoWeatherProvider()


def fetch_with_fallback(provider: WeatherProvider | None = None, latitude: float | None = None, longitude: float | None = None, location: str = "unknown") -> tuple[NormalizedWeather, str | None]:
    provider = provider or get_weather_provider()
    try:
        return provider.fetch_current(latitude=latitude, longitude=longitude, location=location), None
    except (ProviderUnavailable, ValidationError) as exc:
        if not settings.ALLOW_DETERMINISTIC_FALLBACK:
            raise
        demo = DemoWeatherProvider().fetch_current(latitude=latitude, longitude=longitude, location=location)
        demo.source = "DEMO_FALLBACK"
        demo.status = "FALLBACK"
        demo.freshness_seconds = None
        provider_health.mark_fallback(type(provider).__name__.replace("Provider", "").upper(), source="demo")
        logger.warning("weather provider fallback provider=%s error_type=%s", type(provider).__name__, type(exc).__name__)
        return demo, str(exc)
