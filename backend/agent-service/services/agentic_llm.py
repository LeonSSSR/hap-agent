"""Agentic multi-turn LLM interface (OpenAI-compatible tools); Mock for P0/P tests."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from config import settings

from services.agentic_output_format import format_tool_result_for_user
from services.hierarchical_page_selection import (
    is_page_root,
    page_root_of,
)
from services.operation_tools import is_operation_tool, operation_tool_name, ui_action_id_from_operation_tool
from services.platform_operations_catalog import resolve_operations_from_text
from services.tool_registry import tool_registry


class LLMClientError(RuntimeError):
    pass


@dataclass(slots=True)
class ToolCallSpec:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class AgenticTurnOutput:
    text_deltas: list[str] = field(default_factory=list)
    content: str = ""
    reasoning_content: str = ""
    reasoning_deltas: list[str] = field(default_factory=list)
    tool_calls: list[ToolCallSpec] = field(default_factory=list)


LlmStreamKind = Literal["reasoning_delta", "text_delta", "turn_complete"]


@dataclass(slots=True)
class LlmStreamEvent:
    kind: LlmStreamKind
    delta: str = ""
    output: AgenticTurnOutput | None = None


def emit_turn_chunks(out: AgenticTurnOutput) -> Iterator[LlmStreamEvent]:
    for delta in out.reasoning_deltas:
        if delta:
            yield LlmStreamEvent(kind="reasoning_delta", delta=delta)
    for delta in out.text_deltas:
        if delta:
            yield LlmStreamEvent(kind="text_delta", delta=delta)
    yield LlmStreamEvent(kind="turn_complete", output=out)


def aggregate_stream_events(events: Iterator[LlmStreamEvent]) -> AgenticTurnOutput:
    content = ""
    reasoning = ""
    text_deltas: list[str] = []
    reasoning_deltas: list[str] = []
    tool_calls: list[ToolCallSpec] = []
    for event in events:
        if event.kind == "reasoning_delta" and event.delta:
            reasoning += event.delta
            reasoning_deltas.append(event.delta)
        elif event.kind == "text_delta" and event.delta:
            content += event.delta
            text_deltas.append(event.delta)
        elif event.kind == "turn_complete" and event.output is not None:
            final = event.output
            return AgenticTurnOutput(
                text_deltas=text_deltas or final.text_deltas,
                content=content or final.content,
                reasoning_content=reasoning or final.reasoning_content,
                reasoning_deltas=reasoning_deltas or final.reasoning_deltas,
                tool_calls=final.tool_calls,
            )
    return AgenticTurnOutput(
        text_deltas=text_deltas,
        content=content,
        reasoning_content=reasoning,
        reasoning_deltas=reasoning_deltas,
        tool_calls=tool_calls,
    )


def _chunk_text(text: str, *, size: int = 16) -> list[str]:
    if not text:
        return []
    return [text[i : i + size] for i in range(0, len(text), size)]


class AgenticLlmClient(ABC):
    @abstractmethod
    def complete_turn(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        turn: int,
    ) -> AgenticTurnOutput:
        raise NotImplementedError

    def stream_turn(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        turn: int,
    ) -> Iterator[LlmStreamEvent]:
        yield from emit_turn_chunks(
            self.complete_turn(messages=messages, tools=tools, turn=turn)
        )


def _mock_tool_risk(tool_name: str) -> str:
    meta = tool_registry.get(tool_name) or {}
    return str(meta.get("risk_level") or "low").lower()


def _pick_low_risk_mock_tool(tool_names: set[str]) -> str | None:
    candidates = sorted(
        name
        for name in tool_names
        if not is_operation_tool(name) and _mock_tool_risk(name) == "low"
    )
    return candidates[0] if candidates else None


def _mock_page_root_from_hint(ui_action_id: str) -> str:
    ui_id = str(ui_action_id or "").strip()
    if is_page_root(ui_id):
        return ui_id
    return page_root_of(ui_id) or ui_id


def _tool_call_attempted(messages: list[dict[str, Any]], tool_name: str) -> bool:
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls") or []:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
            if str(fn.get("name") or "") == tool_name:
                return True
    return False


def _last_navigate_page_id(messages: list[dict[str, Any]]) -> str | None:
    pending: dict[str, str] = {}
    for msg in messages:
        if msg.get("role") == "assistant":
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function") or {}
                name = str(fn.get("name") or "")
                if not is_operation_tool(name):
                    continue
                ui_id = ui_action_id_from_operation_tool(name) or ""
                if not ui_id or not is_page_root(ui_id):
                    continue
                call_id = str(tc.get("id") or "").strip()
                if call_id and ui_id:
                    pending[call_id] = ui_id
        elif msg.get("role") == "tool":
            call_id = str(msg.get("tool_call_id") or "").strip()
            if call_id not in pending:
                continue
            content = str(msg.get("content") or "")
            if content and '"error"' not in content:
                return pending[call_id]
            pending.pop(call_id, None)
    return None


def _operation_tool_attempted(messages: list[dict[str, Any]], ui_action_id: str) -> bool:
    tool_name = operation_tool_name(ui_action_id)
    return _tool_call_attempted(messages, tool_name)


def _operation_tool_completed(messages: list[dict[str, Any]], ui_action_id: str) -> bool:
    tool_name = operation_tool_name(ui_action_id)
    return _tool_call_completed(messages, tool_name)


def _pick_exposed_operation_tool(tool_names: set[str], ui_action_id: str) -> str | None:
    candidate = operation_tool_name(ui_action_id)
    return candidate if candidate in tool_names else None


def _mock_child_action_for_scope(ui_hints: list[str], scope_page_id: str | None) -> str | None:
    from services.platform_operations_catalog import get_operation

    children = [h for h in ui_hints if not is_page_root(h)]
    if scope_page_id:
        scoped = [
            h
            for h in children
            if str((get_operation(h) or {}).get("parent_ui_action_id") or "").strip() == scope_page_id
            or page_root_of(h) == scope_page_id
        ]
        if scoped:
            return scoped[0]
    return children[0] if children else None


def _tool_call_completed(messages: list[dict[str, Any]], tool_name: str) -> bool:
    pending_ids: set[str] = set()
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls") or []:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
            if str(fn.get("name") or "") == tool_name:
                call_id = str(tc.get("id") or "").strip()
                if call_id:
                    pending_ids.add(call_id)
    if not pending_ids:
        return False
    for msg in messages:
        if msg.get("role") != "tool":
            continue
        call_id = str(msg.get("tool_call_id") or "").strip()
        if call_id not in pending_ids:
            continue
        content = str(msg.get("content") or "")
        if content and '"error"' not in content:
            return True
    return False


def _last_tool_payload(messages: list[dict[str, Any]]) -> Any:
    for msg in reversed(messages):
        if msg.get("role") != "tool":
            continue
        content = msg.get("content")
        if content is None:
            continue
        if isinstance(content, str):
            text = content.strip()
            if not text:
                continue
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        return content
    return None


def _mock_final_reply(messages: list[dict[str, Any]]) -> str:
    return format_tool_result_for_user(_last_tool_payload(messages))


def _pick_high_risk_mock_tool(tool_names: set[str]) -> str | None:
    preferred = ("approval_gate", "risk_policy_checker")
    for name in preferred:
        if name in tool_names:
            return name
    candidates = sorted(
        name
        for name in tool_names
        if not is_operation_tool(name) and _mock_tool_risk(name) in {"medium", "high"}
    )
    return candidates[0] if candidates else None


class MockAgenticLlm(AgenticLlmClient):
    """P0: turn 1 → one MCP tool; turn 2 → final assistant text, no tools."""

    def complete_turn(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        turn: int,
    ) -> AgenticTurnOutput:
        user_text = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_text = str(msg.get("content") or "")
                break
        tool_names = {
            str((t.get("function") or {}).get("name") or "")
            for t in tools
            if isinstance(t, dict)
        }
        mock_reasoning = (
            "用户请求涉及页面操作，先调用页面导航类 hap_op_* 工具，成功后再调用页内 hap_op_* 操作工具。"
            if settings.agent_model_thinking_enabled
            else ""
        )

        ui_hints = resolve_operations_from_text(user_text, limit=3)
        prefers_create = any(token in user_text for token in ("新建", "创建", "添加", "注册", "提交", "部署", "发布"))
        prefers_page_open = any(token in user_text for token in ("打开", "跳转", "进入", "前往", "页面")) or (
            prefers_create and "项目" in user_text
        )
        prefers_data_query = any(token in user_text for token in ("查询", "列出", "查看", "检查", "统计", "获取")) and not (
            prefers_page_open or prefers_create
        )

        page_id = _mock_page_root_from_hint(ui_hints[0]) if ui_hints else ""
        navigate_tool = _pick_exposed_operation_tool(tool_names, page_id) if page_id else None
        if (
            ui_hints
            and navigate_tool
            and is_page_root(page_id)
            and (prefers_page_open or prefers_create)
            and not prefers_data_query
            and not _operation_tool_attempted(messages, page_id)
        ):
            return AgenticTurnOutput(
                text_deltas=["正在打开对应页面", "…"],
                content="正在打开对应页面…",
                reasoning_content=mock_reasoning,
                reasoning_deltas=_chunk_text(mock_reasoning),
                tool_calls=[
                    ToolCallSpec(
                        id=f"tc_{uuid4().hex[:12]}",
                        name=navigate_tool,
                        arguments={"params": {}},
                    )
                ],
            )
        scope_page = _last_navigate_page_id(messages)
        child = _mock_child_action_for_scope(ui_hints, scope_page)
        action_tool = _pick_exposed_operation_tool(tool_names, child) if child else None
        if (
            ui_hints
            and action_tool
            and child
            and scope_page
            and _operation_tool_completed(messages, scope_page)
            and (prefers_page_open or prefers_create)
            and not prefers_data_query
        ):
            return AgenticTurnOutput(
                text_deltas=["正在执行页面内操作", "…"],
                content="正在执行页面内操作…",
                reasoning_content=mock_reasoning,
                reasoning_deltas=_chunk_text(mock_reasoning),
                tool_calls=[
                    ToolCallSpec(
                        id=f"tc_{uuid4().hex[:12]}",
                        name=action_tool,
                        arguments={"params": {}},
                    )
                ],
            )
        lead = _pick_low_risk_mock_tool(tool_names)
        if not lead and tool_names:
            mcp_names = sorted(n for n in tool_names if not is_operation_tool(n))
            lead = mcp_names[0] if mcp_names else None

        if turn == 1:
            high_tool = _pick_high_risk_mock_tool(tool_names)
            if high_tool and any(token in user_text for token in ("高风险", "审批")):
                return AgenticTurnOutput(
                    text_deltas=["正在准备高风险操作", "…"],
                    content="正在准备高风险操作…",
                    reasoning_content=mock_reasoning,
                    reasoning_deltas=_chunk_text(mock_reasoning),
                    tool_calls=[
                        ToolCallSpec(
                            id=f"tc_{uuid4().hex[:12]}",
                            name=high_tool,
                            arguments={"action": "publish"},
                        )
                    ],
                )

        if turn == 1 and lead:
            reasoning = mock_reasoning or "用户提出需求，先调用已授权的低风险工具获取信息。"
            return AgenticTurnOutput(
                text_deltas=["正在查询平台信息", "…"],
                content="正在查询平台信息…",
                reasoning_content=reasoning,
                reasoning_deltas=_chunk_text(reasoning),
                tool_calls=[
                    ToolCallSpec(
                        id=f"tc_{uuid4().hex[:12]}",
                        name=lead,
                        arguments={"query": "health"},
                    )
                ],
            )
        final = _mock_final_reply(messages)
        final_reasoning = (
            "工具已返回结果，接下来用自然语言整合关键信息并给出简洁结论。"
            if settings.agent_model_thinking_enabled
            else ""
        )
        return AgenticTurnOutput(
            text_deltas=_chunk_text(final) or [final],
            content=final,
            reasoning_content=final_reasoning,
            reasoning_deltas=_chunk_text(final_reasoning),
            tool_calls=[],
        )


def build_agentic_llm() -> AgenticLlmClient:
    if not settings.agent_model_enabled:
        return MockAgenticLlm()
    api_key = (settings.agent_model_api_key or "").strip()
    if not api_key or settings.agent_model_provider == "mock":
        return MockAgenticLlm()
    try:
        from services.agentic_llm_openai import OpenAIAgenticLlm

        return OpenAIAgenticLlm()
    except ImportError:
        return MockAgenticLlm()


AGENTIC_SYSTEM_PROMPT = """你是 HAP 平台智能助手，帮助用户查询与操作数据治理、模型训练、推理部署等平台能力。

## 能力边界
- 只能通过已提供的工具影响平台与 HAP 页面；不得编造已执行的操作或未确认的结果。
- 页面操作使用按层级暴露的独立工具（名称形如 `hap_op_*`）：先调用页面导航工具，成功后再调用页内操作工具。纯查询意图使用数据查询类工具。

## 回复风格
- 使用简体中文，语气专业、简洁、易懂。
- 最终回复结构：先给 1–2 句结论，再用「-」分点列出关键信息；避免堆砌 JSON 或内部字段名（如 tool_call_id、ui_action_id）。
- 调用工具前可用一句话说明正在做什么；收到工具结果后整合为自然语言，不要原样复述原始 JSON。
- 列表过长时只展示前 8 条并说明总数；失败时说明原因与下一步，同一工具连续失败不超过 2 次。

## 信息补充（hap_request_clarification）
- 必填参数缺失或用户意图不明确时，先调用 `hap_request_clarification` 向用户提问，不要猜测。
- 收到用户回答（tool 结果中的 answer）后，再选择合适工具继续执行。
- 所有写操作与页面步骤均按通用工具选择，不要假设某业务有固定捷径或预设剧本。"""
