"""Focused Phase 11.7 tests for real-provider boundaries and exact locations."""

from datetime import datetime, timezone

from backend.models.intelligence import IntelligencePreviewRequest
from backend.services.earthquake_providers import USGSEarthquakeProvider
from backend.services.intelligence_service import analyze_location
from backend.services.severe_weather_providers import IMDCAPProvider


def test_usgs_query_is_configurable_and_normalized():
    provider = USGSEarthquakeProvider()
    captured = {}
    provider._request = lambda params: captured.update(params) or {"features": [{"id": "eq-1", "properties": {"time": 1710000000000, "mag": 5.2, "place": "Test"}, "geometry": {"coordinates": [84.2, 18.57, 12]}}]}
    events = provider.fetch_recent(18.56517, 84.19587, radius_km=42, lookback_hours=6, min_magnitude=4.8)
    assert captured["maxradiuskm"] == 42
    assert captured["minmagnitude"] == 4.8
    assert events[0].event_id == "eq-1"
    assert events[0].distance_km is not None
    assert events[0].status in {"LIVE", "STALE"}


def test_imd_cap_alert_requires_geometry_for_exact_matching(monkeypatch):
    feed = b"""<rss><channel><item><guid>imd-1</guid><title>Heavy rain warning</title><circle>18.565,84.196 100</circle><info><headline>Heavy rain warning</headline><event>Rain</event><severity>Severe</severity><sent>2026-08-29T00:00:00Z</sent><expires>2099-08-29T00:00:00Z</expires><areadesc>Tekkali</areadesc></info></item></channel></rss>"""

    class Response:
        status_code = 200
        content = feed

        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr("backend.services.severe_weather_providers.settings.SEVERE_WEATHER_RADIUS_KM", 150.0)
    alerts = IMDCAPProvider(client_factory=Client).fetch_alerts(18.56517, 84.19587)
    assert alerts and alerts[0].alert_id == "imd-1"
    assert alerts[0].source == "IMD_CAP"
    assert alerts[0].distance_km is not None


def test_preview_fuses_exact_coordinates_without_persisting(monkeypatch):
    now = datetime.now(timezone.utc)

    class Weather:
        source = "OPEN_METEO"
        status = "LIVE"
        timestamp = now
        received_at = now
        freshness_seconds = 0.0
        condition = "clear"
        rainfall_mm = 0.0
        rainfall_intensity = 0.0
        wind_speed_kph = 8.0
        wind_direction = 90.0
        pressure = 1013.0
        temperature_c = 28.0
        humidity = 55.0

    class WeatherProvider:
        def fetch_current(self, latitude, longitude, location):
            assert (latitude, longitude) == (27.9881, 86.9250)
            return Weather()

    class EnvironmentProvider:
        def fetch_for_zone(self, zone):
            return [{"indicator": "water_level_score", "value": 2, "source": "OPEN_METEO", "observed_at": now, "received_at": now}]

    class Earthquakes:
        def fetch_recent(self, *args, **kwargs):
            return []

    class Severe:
        def fetch_alerts(self, *args, **kwargs):
            return []

    monkeypatch.setattr("backend.services.intelligence_service.get_weather_provider", lambda: WeatherProvider())
    monkeypatch.setattr("backend.services.intelligence_service.get_environmental_provider", lambda: EnvironmentProvider())
    monkeypatch.setattr("backend.services.intelligence_service.USGSEarthquakeProvider", Earthquakes)
    monkeypatch.setattr("backend.services.intelligence_service.get_severe_weather_provider", lambda: Severe())
    request = IntelligencePreviewRequest(description="Road conditions reported", location="Selected Himalayan point", latitude=27.9881, longitude=86.9250, disaster_type="other", image_url="photo_reference:test.jpg")
    result = analyze_location(None, request)
    assert (result["latitude"], result["longitude"]) == (27.9881, 86.9250)
    assert result["earthquake_status"] == "NO_QUALIFYING_EVENT"
    assert result["severe_weather_status"] == "NO_ACTIVE_WARNING"
    assert result["image_analysis"]["status"] == "IMAGE_ANALYSIS_UNAVAILABLE"
    assert result["risk"]["data_status"] == "LIVE"
