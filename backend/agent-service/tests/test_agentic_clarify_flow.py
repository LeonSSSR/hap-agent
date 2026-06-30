"""User clarification pause/resume during Agentic run/stream."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from main import app
from services import run_store as run_store_module
from services.agentic_llm import AgenticTurnOutput, MockAgenticLlm, ToolCallSpec

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
def auto_clarify_answer():
    original = run_store_module.run_store.register_clarify_wait

    def _patched(
        run_id: str,
        tool_call_id: str,
        resume_token: str,
        *,
        answer: str = "补充信息已收到",
    ) -> None:
        original(run_id, tool_call_id, resume_token)
        run_store_module.run_store.set_clarify_answer(
            run_id,
            resume_token,
            answer=answer,
            skipped=False,
        )

    return _patched


def test_clarify_gate_resume_completes(auto_clarify_answer, monkeypatch) -> None:
    original_complete = MockAgenticLlm.complete_turn

    def _clarify_then_default(self, *, messages, tools, turn):
        if turn == 1:
            return AgenticTurnOutput(
                text_deltas=["需要您补充信息", "…"],
                content="继续前需要您补充信息。",
                tool_calls=[
                    ToolCallSpec(
                        id=f"tc_{uuid4().hex[:12]}",
                        name="hap_request_clarification",
                        arguments={
                            "question": "请提供继续操作所需的信息：",
                            "fields": ["detail"],
                            "placeholder": "例如：名称 测试38",
                        },
                    )
                ],
            )
        return original_complete(self, messages=messages, tools=tools, turn=turn)

    monkeypatch.setattr(MockAgenticLlm, "complete_turn", _clarify_then_default)
    monkeypatch.setattr(
        run_store_module.run_store,
        "register_clarify_wait",
        lambda run_id, tool_call_id, resume_token: auto_clarify_answer(
            run_id,
            tool_call_id,
            resume_token,
            answer="名称：测试38",
        ),
    )

    res = client.post(
        "/api/agent/run/stream",
        json={"message": "帮我完成一项需要补充信息的操作"},
    )
    assert res.status_code == 200
    events = _parse_sse(res.text)
    names = [name for name, _ in events]
    assert "clarification_required" in names
    clarify = next(data for name, data in events if name == "clarification_required")
    assert str(clarify.get("question") or "").strip()
    tool_start_idx = next(
        i
        for i, (n, d) in enumerate(events)
        if n == "tool_start" and d.get("tool_name") == "hap_request_clarification"
    )
    clarify_idx = names.index("clarification_required")
    tool_result_idx = next(
        i
        for i, (n, d) in enumerate(events)
        if n == "tool_result" and d.get("tool_name") == "hap_request_clarification"
    )
    assert tool_start_idx < clarify_idx < tool_result_idx
    assert events[-1][0] == "run_done"
    assert events[-1][1]["status"] == "completed"
