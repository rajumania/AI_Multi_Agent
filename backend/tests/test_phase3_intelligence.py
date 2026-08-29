"""Phase 3 sensor, converging workflow, travel and monitoring tests."""

from backend.services.sensor_monitoring import SensorAnomalyDetector


def operator_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_sensor_anomaly_detector_detects_rising_conditions():
    detector = SensorAnomalyDetector()
    assert detector.detect("river_level", 88, 60)["anomaly_level"] == "critical"
    assert detector.detect("ground_movement", 50, 20)["anomaly_level"] == "high"
    assert detector.detect("rainfall", 20, 18) is None


def test_sensor_event_converges_into_risk_and_plan(client):
    headers = operator_headers(client)
    response = client.post("/api/v1/sensor-events", headers=headers, json={"sensor_id": "TEST-RIVER-01", "sensor_type": "river_level", "zone_id": "DEMO-ZONE-A", "value": 90, "unit": "normalized", "source": "DEMO_SIMULATION"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["anomaly"]["anomaly_level"] == "critical"
    assert body["analysis"]["prediction"]["risk_score"] >= 0
    assert body["analysis"]["approval_status"] == "pending"
    assert len(body["analysis"]["agent_results"]) >= 8
    trace = client.get(f"/api/v1/agent-runs/{body['analysis']['agent_run_id']}/trace", headers=headers)
    assert trace.status_code == 200
    assert len(trace.json()["trace"]) >= 8


def test_human_and_travel_paths_use_same_pipeline(client):
    headers = operator_headers(client)
    event = client.post("/api/v1/events", headers=headers, json={"event_source": "community", "disaster_type": "flood", "location": "Zone A (DEMO)", "zone_id": "DEMO-ZONE-A", "description": "Road flooded and people trapped; water entering houses.", "people_count": 4, "community_reports": 17})
    assert event.status_code == 201, event.text
    result = event.json()
    assert result["prediction"]["disaster_type"] == "flood"
    assert result["response_plan"]["approval_status"] == "pending"
    assert "rescue_priority" in result["agent_results"]
    travel = client.post("/api/v1/travel/safety-check", headers=headers, json={"destination": "Zone A (DEMO)"})
    assert travel.status_code == 200, travel.text
    assert travel.json()["recommendation"] in {"SAFE", "CAUTION", "NOT_RECOMMENDED"}


def test_nepal_demo_has_two_hazards_admin_alert_and_replan(client):
    headers = operator_headers(client)
    response = client.post("/api/v1/sensor-simulations", headers=headers, json={"scenario": "nepal_mountain"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data_status"] == "DEMO/SIMULATION"
    assert len(body["sensor_event_ids"]) >= 3
    analyses = {item["prediction"]["disaster_type"]: item for item in body["analyses"]}
    assert analyses["landslide"]["prediction"]["risk_score"] >= 75
    assert analyses["landslide"]["prediction"]["data_status"] == "DEMO"
    nearby = client.get("/api/v1/alerts/nearby?zone_id=DEMO-N14", headers=headers)
    assert nearby.status_code == 200
    assert any(item["audience"] == "community" for item in nearby.json())
    replan = client.post(f"/api/v1/monitoring/replan/{body['event_id']}", headers=headers)
    assert replan.status_code == 200, replan.text
    assert replan.json()["approval_status"] == "pending"
    travel = client.get("/api/v1/travel/safety-check?destination=DEMO-N14", headers=headers)
    assert travel.status_code == 200
    assert travel.json()["recommendation"] == "NOT_RECOMMENDED"


def test_departments_and_sensor_status_are_real_api_views(client):
    headers = operator_headers(client)
    departments = client.get("/api/v1/departments", headers=headers)
    assert departments.status_code == 200
    assert {item["id"] for item in departments.json()} >= {"SEARCH_AND_RESCUE", "WEATHER_ENVIRONMENT", "PUBLIC_INFORMATION"}
    status = client.get("/api/v1/sensors/status", headers=headers)
    assert status.status_code == 200
