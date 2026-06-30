"""Unit tests for OpenAI-compatible LLM streaming."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from config import settings
from services.agentic_llm import aggregate_stream_events
from services.agentic_llm_openai import OpenAIAgenticLlm


def _sse_lines(*payloads: dict) -> list[bytes]:
    lines: list[bytes] = []
    for payload in payloads:
        lines.append(f"data: {json.dumps(payload, ensure_ascii=False)}".encode())
    lines.append(b"data: [DONE]")
    return lines


def test_openai_stream_turn_yields_live_deltas() -> None:
    settings.agent_model_stream_enabled = True
    client = OpenAIAgenticLlm()
    stream_body = _sse_lines(
        {"choices": [{"delta": {"reasoning_content": "先分析"}}]},
        {"choices": [{"delta": {"reasoning_content": "用户需求"}}]},
        {"choices": [{"delta": {"content": "你好"}}]},
        {"choices": [{"delta": {"content": "，世界"}}]},
        {"choices": [{"finish_reason": "stop"}]},
    )

    mock_response = MagicMock()
    mock_response.iter_lines.return_value = iter(stream_body)
    mock_response.raise_for_status = MagicMock()

    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__enter__.return_value = mock_response
    mock_stream_ctx.__exit__.return_value = False

    mock_http = MagicMock()
    mock_http.stream.return_value = mock_stream_ctx
    mock_http.__enter__.return_value = mock_http
    mock_http.__exit__.return_value = False

    events = []
    with patch("services.agentic_llm_openai.httpx.Client", return_value=mock_http):
        events = list(
            client.stream_turn(
                messages=[{"role": "user", "content": "hi"}],
                tools=[],
                turn=1,
            )
        )

    kinds = [event.kind for event in events]
    assert kinds.count("reasoning_delta") == 2
    assert kinds.count("text_delta") == 2
    assert kinds[-1] == "turn_complete"
    final = events[-1].output
    assert final is not None
    assert final.reasoning_content == "先分析用户需求"
    assert final.content == "你好，世界"


def test_openai_stream_turn_parses_tool_calls() -> None:
    settings.agent_model_stream_enabled = True
    client = OpenAIAgenticLlm()
    stream_body = _sse_lines(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "tc_1",
                                "function": {"name": "platform_task_status", "arguments": '{"query":'},
                            }
                        ]
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {"index": 0, "function": {"arguments": '"health"}'}}
                        ]
                    }
                }
            ]
        },
        {"choices": [{"finish_reason": "tool_calls"}]},
    )

    mock_response = MagicMock()
    mock_response.iter_lines.return_value = iter(stream_body)
    mock_response.raise_for_status = MagicMock()
    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__enter__.return_value = mock_response
    mock_stream_ctx.__exit__.return_value = False
    mock_http = MagicMock()
    mock_http.stream.return_value = mock_stream_ctx
    mock_http.__enter__.return_value = mock_http
    mock_http.__exit__.return_value = False

    with patch("services.agentic_llm_openai.httpx.Client", return_value=mock_http):
        out = aggregate_stream_events(
            client.stream_turn(
                messages=[{"role": "user", "content": "查健康"}],
                tools=[{"type": "function", "function": {"name": "platform_task_status"}}],
                turn=1,
            )
        )

    assert len(out.tool_calls) == 1
    assert out.tool_calls[0].name == "platform_task_status"
    assert out.tool_calls[0].arguments == {"query": "health"}


def test_openai_complete_turn_aggregates_stream() -> None:
    settings.agent_model_stream_enabled = True
    client = OpenAIAgenticLlm()
    stream_body = _sse_lines(
        {"choices": [{"delta": {"content": "OK"}}]},
        {"choices": [{"finish_reason": "stop"}]},
    )
    mock_response = MagicMock()
    mock_response.iter_lines.return_value = iter(stream_body)
    mock_response.raise_for_status = MagicMock()
    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__enter__.return_value = mock_response
    mock_stream_ctx.__exit__.return_value = False
    mock_http = MagicMock()
    mock_http.stream.return_value = mock_stream_ctx
    mock_http.__enter__.return_value = mock_http
    mock_http.__exit__.return_value = False

    with patch("services.agentic_llm_openai.httpx.Client", return_value=mock_http):
        out = client.complete_turn(
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            turn=1,
        )
    assert out.content == "OK"
