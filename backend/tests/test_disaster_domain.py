"""Phase 1 contract tests for the additive disaster domain."""


def test_demo_geography_and_resource_aliases_are_available(client):
    regions = client.get("/api/v1/regions")
    zones = client.get("/api/v1/zones?region_id=DEMO-REGION-01")
    shelters = client.get("/api/v1/shelters")
    hospitals = client.get("/api/v1/hospitals")
    services = client.get("/api/v1/emergency-services")

    assert regions.status_code == 200
    assert regions.json()[0]["is_demo"] is True
    assert zones.status_code == 200
    assert len(zones.json()) >= 2
    assert shelters.status_code == 200
    assert any(item["resource_id"] == "DEMO-SHELTER-01" for item in shelters.json())
    assert hospitals.status_code == 200
    assert hospitals.json()[0]["emergency_beds"] == 40
    assert services.status_code == 200


def test_disaster_event_alias_preserves_incident_contract(client):
    response = client.post(
        "/api/v1/disasters?region_id=DEMO-REGION-01&zone_id=DEMO-ZONE-A",
        json={
            "description": "DEMO flood observation for contract testing",
            "incident_type": "weather",
            "disaster_type": "flood",
            "location": "Demo Riverside Community",
            "severity": "medium",
        },
    )
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["disaster_type"] == "flood"
    assert record["region_id"] == "DEMO-REGION-01"
    listed = client.get("/api/v1/disasters?disaster_type=flood")
    assert listed.status_code == 200
    assert any(item["incident_id"] == record["incident_id"] for item in listed.json())


def test_rescue_request_contract_does_not_invent_priority(client):
    response = client.post(
        "/api/v1/rescue-requests",
        json={
            "location": "Demo Zone A",
            "people_count": 5,
            "injured_count": 1,
            "children_count": 2,
            "elderly_count": 1,
            "medical_emergency": True,
            "hazard_level": "high",
            "description": "DEMO request for Phase 1 contract testing",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "reported"
    assert response.json()["priority_score"] is None


def test_prediction_storage_is_read_only_until_phase_two(client):
    response = client.get("/api/v1/risk-predictions")
    assert response.status_code == 200
    assert response.json() == []
