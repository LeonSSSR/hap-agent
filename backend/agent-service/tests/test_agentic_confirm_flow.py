"""High-risk tool confirm_required + POST /run/{id}/confirm resume."""

from __future__ import annotations

import json
from typing import Literal

import pytest

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


@pytest.fixture
def auto_confirm_decision():
    original = run_store_module.run_store.register_confirm_wait

    def _patched(
        run_id: str,
        tool_call_id: str,
        resume_token: str,
        *,
        decision: Literal["approve", "reject"] = "approve",
    ) -> None:
        original(run_id, tool_call_id, resume_token)
        run_store_module.run_store.set_confirm_decision(
            run_id,
            resume_token,
            decision=decision,
            approved_by="pytest",
        )

    return _patched


def test_confirm_flow_approve_and_complete(auto_confirm_decision, monkeypatch) -> None:
    monkeypatch.setattr(
        run_store_module.run_store,
        "register_confirm_wait",
        lambda run_id, tool_call_id, resume_token: auto_confirm_decision(
            run_id, tool_call_id, resume_token, decision="approve"
        ),
    )
    res = client.post(
        "/api/agent/run/stream",
        json={"message": "高风险审批操作", "options": {"confirm_high_risk": True}},
    )
    assert res.status_code == 200
    events = _parse_sse(res.text)
    assert any(name == "confirm_required" for name, _ in events)
    confirm_idx = next(i for i, (n, _) in enumerate(events) if n == "confirm_required")
    tool_start_idx = next(i for i, (n, _) in enumerate(events) if n == "tool_start")
    assert confirm_idx < tool_start_idx
    assert events[-1][0] == "run_done"
    assert events[-1][1]["status"] == "completed"
    confirm_tool = next(d.get("tool_name") for n, d in events if n == "confirm_required")
    assert any(name == "tool_result" and d.get("tool_name") == confirm_tool for name, d in events)


def test_page_confirm_flow_before_page_action(auto_confirm_decision, monkeypatch) -> None:
    original_page_wait = run_store_module.run_store.register_page_wait

    def _auto_page_result(run_id: str, tool_call_id: str, **kwargs: object) -> None:
        original_page_wait(run_id, tool_call_id, **kwargs)
        run_store_module.run_store.set_page_result(
            run_id,
            tool_call_id,
            {
                "success": True,
                "message": "opened",
                "ui_action_id": str(kwargs.get("ui_action_id") or "ml.publish.confirm"),
            },
        )

    monkeypatch.setattr(
        run_store_module.run_store,
        "register_confirm_wait",
        lambda run_id, tool_call_id, resume_token: auto_confirm_decision(
            run_id, tool_call_id, resume_token, decision="approve"
        ),
    )
    monkeypatch.setattr(run_store_module.run_store, "register_page_wait", _auto_page_result)
    res = client.post(
        "/api/agent/run/stream",
        json={"message": "打开模型发布页面", "options": {"confirm_high_risk": True}},
    )
    assert res.status_code == 200
    events = _parse_sse(res.text)
    confirm_events = [d for n, d in events if n == "confirm_required"]
    assert confirm_events
    assert confirm_events[0].get("ui_action_id") == "ml.publish.confirm"
    confirm_idx = next(i for i, (n, _) in enumerate(events) if n == "confirm_required")
    page_idx = next(i for i, (n, _) in enumerate(events) if n == "page_action")
    assert confirm_idx < page_idx
    assert events[-1][1]["status"] == "completed"


def test_confirm_flow_reject_blocks_tool(auto_confirm_decision, monkeypatch) -> None:
    monkeypatch.setattr(
        run_store_module.run_store,
        "register_confirm_wait",
        lambda run_id, tool_call_id, resume_token: auto_confirm_decision(
            run_id, tool_call_id, resume_token, decision="reject"
        ),
    )
    res = client.post(
        "/api/agent/run/stream",
        json={"message": "高风险审批操作", "options": {"confirm_high_risk": True}},
    )
    assert res.status_code == 200
    events = _parse_sse(res.text)
    confirm_tool = next((d.get("tool_name") for n, d in events if n == "confirm_required"), None)
    blocked = [d for n, d in events if n == "tool_blocked" and d.get("tool_name") == confirm_tool]
    assert blocked
    assert blocked[0].get("blocked_reason") == "approval_required"
    assert events[-1][0] == "run_done"
