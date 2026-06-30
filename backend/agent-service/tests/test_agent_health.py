from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_agentic() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["architecture"] == "mcp_agentic"
    assert body["agent_model"]["provider"] == "mock"
