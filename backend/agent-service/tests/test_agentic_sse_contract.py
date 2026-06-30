"""SSE event order contract for Agentic run/stream."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from main import app

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


def test_sse_run_start_first_and_run_done_last() -> None:
    res = client.post("/api/agent/run/stream", json={"message": "查询平台服务健康"})
    assert res.status_code == 200
    events = _parse_sse(res.text)
    assert events
    assert events[0][0] == "run_start"
    assert events[-1][0] == "run_done"
    run_start = events[0][1]
    assert run_start.get("run_id")
    assert run_start.get("trace_id")
    assert run_start.get("architecture") == "mcp_agentic"


def test_sse_tool_events_follow_assistant_deltas() -> None:
    res = client.post("/api/agent/run/stream", json={"message": "查询平台服务健康"})
    events = _parse_sse(res.text)
    names = [name for name, _ in events]
    run_idx = names.index("run_start")
    done_idx = names.index("run_done")
    tool_start_idx = names.index("tool_start")
    tool_result_idx = names.index("tool_result")
    assert run_idx < tool_start_idx < tool_result_idx < done_idx


def test_sse_reasoning_events_before_assistant_deltas() -> None:
    res = client.post("/api/agent/run/stream", json={"message": "查询平台服务健康"})
    events = _parse_sse(res.text)
    names = [name for name, _ in events]
    assert "reasoning_delta" in names
    assert "reasoning_message" in names
    first_reasoning = names.index("reasoning_delta")
    first_assistant = names.index("assistant_delta")
    assert first_reasoning < first_assistant
    reasoning_payload = next(data for event, data in events if event == "reasoning_message")
    assert str(reasoning_payload.get("content") or "").strip()
