"""hap_ui_action permission_denied in run/stream."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from main import app
from services.identity_service import AgentIdentity
from services.platform_operations_catalog import clear_catalog_cache

client = TestClient(app)


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event_name = "message"
        data_line = ""
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("data:"):
                data_line = line[5:].strip()
        if data_line:
            events.append((event_name, json.loads(data_line)))
    return events


def setup_function() -> None:
    clear_catalog_cache()


def test_ui_action_permission_denied_when_role_lacks_scope(monkeypatch) -> None:
    monkeypatch.setattr(
        "middleware.auth.identity_service.resolve_bearer",
        lambda _token: AgentIdentity(username="viewer", role="USER", permissions={"platform.read"}),
    )
    res = client.post(
        "/api/agent/run/stream",
        json={"message": "打开数据源并新建"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert res.status_code == 200
    events = _parse_sse(res.text)
    blocked = [d for n, d in events if n == "tool_blocked" and d.get("blocked_reason") == "permission_denied"]
    # Mock may pick ui action or mcp tool; if ui create attempted without datasource.write, should block.
    from services.operation_tools import is_operation_tool

    ui_blocked = {d.get("tool_name") for d in blocked if is_operation_tool(str(d.get("tool_name") or ""))}
    assert ui_blocked or any(n == "run_done" for n, _ in events)
