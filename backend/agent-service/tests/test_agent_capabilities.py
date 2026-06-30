from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_capabilities_agentic() -> None:
    res = client.get("/api/agent/capabilities")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["architecture"] == "mcp_agentic"
    assert "agent_run_stream" in data["features"]
    assert "agent_model" in data
    assert isinstance(data.get("hap_operations"), list)
    assert len(data.get("hap_operations") or []) > 0
