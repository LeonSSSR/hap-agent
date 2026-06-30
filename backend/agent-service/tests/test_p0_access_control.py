"""P0 access control: auth + per-user session/audit/memory isolation."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from config import settings
from main import app
from middleware.auth import require_agent_identity
from services.audit_store import AuditStore
from services.identity_service import AgentIdentity
from services.long_term_memory import LongTermMemoryStore


def _identity(username: str, *, role: str = "USER") -> AgentIdentity:
    return AgentIdentity(username=username, role=role, permissions=set())


class _IdentitySwitchingClient:
    def __init__(self) -> None:
        self._active_user = "dev-operator"
        self._client = TestClient(app)

        async def _override() -> AgentIdentity:
            return _identity(self._active_user)

        app.dependency_overrides[require_agent_identity] = _override

    def as_user(self, username: str) -> TestClient:
        self._active_user = username
        return self._client

    def close(self) -> None:
        app.dependency_overrides.pop(require_agent_identity, None)


@pytest.fixture
def auth_client() -> Iterator[_IdentitySwitchingClient]:
    wrapper = _IdentitySwitchingClient()
    try:
        yield wrapper
    finally:
        wrapper.close()


def test_sensitive_endpoints_require_identity_when_auth_required() -> None:
    original_required = settings.auth_required
    original_bypass = settings.auth_dev_bypass
    settings.auth_required = True
    settings.auth_dev_bypass = False
    app.dependency_overrides.pop(require_agent_identity, None)
    try:
        client = TestClient(app)
        for path in (
            "/api/agent/sessions",
            "/api/agent/memory/search?q=test",
            "/api/agent/audits",
        ):
            response = client.get(path)
            assert response.status_code == 401, path
    finally:
        settings.auth_required = original_required
        settings.auth_dev_bypass = original_bypass


def test_session_isolation_between_users(auth_client: _IdentitySwitchingClient) -> None:
    created = auth_client.as_user("alice").post("/api/agent/sessions")
    assert created.status_code == 200
    session_id = created.json()["sessionId"]

    assert auth_client.as_user("alice").get(f"/api/agent/sessions/{session_id}").status_code == 200
    assert auth_client.as_user("bob").get(f"/api/agent/sessions/{session_id}").status_code == 403
    assert (
        auth_client.as_user("bob").put(
            f"/api/agent/sessions/{session_id}",
            json={"turns": [{"userMessage": "hack", "assistantReply": "no"}]},
        ).status_code
        == 403
    )
    assert auth_client.as_user("bob").delete(f"/api/agent/sessions/{session_id}").status_code == 403


def test_list_sessions_only_returns_owner_items(auth_client: _IdentitySwitchingClient) -> None:
    alice_session = auth_client.as_user("alice").post("/api/agent/sessions").json()["sessionId"]
    bob_session = auth_client.as_user("bob").post("/api/agent/sessions").json()["sessionId"]

    alice_items = {
        item["sessionId"]
        for item in auth_client.as_user("alice").get("/api/agent/sessions").json()["data"]["items"]
    }
    bob_items = {
        item["sessionId"]
        for item in auth_client.as_user("bob").get("/api/agent/sessions").json()["data"]["items"]
    }

    assert alice_session in alice_items
    assert bob_session not in alice_items
    assert bob_session in bob_items
    assert alice_session not in bob_items


def test_memory_search_is_scoped_to_owner(tmp_path) -> None:
    memory = LongTermMemoryStore(base_path=str(tmp_path), search_limit=5)
    memory.index_turn(
        session_id="session-alice",
        user_input="alice 专属训练任务",
        assistant_reply="alice 回复",
        username="alice",
    )
    memory.index_turn(
        session_id="session-bob",
        user_input="bob 专属部署任务",
        assistant_reply="bob 回复",
        username="bob",
    )

    alice_hits = memory.search("alice 专属训练任务", username="alice")
    bob_hits = memory.search("bob 专属部署任务", username="bob")

    assert len(alice_hits) == 1
    assert "alice" in str(alice_hits[0].get("text") or "")
    assert len(bob_hits) == 1
    assert "bob" in str(bob_hits[0].get("text") or "")

    cross_hits = memory.search("alice 专属训练任务", username="bob")
    assert not any("alice 专属训练任务" in str(hit.get("text") or "") for hit in cross_hits)


def test_audit_list_and_trace_are_scoped_to_owner(tmp_path) -> None:
    audit = AuditStore(durable_path=None)
    audit.add(action="tool_execution", trace_id="trace-alice", task_id="t1", username="alice", summary="alice run")
    audit.add(action="tool_execution", trace_id="trace-bob", task_id="t2", username="bob", summary="bob run")

    alice_items = audit.list(username="alice")
    bob_items = audit.list(username="bob")

    assert len(alice_items) == 1
    assert alice_items[0]["username"] == "alice"
    assert len(bob_items) == 1
    assert bob_items[0]["username"] == "bob"
    assert len(audit.list_by_trace_id("trace-alice", username="alice")) == 1
    assert audit.list_by_trace_id("trace-alice", username="bob") == []


def test_audit_api_denies_cross_user_trace(auth_client: _IdentitySwitchingClient) -> None:
    from services.audit_store import audit_store

    audit_store.add(
        action="agentic_run_started",
        trace_id="trace-cross-user",
        task_id="task-1",
        username="alice",
        summary="alice trace",
    )

    assert auth_client.as_user("alice").get("/api/agent/audits/trace/trace-cross-user").status_code == 200
    assert auth_client.as_user("bob").get("/api/agent/audits/trace/trace-cross-user").status_code == 403


def test_run_stream_rejects_foreign_session(auth_client: _IdentitySwitchingClient) -> None:
    session_id = auth_client.as_user("alice").post("/api/agent/sessions").json()["sessionId"]
    response = auth_client.as_user("bob").post(
        "/api/agent/run/stream",
        json={"message": "你好", "session_id": session_id},
    )
    assert response.status_code == 403
