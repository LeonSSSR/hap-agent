"""Agentic run cancellation when client disconnects or cancel_check fires."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from fastapi.testclient import TestClient

from main import app
from schemas.agentic import AgentRunRequest
from services.agentic_runner import AgenticRunner
from services.identity_service import AgentIdentity


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


def test_agent_run_stream_wires_disconnect_cancel_check() -> None:
    router_source = (
        Path(__file__).resolve().parents[1] / "routers" / "agent.py"
    ).read_text(encoding="utf-8")
    assert "disconnected = threading.Event()" in router_source
    assert "await http_request.is_disconnected()" in router_source
    assert "return disconnected.is_set()" in router_source
    assert "return False" not in router_source.split("def cancel_check")[1].split("def producer")[0]


def test_run_events_stops_on_cancel_check() -> None:
    cancelled = threading.Event()
    runner = AgenticRunner(tool_executor=lambda *args, **kwargs: {"ok": True})
    request = AgentRunRequest(message="查询平台服务健康")
    identity = AgentIdentity(username="tester", role="USER", permissions=set())

    events: list[tuple[str, dict]] = []

    def consume() -> None:
        for event, data in runner.run_events(
            request=request,
            identity=identity,
            cancel_check=cancelled.is_set,
        ):
            events.append((event, data))
            if event == "run_start":
                cancelled.set()

    thread = threading.Thread(target=consume)
    thread.start()
    thread.join(timeout=15.0)
    assert not thread.is_alive()
    assert events
    assert events[-1][0] == "run_done"
    assert events[-1][1].get("status") == "stopped"
