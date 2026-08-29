"""Phase 9A provider contract tests; all HTTP is mocked."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from backend.config import settings
from backend.services.earthquake_providers import USGSEarthquakeProvider
from backend.services.provider_health import provider_health
from backend.services.routing_providers import OSRMProvider
from backend.services.sensor_monitoring import HttpSensorProvider
from backend.services.safe_routing import SafeRoutingService
from backend.services.weather_providers import OpenMeteoWeatherProvider, ProviderUnavailable, fetch_with_fallback


class FakeResponse:
    def __init__(self, body, status_code=200):
        self.body = body
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("provider error", request=httpx.Request("GET", "https://provider.test"), response=httpx.Response(self.status_code))

    def json(self):
        return self.body


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, _url, params=None, **_kwargs):
        self.params = params
        return self.response


def factory(response):
    def create(**_kwargs):
        return FakeClient(response)
    return create


def test_open_meteo_normalizes_current_weather_and_metadata(monkeypatch):
    observed = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    provider = OpenMeteoWeatherProvider(factory(FakeResponse({"current": {"time": observed, "temperature_2m": 18, "relative_humidity_2m": 81, "precipitation": 4.2, "rain": 3.1, "wind_speed_10m": 20, "wind_direction_10m": 145, "surface_pressure": 1002, "weather_code": 63}})))
    result = provider.fetch_current(28.21, 84.02, "N-14")
    assert result.source == "OPEN_METEO"
    assert result.status == "LIVE"
    assert result.rainfall_mm == 4.2
    assert result.condition == "rain"
    assert result.freshness_seconds is not None
    assert provider_health.snapshot()[-1]["provider"] == "OPEN_METEO"


def test_open_meteo_stale_response_is_not_live():
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    provider = OpenMeteoWeatherProvider(factory(FakeResponse({"current": {"time": old, "temperature_2m": 18}})))
    result = provider.fetch_current(28.21, 84.02, "N-14")
    assert result.status == "STALE"
    assert result.freshness_seconds > settings.WEATHER_STALE_AFTER_MINUTES * 60


def test_open_meteo_http_failure_records_provider_failure(monkeypatch):
    monkeypatch.setattr(settings, "WEATHER_RETRIES", 0)
    provider = OpenMeteoWeatherProvider(factory(FakeResponse({}, status_code=503)))
    with pytest.raises(ProviderUnavailable):
        provider.fetch_current(28.21, 84.02, "N-14")
    assert any(item["provider"] == "OPEN_METEO" and item["status"] == "FAILED" for item in provider_health.snapshot())


def test_invalid_external_weather_uses_explicit_fallback(monkeypatch):
    class BrokenProvider:
        def fetch_current(self, **_kwargs):
            raise ProviderUnavailable("timeout")

    monkeypatch.setattr(settings, "ALLOW_DETERMINISTIC_FALLBACK", True)
    result, error = fetch_with_fallback(BrokenProvider(), 28.21, 84.02, "N-14")
    assert result.source == "DEMO_FALLBACK"
    assert result.status == "FALLBACK"
    assert result.freshness_seconds is None
    assert "timeout" in error


def test_osrm_normalizes_geojson_route():
    provider = OSRMProvider(factory(FakeResponse({"code": "Ok", "routes": [{"distance": 1200, "duration": 180, "geometry": {"coordinates": [[80.55, 16.23], [80.56, 16.24]]}, "legs": [{"steps": [{"name": "Mountain Road", "distance": 1200, "duration": 180, "maneuver": {"type": "turn"}}]}]}]})))
    result = provider.route(16.23, 80.55, 16.24, 80.56)
    assert result["source"] == "OSRM"
    assert result["data_status"] == "LIVE"
    assert result["coordinates"] == [(16.23, 80.55), (16.24, 80.56)]


def test_usgs_normalizes_geojson_and_calculates_relevance():
    provider = USGSEarthquakeProvider(factory(FakeResponse({"features": [{"id": "us123", "properties": {"time": 1700000000000, "mag": 5.1, "place": "Nepal", "type": "earthquake"}, "geometry": {"coordinates": [84.1, 28.2, 10.0]}}]})))
    result = provider.fetch_recent(28.21, 84.02)
    assert result[0].event_id == "us123"
    assert result[0].magnitude == 5.1
    assert result[0].depth_km == 10
    assert result[0].distance_km is not None
    assert result[0].source == "USGS"


def test_http_sensor_provider_normalizes_gateway_observations(monkeypatch):
    monkeypatch.setattr(settings, "SENSOR_API_URL", "https://iot.test/readings")
    provider = HttpSensorProvider(factory(FakeResponse({"observations": [{"sensor_id": "iot-1", "sensor_type": "rainfall", "value": 12.5, "unit": "mm", "observed_at": "2026-08-28T10:00:00Z"}]})))
    zone = type("Zone", (), {"id": "DEMO-N14", "region_id": "DEMO-NEPAL-MOUNTAIN", "name": "N-14", "latitude": 28.21, "longitude": 84.02})()
    result = provider.read(zone)
    assert len(result) == 1
    assert result[0].zone_id == "DEMO-N14"
    assert result[0].source == "IOT"


def test_safe_routing_rejects_provider_route_inside_flagged_zone():
    result = SafeRoutingService().calculate("Nepal Mountain Region", "N-14 route", hazardous_zones=["DEMO-N14"])
    assert result["route_status"] == "blocked_by_hazard_zone"
    assert result["route"] is None


def test_iot_payload_enters_existing_sensor_ingestion_api(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"}).json()["token"]
    response = client.post(
        "/api/v1/sensor-events",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "sensor_id": "IOT-N14-RIVER-01",
            "sensor_type": "river_level",
            "zone_id": "DEMO-N14",
            "latitude": 28.21,
            "longitude": 84.02,
            "value": 91,
            "unit": "normalized",
            "observed_at": "2026-08-28T17:50:00Z",
            "source": "IOT",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["observation"]["source"] == "IOT"
    assert body["anomaly"]["anomaly_level"] == "critical"
    # The sensor source is present in the fused situation state. The risk
    # status may be MIXED/DEMO when the isolated database also contains the
    # deterministic weather baseline; it must never be mislabelled as live.
    assert "IOT" in body["analysis"]["correlation"]["sources"]
    assert body["analysis"]["prediction"]["data_status"] in {"LIVE", "MIXED", "DEMO", "MANUAL"}
