"""Phase 4 consolidated map-data and GeoJSON contract tests."""


def operator_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_map_overview_contains_backend_nepal_state(client):
    headers = operator_headers(client)
    demo = client.post("/api/v1/sensor-simulations", headers=headers, json={"scenario": "nepal_mountain"})
    assert demo.status_code == 200, demo.text
    response = client.get("/api/v1/map/overview", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data_status"] == "DEMO/SIMULATION"
    assert any(item["zone_id"] == "DEMO-N14" and item["risk_level"] in {"high", "critical"} for item in body["risks"])
    assert any(item["id"] == "DEMO-N14" and item["geometry"]["type"] == "Polygon" for item in body["zones"])
    assert any(item["sensor_id"].startswith("DEMO-N14") for item in body["sensors"])
    assert {item["status"] for item in body["routes"]} >= {"active", "blocked"}
    assert any(item["id"] == "DEMO-N14-SHELTER-01" for item in body["resources"])


def test_map_filters_are_applied_by_backend(client):
    headers = operator_headers(client)
    client.post("/api/v1/sensor-simulations", headers=headers, json={"scenario": "nepal_mountain"})
    response = client.get("/api/v1/map/overview?zone_id=DEMO-N14&risk_level=critical", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert all(item["zone_id"] == "DEMO-N14" for item in body["risks"])
    assert all(item["id"].startswith("DEMO-N14") for item in body["zones"])


def test_map_layer_endpoint_returns_consolidated_layer(client):
    response = client.get("/api/v1/map/zones")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert all(item.get("geometry", {}).get("type") == "Polygon" for item in body["items"] if item.get("geometry"))

