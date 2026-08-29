"""Environmental provider contracts and normalized Open-Meteo adapter."""

import time
from typing import Protocol

from backend.database.models import ZoneDB
from backend.config import settings
from backend.services.provider_health import provider_health
from backend.services.weather_providers import OpenMeteoWeatherProvider, ProviderUnavailable


class EnvironmentalProvider(Protocol):
    def fetch_for_zone(self, zone: ZoneDB) -> list[dict]: ...


class DemoEnvironmentalProvider:
    """Deterministic, explicitly simulated zone indicators."""

    def fetch_for_zone(self, zone: ZoneDB) -> list[dict]:
        return [
            {"indicator": "water_level_score", "value": 35.0, "unit": "normalized", "source": "DEMO"},
            {"indicator": "soil_moisture", "value": 58.0, "unit": "percent", "source": "DEMO"},
            {"indicator": "drainage_vulnerability", "value": zone.drainage_vulnerability if zone.drainage_vulnerability is not None else 45.0, "unit": "score", "source": "DEMO"},
        ]


class OpenMeteoEnvironmentalProvider:
    """Expose Open-Meteo weather/environment fields as app indicators."""

    def __init__(self, weather_provider: OpenMeteoWeatherProvider | None = None):
        self.weather_provider = weather_provider or OpenMeteoWeatherProvider()

    def fetch_for_zone(self, zone: ZoneDB) -> list[dict]:
        started = time.perf_counter()
        try:
            weather = self.weather_provider.fetch_current(zone.latitude, zone.longitude, zone.name)
        except Exception as exc:
            provider_health.failure(
                "ENVIRONMENT",
                latency_ms=(time.perf_counter() - started) * 1000,
                error_type=type(exc).__name__,
                source="open_meteo",
            )
            raise
        provider_health.success(
            "ENVIRONMENT",
            latency_ms=(time.perf_counter() - started) * 1000,
            freshness_seconds=weather.freshness_seconds,
            source="open_meteo",
        )
        observed_at = weather.timestamp
        received_at = weather.received_at
        common = {"source": "OPEN_METEO", "observed_at": observed_at, "received_at": received_at, "location": zone.name, "latitude": zone.latitude, "longitude": zone.longitude}
        values = [
            ("rainfall_mm", weather.rainfall_mm, "mm"),
            ("humidity_percent", weather.humidity, "percent"),
            ("wind_speed_kph", weather.wind_speed_kph, "kph"),
            ("pressure_hpa", weather.pressure, "hPa"),
        ]
        return [{**common, "indicator": indicator, "value": value, "unit": unit, "status": weather.status, "freshness_seconds": weather.freshness_seconds} for indicator, value, unit in values if value is not None]


def get_environmental_provider() -> EnvironmentalProvider:
    if settings.ENVIRONMENT_PROVIDER.strip().lower() in {"open_meteo", "openmeteo", "meteo"}:
        return OpenMeteoEnvironmentalProvider()
    return DemoEnvironmentalProvider()
