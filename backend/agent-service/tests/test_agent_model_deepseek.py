"""DeepSeek / OpenAI-compatible LLM integration (requires AGENT_MODEL_API_KEY)."""

from __future__ import annotations

import os

import pytest

from config import settings
from services.agentic_llm_openai import OpenAIAgenticLlm


def _api_key() -> str | None:
    key = (os.getenv("AGENT_MODEL_API_KEY") or settings.agent_model_api_key or "").strip()
    return key or None


@pytest.mark.live
@pytest.mark.skipif(_api_key() is None, reason="AGENT_MODEL_API_KEY not set")
def test_deepseek_single_turn_text() -> None:
    settings.agent_model_provider = "openai_compatible"
    settings.agent_model_api_key = _api_key()
    settings.agent_model_base_url = os.getenv(
        "AGENT_MODEL_BASE_URL", "https://api.deepseek.com"
    )
    settings.agent_model_name = os.getenv("AGENT_MODEL_NAME", "deepseek-v4-pro")
    client = OpenAIAgenticLlm()
    out = client.complete_turn(
        messages=[
            {"role": "system", "content": "你是助手，用一句话中文回复。"},
            {"role": "user", "content": "说 hello"},
        ],
        tools=[],
        turn=1,
    )
    text = out.content or "".join(out.text_deltas)
    assert len(text.strip()) > 0


@pytest.mark.live
@pytest.mark.skipif(_api_key() is None, reason="AGENT_MODEL_API_KEY not set")
def test_deepseek_thinking_returns_reasoning_content() -> None:
    settings.agent_model_provider = "openai_compatible"
    settings.agent_model_api_key = _api_key()
    settings.agent_model_base_url = os.getenv(
        "AGENT_MODEL_BASE_URL", "https://api.deepseek.com"
    )
    settings.agent_model_name = os.getenv("AGENT_MODEL_NAME", "deepseek-v4-pro")
    settings.agent_model_thinking_enabled = True
    client = OpenAIAgenticLlm()
    out = client.complete_turn(
        messages=[
            {"role": "system", "content": "你是助手，用一句话中文回复。"},
            {"role": "user", "content": "9.11 和 9.8 哪个更大？只回答结论。"},
        ],
        tools=[],
        turn=1,
    )
    assert len((out.reasoning_content or "").strip()) > 0
    assert len((out.content or "").strip()) > 0


@pytest.mark.live
@pytest.mark.skipif(_api_key() is None, reason="AGENT_MODEL_API_KEY not set")
def test_live_run_stream_health_query() -> None:
    from fastapi.testclient import TestClient

    from main import app

    settings.agent_model_provider = "openai_compatible"
    settings.agent_model_api_key = _api_key()
    client = TestClient(app)
    res = client.post("/api/agent/run/stream", json={"message": "用一句话说明平台服务健康查询结果"})
    assert res.status_code == 200
    assert "run_done" in res.text
