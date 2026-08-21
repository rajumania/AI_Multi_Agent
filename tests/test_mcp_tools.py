import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.mcp.server import mcp_server
from backend.mcp.tools import (
    find_available_ambulances,
    find_security_units,
    find_first_aid_units,
    find_nearby_shelters,
    find_available_campus_vehicles,
    find_facility_resources,
    find_nearby_resources,
)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_find_available_ambulances():
    """Verify MCP ambulance lookup returns real available seeded ambulances."""
    ambulances = find_available_ambulances(location="CSE Block", limit=5)
    assert len(ambulances) >= 2
    res_ids = [a["resource_id"] for a in ambulances]
    assert "AMB-001" in res_ids
    assert "AMB-002" in res_ids
    assert all(a["availability_status"] == "available" for a in ambulances)


def test_find_security_units_filters_busy():
    """Verify MCP security lookup returns available units and excludes busy ones."""
    units = find_security_units(location="Main Entrance", limit=5)
    assert len(units) >= 2
    res_ids = [u["resource_id"] for u in units]
    assert "SEC-001" in res_ids
    assert "SEC-002" in res_ids
    # SEC-003 is seeded as 'busy', so it MUST NOT be returned in available list!
    assert "SEC-003" not in res_ids


def test_find_first_aid_units():
    """Verify MCP first aid units lookup."""
    units = find_first_aid_units(location="Sports Complex", limit=5)
    assert len(units) >= 2
    res_ids = [u["resource_id"] for u in units]
    assert "MED-001" in res_ids
    assert "MED-002" in res_ids


def test_find_nearby_shelters():
    """Verify MCP shelters lookup."""
    shelters = find_nearby_shelters(location="Auditorium Complex", min_capacity=500)
    assert len(shelters) >= 2
    res_ids = [s["resource_id"] for s in shelters]
    assert "SHELTER-001" in res_ids
    assert "SHELTER-002" in res_ids


def test_find_available_campus_vehicles():
    """Verify MCP campus vehicles lookup."""
    vehicles = find_available_campus_vehicles(location="Central Parking", limit=5)
    assert len(vehicles) >= 2
    res_ids = [v["resource_id"] for v in vehicles]
    assert "VEH-001" in res_ids
    assert "VEH-002" in res_ids


def test_find_facility_resources():
    """Verify MCP facility and fire equipment lookup."""
    fac = find_facility_resources(location="Engineering Hub", limit=5)
    assert len(fac) >= 2
    res_ids = [f["resource_id"] for f in fac]
    assert "FAC-001" in res_ids
    assert "FIRE-001" in res_ids


def test_mcp_server_dispatch():
    """Verify MCPServer tool registry and execution dispatcher."""
    tools = mcp_server.list_tools()
    assert len(tools) >= 7
    tool_names = [t["name"] for t in tools]
    assert "find_available_ambulances" in tool_names
    assert "find_security_units" in tool_names

    res = mcp_server.call_tool("find_available_ambulances", {"location": "CSE Block", "limit": 1})
    assert len(res) == 1
    assert res[0]["resource_type"] == "ambulance"


def test_api_list_resources(client):
    """Test GET /api/v1/resources endpoint."""
    response = client.get("/api/v1/resources")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 12


def test_api_search_available_resources(client):
    """Test GET /api/v1/resources/search/available location-aware search."""
    response = client.get("/api/v1/resources/search/available?type=ambulance&location=CSE")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    assert data[0]["resource_type"] == "ambulance"


def test_mcp_langgraph_integration(client):
    """Test that LangGraph multi-agent orchestration returns real MCP discovered resources."""
    create_payload = {
        "description": "Chemical smoke spill near Science Lab corridor. Precautionary check needed.",
        "location": "Science Hub",
        "incident_type": "fire",
        "severity": "high",
        "injured_count": None
    }
    create_res = client.post("/api/v1/incidents", json=create_payload)
    inc_id = create_res.json()["incident_id"]

    orch_res = client.post(f"/api/v1/incidents/{inc_id}/orchestrate")
    assert orch_res.status_code == 200
    data = orch_res.json()

    # Must contain real factual MCP resources discovered from SQLite
    assert "mcp_resources" in data
    assert len(data["mcp_resources"]) >= 2
    resource_ids = [r["resource_id"] for r in data["mcp_resources"]]
    # Should include security and ambulance/medical units
    assert any(r.startswith("SEC-") for r in resource_ids)
    assert any(r.startswith("AMB-") or r.startswith("MED-") for r in resource_ids)
