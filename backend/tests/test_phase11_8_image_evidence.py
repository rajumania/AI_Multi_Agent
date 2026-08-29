"""Focused Phase 11.8 tests for secure image evidence and fusion."""

from backend.config import settings
from backend.services.evidence_storage import get_evidence_storage
from backend.services.vision_provider import ImageEvidenceResult, analyze_image_reference


PNG = b"\x89PNG\r\n\x1a\nphase-11-8-test"


def _community_token(client):
    response = client.post(
        "/api/v1/auth/user/login",
        json={"email": "community@aitam.local", "phone": "9000000000"},
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _upload(client, token, content=PNG, filename="evidence.png", mime="image/png"):
    return client.post(
        "/api/v1/evidence/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (filename, content, mime)},
    )


def test_evidence_upload_is_authenticated_and_returns_opaque_reference(client):
    token = _community_token(client)
    assert client.post("/api/v1/evidence/upload", files={"file": ("x.png", PNG, "image/png")}).status_code == 401
    response = _upload(client, token)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "STORED"
    assert body["reference"].startswith("evidence:")
    assert "storage" not in body["reference"]
    assert "path" not in body
    evidence_id = body["evidence_id"]
    try:
        retrieved = client.get(f"/api/v1/evidence/{evidence_id}", headers={"Authorization": f"Bearer {token}"})
        assert retrieved.status_code == 200
        assert retrieved.content == PNG
    finally:
        get_evidence_storage().delete(evidence_id)


def test_evidence_upload_validates_type_and_size(client, monkeypatch):
    token = _community_token(client)
    assert _upload(client, token, filename="evidence.txt", mime="text/plain").status_code == 415
    assert _upload(client, token, content=b"not-an-image", filename="evidence.png", mime="image/png").status_code == 415
    monkeypatch.setattr(settings, "EVIDENCE_MAX_BYTES", 16)
    assert _upload(client, token, content=PNG + b"x" * 20).status_code == 413


def test_image_analysis_is_explicitly_unavailable_without_configured_provider(client):
    token = _community_token(client)
    response = _upload(client, token)
    assert response.status_code == 201
    evidence_id = response.json()["evidence_id"]
    try:
        result = analyze_image_reference(response.json()["reference"], "Water visible on the road")
        assert result["status"] == "IMAGE_ANALYSIS_UNAVAILABLE"
        assert result["supporting_only"] is True
        assert result["flood_evidence"] is False
    finally:
        get_evidence_storage().delete(evidence_id)


def test_mocked_vision_result_is_structured_supporting_evidence(client, monkeypatch):
    token = _community_token(client)
    response = _upload(client, token)
    assert response.status_code == 201
    evidence_id = response.json()["evidence_id"]

    class FakeVision:
        name = "TEST_VISION"

        def analyze(self, content, mime_type, description):
            assert content.startswith(b"\x89PNG")
            assert mime_type == "image/png"
            return ImageEvidenceResult(
                scene_description="Water is visibly pooling across a road.",
                possible_hazards=["waterlogging"],
                waterlogging=True,
                flood_evidence=True,
                confidence=0.82,
                limitations=["Image cannot establish geographic extent."],
            )

    monkeypatch.setattr("backend.services.vision_provider.get_vision_provider", lambda: FakeVision())
    try:
        result = analyze_image_reference(response.json()["reference"], "Water visible on the road")
        assert result["status"] == "LIVE"
        assert result["supporting_only"] is True
        assert result["flood_evidence"] is True
        assert result["confidence"] == 0.82
    finally:
        get_evidence_storage().delete(evidence_id)


def test_malformed_vision_response_never_becomes_live(client, monkeypatch):
    token = _community_token(client)
    response = _upload(client, token)
    assert response.status_code == 201
    evidence_id = response.json()["evidence_id"]

    class BrokenVision:
        name = "TEST_VISION"

        def analyze(self, content, mime_type, description):
            raise ValueError("MALFORMED_VISION_RESPONSE")

    monkeypatch.setattr("backend.services.vision_provider.get_vision_provider", lambda: BrokenVision())
    try:
        result = analyze_image_reference(response.json()["reference"], "Reported incident")
        assert result["status"] == "IMAGE_ANALYSIS_UNAVAILABLE"
        assert result["flood_evidence"] is False
    finally:
        get_evidence_storage().delete(evidence_id)


def test_image_fusion_adds_existing_risk_feature_and_targeting(monkeypatch):
    from datetime import datetime, timezone
    from backend.models.intelligence import IntelligencePreviewRequest
    from backend.services.intelligence_service import analyze_location

    now = datetime.now(timezone.utc)

    class Weather:
        source = "OPEN_METEO"
        status = "LIVE"
        timestamp = now
        received_at = now
        freshness_seconds = 0.0
        condition = "rain"
        rainfall_mm = 22.0
        rainfall_intensity = 8.0
        wind_speed_kph = 14.0
        wind_direction = 90.0
        pressure = 1008.0
        temperature_c = 27.0
        humidity = 90.0

    class WeatherProvider:
        def fetch_current(self, latitude, longitude, location):
            return Weather()

    class EnvironmentProvider:
        def fetch_for_zone(self, zone):
            return [{"indicator": "water_level_score", "value": 35, "source": "OPEN_METEO", "observed_at": now, "received_at": now}]

    class EmptyEarthquakes:
        def fetch_recent(self, *args, **kwargs):
            return []

    class EmptyWarnings:
        def fetch_alerts(self, *args, **kwargs):
            return []

    image = {"status": "LIVE", "provider": "TEST_VISION", "confidence": 0.82, "flood_evidence": True, "waterlogging": True, "supporting_only": True}
    monkeypatch.setattr("backend.services.intelligence_service.get_weather_provider", lambda: WeatherProvider())
    monkeypatch.setattr("backend.services.intelligence_service.get_environmental_provider", lambda: EnvironmentProvider())
    monkeypatch.setattr("backend.services.intelligence_service.USGSEarthquakeProvider", EmptyEarthquakes)
    monkeypatch.setattr("backend.services.intelligence_service.get_severe_weather_provider", lambda: EmptyWarnings())
    monkeypatch.setattr("backend.services.intelligence_service.analyze_image_reference", lambda reference, description: image)
    request = IntelligencePreviewRequest(description="Waterlogging reported on the road", location="Selected coordinates", latitude=18.56517, longitude=84.19587, disaster_type="other", image_url="evidence:" + "a" * 32)
    result = analyze_location(None, request)
    assert result["image_analysis"]["status"] == "LIVE"
    assert any(item["indicator"] == "image_evidence_score" for item in result["environmental"])
    assert {item["department"] for item in result["departments"]} >= {"SEARCH_AND_RESCUE", "MEDICAL", "TRANSPORT", "SHELTER"}
