"""Phase 2 deterministic risk, provider fallback and API contract tests."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.database.models import NotificationDB
from backend.models.incident import DisasterType, SeverityLevel
from backend.services.risk_engine import DeterministicRiskEngine, RiskFeatureEngine, RiskFeatures
from backend.services.weather_providers import DemoWeatherProvider, ProviderUnavailable, fetch_with_fallback


def operator_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def features(value: float, **extra) -> RiskFeatures:
    values = {"rainfall_score": value, "water_level_score": value, "elevation_vulnerability": value, "historical_risk": value, "community_signal": value, "drainage_vulnerability": value, "population_exposure": value, "weather_severity": value, "rainfall_intensity_score": value, "wind_severity": value, "pressure_severity": value, "coastal_vulnerability": value, "slope_vulnerability": value, "soil_moisture_score": value, "terrain_vulnerability": value, "temperature_severity": value, "humidity_severity": value, "heat_duration": value}
    values.update(extra)
    return RiskFeatures(values, set(values), source_count=3)


@pytest.mark.parametrize("score, level", [(10, SeverityLevel.LOW), (35, SeverityLevel.MEDIUM), (60, SeverityLevel.HIGH), (90, SeverityLevel.CRITICAL)])
def test_risk_levels_are_deterministic(score, level):
    result = DeterministicRiskEngine().score(DisasterType.FLOOD, features(score))
    assert result.score == score
    assert result.level == level


def test_feature_engine_handles_missing_data_and_stale_weather(db_session):
    zone = db_session.query(__import__("backend.database.models", fromlist=["ZoneDB"]).ZoneDB).filter_by(id="DEMO-ZONE-A").one()
    old = {"rainfall_mm": None, "condition": "unknown", "source": "EXTERNAL", "received_at": datetime.now(timezone.utc) - timedelta(hours=2)}
    result = RiskFeatureEngine().build(zone, old, [], [], datetime.now(timezone.utc))
    assert result.stale is True
    assert "rainfall_score" not in result.available
    assert 0 <= DeterministicRiskEngine().score("flood", result).confidence <= 100


@pytest.mark.parametrize("disaster", ["flood", "urban_flood", "cyclone", "landslide", "heatwave", "severe_weather"])
def test_all_supported_disasters_have_strategy(disaster):
    result = DeterministicRiskEngine().score(disaster, features(80))
    assert result.level == SeverityLevel.CRITICAL
    assert result.recommendations


def test_provider_demo_and_fallback(monkeypatch):
    demo = DemoWeatherProvider().fetch_current(16.2, 80.5, "Zone A")
    assert demo.source == "DEMO"

    class BrokenProvider:
        def fetch_current(self, *_args, **_kwargs):
            raise ProviderUnavailable("timeout")

    data, error = fetch_with_fallback(BrokenProvider(), 16.2, 80.5, "Zone A")
    assert data.source == "DEMO_FALLBACK"
    assert "timeout" in error


def test_demo_end_to_end_persists_prediction_and_deduplicates_alerts(client, db_session):
    headers = operator_headers(client)
    first = client.post("/api/v1/demo/scenarios/flood-critical", headers=headers)
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["risk_level"] == "critical"
    assert body["data_status"] == "DEMO"
    assert client.get(f"/api/v1/risk/{body['prediction_id']}").status_code == 200
    assert client.get("/api/v1/weather/history").status_code == 200
    second = client.post("/api/v1/demo/scenarios/flood-critical", headers=headers)
    assert second.status_code == 201
    count = db_session.query(NotificationDB).filter(NotificationDB.alert_type == "early_warning").count()
    assert count == 1


def test_invalid_observation_is_rejected(client):
    response = client.post("/api/v1/weather/ingest", headers=operator_headers(client), json={"zone_id": "DEMO-ZONE-A", "indicator": "not-used", "temperature_c": 999, "condition": "unknown"})
    assert response.status_code == 422
