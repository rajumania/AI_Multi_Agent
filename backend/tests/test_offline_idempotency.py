"""Contract tests for reconnect-safe incident submission."""


def test_replaying_same_client_operation_returns_original_incident(client):
    payload = {
        "description": "Offline report replay contract test",
        "incident_type": "medical",
        "location": "NTR Central Library",
        "severity": "high",
        "injured_count": None,
    }
    headers = {"X-Client-Operation-Id": "offline-test-operation-001"}
    first = client.post("/api/v1/incidents", json=payload, headers=headers)
    second = client.post("/api/v1/incidents", json=payload, headers=headers)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json()["incident_id"] == first.json()["incident_id"]
    assert second.json()["client_operation_id"] == headers["X-Client-Operation-Id"]
