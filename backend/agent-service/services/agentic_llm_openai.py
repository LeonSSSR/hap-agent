"""OpenAI-compatible multi-turn tool client for Agentic runner."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import httpx

from config import settings
from services.agentic_llm import (
    AgenticLlmClient,
    AgenticTurnOutput,
    LLMClientError,
    LlmStreamEvent,
    ToolCallSpec,
    aggregate_stream_events,
    emit_turn_chunks,
)


class OpenAIAgenticLlm(AgenticLlmClient):
    def __init__(self) -> None:
        self._base = settings.agent_model_base_url.rstrip("/")
        self._api_key = settings.agent_model_api_key or ""
        self._model = settings.agent_model_name
        self._timeout = settings.agent_model_timeout_seconds

    def _build_payload(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        stream: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": settings.agent_model_max_tokens,
        }
        if stream:
            payload["stream"] = True
        if settings.agent_model_thinking_enabled:
            payload["thinking"] = {"type": "enabled"}
            payload["reasoning_effort"] = settings.agent_model_reasoning_effort
        else:
            payload["temperature"] = settings.agent_model_temperature
        if tools and settings.agent_model_use_tools:
            payload["tools"] = tools
        return payload

    def complete_turn(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        turn: int,
    ) -> AgenticTurnOutput:
        return aggregate_stream_events(
            self.stream_turn(messages=messages, tools=tools, turn=turn)
        )

    def stream_turn(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        turn: int,
    ) -> Iterator[LlmStreamEvent]:
        if not settings.agent_model_stream_enabled:
            yield from emit_turn_chunks(self._complete_turn_blocking(messages=messages, tools=tools))
            return
        try:
            yield from self._stream_turn_http(messages=messages, tools=tools)
        except LLMClientError:
            yield from emit_turn_chunks(self._complete_turn_blocking(messages=messages, tools=tools))

    def _stream_turn_http(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Iterator[LlmStreamEvent]:
        payload = self._build_payload(messages=messages, tools=tools, stream=True)
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        content = ""
        reasoning = ""
        tool_acc: dict[int, dict[str, str]] = {}

        try:
            with httpx.Client(timeout=self._timeout) as client:
                with client.stream(
                    "POST",
                    f"{self._base}/chat/completions",
                    json=payload,
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    for raw_line in response.iter_lines():
                        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else str(raw_line)
                        line = line.strip()
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices")
                        if not isinstance(choices, list) or not choices:
                            continue
                        choice = choices[0] if isinstance(choices[0], dict) else {}
                        delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
                        if not delta:
                            continue

                        reasoning_delta = str(delta.get("reasoning_content") or "")
                        if reasoning_delta:
                            reasoning += reasoning_delta
                            yield LlmStreamEvent(kind="reasoning_delta", delta=reasoning_delta)

                        text_delta = str(delta.get("content") or "")
                        if text_delta:
                            content += text_delta
                            yield LlmStreamEvent(kind="text_delta", delta=text_delta)

                        tool_calls_raw = delta.get("tool_calls")
                        if isinstance(tool_calls_raw, list):
                            for raw in tool_calls_raw:
                                if not isinstance(raw, dict):
                                    continue
                                index = int(raw.get("index") or 0)
                                slot = tool_acc.setdefault(
                                    index,
                                    {"id": "", "name": "", "arguments": ""},
                                )
                                if raw.get("id"):
                                    slot["id"] = str(raw["id"])
                                fn = raw.get("function") if isinstance(raw.get("function"), dict) else {}
                                if fn.get("name"):
                                    slot["name"] += str(fn["name"])
                                if fn.get("arguments"):
                                    slot["arguments"] += str(fn["arguments"])
        except httpx.HTTPError as exc:
            raise LLMClientError(f"agent model HTTP error: {exc}") from exc

        tool_calls = _parse_tool_call_specs(tool_acc)
        yield LlmStreamEvent(
            kind="turn_complete",
            output=AgenticTurnOutput(
                content=content.strip(),
                reasoning_content=reasoning.strip(),
                tool_calls=tool_calls,
            ),
        )

    def _complete_turn_blocking(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AgenticTurnOutput:
        payload = self._build_payload(messages=messages, tools=tools, stream=False)
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(f"{self._base}/chat/completions", json=payload, headers=headers)
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            raise LLMClientError(f"agent model HTTP error: {exc}") from exc

        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMClientError("agent model returned no choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else {}
        if not isinstance(message, dict):
            raise LLMClientError("invalid message in agent model response")

        content = str(message.get("content") or "").strip()
        reasoning_content = str(message.get("reasoning_content") or "").strip()
        tool_calls_raw = message.get("tool_calls")
        tool_calls: list[ToolCallSpec] = []
        if isinstance(tool_calls_raw, list):
            acc: dict[int, dict[str, str]] = {}
            for idx, raw in enumerate(tool_calls_raw):
                if not isinstance(raw, dict):
                    continue
                fn = raw.get("function") if isinstance(raw.get("function"), dict) else {}
                acc[idx] = {
                    "id": str(raw.get("id") or ""),
                    "name": str(fn.get("name") or ""),
                    "arguments": str(fn.get("arguments") or "{}"),
                }
            tool_calls = _parse_tool_call_specs(acc)

        return AgenticTurnOutput(
            content=content,
            reasoning_content=reasoning_content,
            tool_calls=tool_calls,
        )


def _parse_tool_call_specs(tool_acc: dict[int, dict[str, str]]) -> list[ToolCallSpec]:
    tool_calls: list[ToolCallSpec] = []
    for index in sorted(tool_acc):
        slot = tool_acc[index]
        name = str(slot.get("name") or "").strip()
        if not name:
            continue
        args_raw = slot.get("arguments") or "{}"
        try:
            args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
        except json.JSONDecodeError:
            args = {}
        if not isinstance(args, dict):
            args = {}
        tool_calls.append(
            ToolCallSpec(
                id=str(slot.get("id") or f"tc_{uuid4().hex[:12]}"),
                name=name,
                arguments=args,
            )
        )
    return tool_calls
