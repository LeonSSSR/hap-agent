"""Agentic run/stream SSE contract."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from main import app
from services import run_store as run_store_module

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


def test_run_stream_mcp_health_query() -> None:
    res = client.post("/api/agent/run/stream", json={"message": "查询平台服务健康"})
    assert res.status_code == 200
    events = _parse_sse(res.text)
    assert events[0][0] == "run_start"
    assert events[-1][0] == "run_done"
    assert events[-1][1]["status"] == "completed"
    assert any(name == "tool_result" for name, _ in events)


def test_run_stream_hap_ui_action_with_page_result(monkeypatch) -> None:
    original = run_store_module.run_store.register_page_wait

    def _auto_page_result(run_id: str, tool_call_id: str, **kwargs: object) -> None:
        original(run_id, tool_call_id, **kwargs)
        run_store_module.run_store.set_page_result(
            run_id,
            tool_call_id,
            {
                "success": True,
                "message": "opened",
                "ui_action_id": "dg.sources",
            },
        )

    monkeypatch.setattr(run_store_module.run_store, "register_page_wait", _auto_page_result)
    res = client.post("/api/agent/run/stream", json={"message": "打开数据源管理页面"})
    assert res.status_code == 200
    events = _parse_sse(res.text)
    assert any(name == "page_action" for name, _ in events)
    tool_results = [d for n, d in events if n == "tool_result" and d.get("tool_name") == "hap_op_dg_sources"]
    assert tool_results
    assert tool_results[0]["status"] == "ok"
