"""Agentic run loop: multi-turn LLM + MCP tools → SSE events."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from audit.logger import audit_logger
from config import settings
from schemas.agentic import AgentRunRequest
from services.agentic_llm import AGENTIC_SYSTEM_PROMPT, AgenticLlmClient, MockAgenticLlm, build_agentic_llm
from services.agentic_output_format import format_result_preview, format_tool_result_for_llm
from services.agentic_clarify_tool import HAP_CLARIFY_TOOL, missing_required_tool_arguments
from services.agentic_tool_schema import build_agentic_openai_tools
from services.identity_service import AgentIdentity
from services.mcp_tool_catalog import AGENT_RUN_ID, build_planning_context, select_tools_for_llm
from services.session_store import session_store
from services.hierarchical_page_selection import (
    PageRunState,
    action_scope_parent,
    advance_state_after_ui_success,
    build_hierarchical_ui_tool_ids,
    classify_agent_intent,
    is_page_root,
    no_match_message,
    validate_navigate_page,
    validate_page_action,
)
from services.operation_tools import (
    is_operation_tool,
    operation_tool_name,
    ui_action_id_from_operation_tool,
)
from services.platform_operations_catalog import (
    get_operation,
    identity_allows_ui_action,
    operation_action_type,
    operation_effective_route,
    operation_risk_level,
    valid_ui_action_ids,
)
from services.run_store import run_store
from services.tool_registry import tool_registry

ToolExecutor = Callable[..., dict[str, Any]]
SseEvent = tuple[str, dict[str, Any]]


def _tool_risk_level(tool_name: str) -> str:
    meta = tool_registry.get(tool_name) or {}
    return str(meta.get("risk_level") or "low").lower()


def _needs_confirm(tool_name: str, *, confirm_high_risk: bool) -> str | None:
    if not confirm_high_risk:
        return None
    risk = _tool_risk_level(tool_name)
    if risk in {"medium", "high"}:
        return risk
    return None


def _needs_ui_confirm(ui_action_id: str, *, confirm_high_risk: bool) -> str | None:
    if not confirm_high_risk:
        return None
    risk = operation_risk_level(ui_action_id)
    if risk in {"medium", "high"}:
        return risk
    return None


@dataclass(slots=True)
class _ConfirmGateResult:
    proceed: bool
    confirmed: bool = True
    approved_by: str | None = None
    blocked_preview: str | None = None


def _confirm_gate_begin(
    *,
    run_id: str,
    tool_call_id: str,
    tool_name: str,
    risk_level: str,
    turn: int,
    index: int,
    ui_action_id: str | None = None,
) -> tuple[str, SseEvent]:
    resume_token = f"resume-{uuid4().hex[:12]}"
    run_store.register_confirm_wait(run_id, tool_call_id, resume_token)
    payload: dict[str, Any] = {
        "run_id": run_id,
        "tool_call_id": tool_call_id,
        "tool_name": tool_name,
        "risk_level": risk_level,
        "resume_token": resume_token,
        "turn": turn,
        "index": index,
    }
    if ui_action_id:
        payload["ui_action_id"] = ui_action_id
    return resume_token, ("confirm_required", payload)


def _confirm_timeout_seconds(risk_level: str) -> float:
    level = str(risk_level or "low").strip().lower()
    if level == "high":
        return float(settings.agentic_confirm_timeout_high_seconds)
    if level == "medium":
        return float(settings.agentic_confirm_timeout_medium_seconds)
    return float(settings.agentic_confirm_timeout_seconds)


def _confirm_gate_complete(
    *,
    run_id: str,
    tool_call_id: str,
    tool_name: str,
    resume_token: str,
    turn: int,
    index: int,
    risk_level: str = "low",
    cancel_check: Callable[[], bool] | None = None,
) -> tuple[list[SseEvent], _ConfirmGateResult]:
    events: list[SseEvent] = []
    decision_pack = run_store.wait_confirm(
        run_id,
        resume_token,
        timeout_seconds=_confirm_timeout_seconds(risk_level),
        cancel_check=cancel_check,
    )
    if decision_pack is None:
        events.append(
            (
                "tool_blocked",
                {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "blocked_reason": "tool_confirm_pending",
                    "policy_source": "executor.restricted",
                    "blocked_label": "确认会话无效或已失效",
                    "turn": turn,
                    "index": index,
                },
            )
        )
        return events, _ConfirmGateResult(proceed=False, blocked_preview="confirm session missing")
    decision, confirm_by = decision_pack
    if decision != "approve":
        events.append(
            (
                "tool_blocked",
                {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "blocked_reason": "approval_required",
                    "policy_source": "executor.restricted",
                    "blocked_label": "用户拒绝高风险操作",
                    "turn": turn,
                    "index": index,
                },
            )
        )
        return events, _ConfirmGateResult(proceed=False, blocked_preview="rejected")
    return events, _ConfirmGateResult(proceed=True, confirmed=True, approved_by=confirm_by)


@dataclass(slots=True)
class _ClarifyGateResult:
    proceed: bool
    answer: str = ""
    skipped: bool = False
    blocked_preview: str | None = None


def _clarify_gate_begin(
    *,
    run_id: str,
    tool_call_id: str,
    question: str,
    turn: int,
    index: int,
    fields: list[str] | None = None,
    placeholder: str | None = None,
    choices: list[str] | None = None,
) -> tuple[str, SseEvent]:
    resume_token = f"clarify-{uuid4().hex[:12]}"
    run_store.register_clarify_wait(run_id, tool_call_id, resume_token)
    payload: dict[str, Any] = {
        "run_id": run_id,
        "tool_call_id": tool_call_id,
        "tool_name": HAP_CLARIFY_TOOL,
        "question": question,
        "resume_token": resume_token,
        "turn": turn,
        "index": index,
    }
    if fields:
        payload["fields"] = fields
    if placeholder:
        payload["placeholder"] = placeholder
    if choices:
        payload["choices"] = choices
    return resume_token, ("clarification_required", payload)


def _clarify_gate_complete(
    *,
    run_id: str,
    tool_call_id: str,
    resume_token: str,
    turn: int,
    index: int,
    cancel_check: Callable[[], bool] | None = None,
) -> tuple[list[SseEvent], _ClarifyGateResult]:
    events: list[SseEvent] = []
    answer_pack = run_store.wait_clarify(
        run_id,
        resume_token,
        timeout_seconds=float(settings.agentic_clarify_timeout_seconds),
        cancel_check=cancel_check,
    )
    if answer_pack is None:
        events.append(
            (
                "tool_blocked",
                {
                    "tool_call_id": tool_call_id,
                    "tool_name": HAP_CLARIFY_TOOL,
                    "blocked_reason": "clarification_pending",
                    "policy_source": "executor.restricted",
                    "blocked_label": "补充信息会话无效或已失效",
                    "turn": turn,
                    "index": index,
                },
            )
        )
        return events, _ClarifyGateResult(proceed=False, blocked_preview="clarify session missing")
    answer, skipped = answer_pack
    if skipped or not str(answer).strip():
        events.append(
            (
                "tool_blocked",
                {
                    "tool_call_id": tool_call_id,
                    "tool_name": HAP_CLARIFY_TOOL,
                    "blocked_reason": "clarification_skipped",
                    "policy_source": "user",
                    "blocked_label": "用户跳过补充信息",
                    "turn": turn,
                    "index": index,
                },
            )
        )
        return events, _ClarifyGateResult(proceed=False, skipped=True, blocked_preview="skipped")
    return events, _ClarifyGateResult(proceed=True, answer=str(answer).strip())


def _preview_result(payload: Any, *, tool_name: str = "", limit: int = 200) -> str:
    return format_result_preview(payload, limit=limit) or format_tool_result_for_llm(
        payload, tool_name=tool_name
    )[:limit]


def _operation_tool_names_from_schema(tools_schema: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for tool in tools_schema:
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
        name = str(fn.get("name") or "").strip()
        if name and is_operation_tool(name):
            names.append(name)
    return names


def _validate_operation_tool_call(
    ui_id: str,
    *,
    state: PageRunState,
    identity: AgentIdentity | None,
) -> tuple[str, str]:
    if is_page_root(ui_id):
        err = validate_navigate_page(ui_id, identity=identity)
        if err == "invalid page_id":
            return "ui_action_not_allowed", f"未知页面 {ui_id}"
        if err == "not a page root":
            return "ui_action_not_allowed", f"{ui_id} 不是页面根节点"
        if err == "permission_denied":
            return "permission_denied", f"当前账号无「{ui_id}」页面权限"
        if err:
            return "ui_action_not_allowed", err
        return "", ""
    err = validate_page_action(ui_id, state=state, identity=identity)
    if err == "navigate_required":
        return "ui_action_not_allowed", "须先完成页面导航"
    if err == "invalid action_id":
        return "ui_action_not_allowed", f"未知操作 {ui_id}"
    if err and err.startswith("action not under"):
        return "ui_action_not_allowed", err
    if err == "page roots require navigation phase":
        return "ui_action_not_allowed", "页面根节点请使用页面导航工具"
    if err == "permission_denied":
        return "permission_denied", f"当前账号无「{ui_id}」操作权限"
    if err:
        return "ui_action_not_allowed", err
    return "", ""


def _iter_ui_page_tool_events(
    *,
    run_id: str,
    call: Any,
    tool_name: str,
    ui_id: str,
    request: AgentRunRequest,
    identity: AgentIdentity | None,
    turn: int,
    index: int,
    cancel_check: Callable[[], bool] | None,
) -> Iterator[tuple[SseEvent, dict[str, Any] | None]]:
    """Yield SSE events for navigate/page_action; terminal dict has llm tool message payload."""
    if ui_id not in valid_ui_action_ids():
        yield (
            (
                "tool_blocked",
                {
                    "tool_call_id": call.id,
                    "tool_name": tool_name,
                    "blocked_reason": "ui_action_not_allowed",
                    "policy_source": "executor.restricted",
                    "blocked_label": f"未知页面操作 {ui_id}",
                    "turn": turn,
                    "index": index,
                },
            ),
            {"role": "tool", "tool_call_id": call.id, "content": json.dumps({"error": "invalid ui_action_id"})},
        )
        return
    if not identity_allows_ui_action(identity, ui_id):
        yield (
            (
                "tool_blocked",
                {
                    "tool_call_id": call.id,
                    "tool_name": tool_name,
                    "blocked_reason": "permission_denied",
                    "policy_source": "identity.permissions",
                    "blocked_label": f"当前账号无「{ui_id}」页面操作权限",
                    "turn": turn,
                    "index": index,
                },
            ),
            {"role": "tool", "tool_call_id": call.id, "content": json.dumps({"error": "permission_denied"})},
        )
        return

    op = get_operation(ui_id) or {}
    title = str(op.get("label") or ui_id)
    ui_risk = _needs_ui_confirm(ui_id, confirm_high_risk=request.options.confirm_high_risk)
    if ui_risk:
        _resume_token, confirm_evt = _confirm_gate_begin(
            run_id=run_id,
            tool_call_id=call.id,
            tool_name=tool_name,
            risk_level=ui_risk,
            turn=turn,
            index=index,
            ui_action_id=ui_id,
        )
        yield (confirm_evt, None)
        gate_events, gate = _confirm_gate_complete(
            run_id=run_id,
            tool_call_id=call.id,
            tool_name=tool_name,
            resume_token=_resume_token,
            turn=turn,
            index=index,
            risk_level=ui_risk,
            cancel_check=cancel_check,
        )
        for evt in gate_events:
            yield (evt, None)
        if cancel_check and cancel_check():
            yield (("run_done", {"status": "stopped"}), {"_stop": True})
            return
        if not gate.proceed:
            preview = gate.blocked_preview or "rejected"
            yield (
                (
                    "tool_result",
                    {
                        "tool_call_id": call.id,
                        "tool_name": tool_name,
                        "status": "error",
                        "duration_ms": 0,
                        "result_preview": preview,
                        "turn": turn,
                    },
                ),
                {"role": "tool", "tool_call_id": call.id, "content": json.dumps({"error": preview})},
            )
            return

    params = call.arguments.get("params") if isinstance(call.arguments.get("params"), dict) else {}
    catalog_route = str(op.get("route") or "")
    navigate_route = operation_effective_route(ui_id, params=params)
    run_store.register_page_wait(run_id, call.id, ui_action_id=ui_id)
    yield (
        (
            "tool_start",
            {
                "tool_call_id": call.id,
                "tool_name": tool_name,
                "arguments_preview": call.arguments,
                "turn": turn,
                "index": index,
            },
        ),
        None,
    )
    yield (
        (
            "page_action",
            {
                "tool_call_id": call.id,
                "ui_action_id": ui_id,
                "title": title,
                "status": "pending",
                "action_type": operation_action_type(ui_id),
                "route": catalog_route,
                "navigate_route": navigate_route,
                "params": params,
                "turn": turn,
            },
        ),
        None,
    )
    started = time.monotonic()
    page_result = run_store.wait_page_result(
        run_id,
        call.id,
        timeout_seconds=float(settings.agentic_page_result_timeout_seconds),
        cancel_check=cancel_check,
    )
    duration_ms = int((time.monotonic() - started) * 1000)
    if page_result is None and cancel_check and cancel_check():
        yield (("run_done", {"status": "stopped"}), {"_stop": True})
        return
    if page_result is None:
        preview = "page_result timeout"
        yield (
            (
                "tool_result",
                {
                    "tool_call_id": call.id,
                    "tool_name": tool_name,
                    "status": "error",
                    "duration_ms": duration_ms,
                    "result_preview": preview,
                    "turn": turn,
                },
            ),
            {"role": "tool", "tool_call_id": call.id, "content": json.dumps({"error": preview})},
        )
        return

    llm_content = format_tool_result_for_llm(page_result, tool_name=tool_name)
    preview = _preview_result(page_result, tool_name=tool_name)
    yield (
        (
            "tool_result",
            {
                "tool_call_id": call.id,
                "tool_name": tool_name,
                "status": "ok" if page_result.get("success", True) else "error",
                "duration_ms": duration_ms,
                "result_preview": preview,
                "turn": turn,
            },
        ),
        {
            "role": "tool",
            "tool_call_id": call.id,
            "content": llm_content,
            "_page_success": bool(page_result.get("success", True)),
        },
    )


class AgenticRunner:
    def __init__(
        self,
        *,
        tool_executor: ToolExecutor,
        llm: AgenticLlmClient | None = None,
    ) -> None:
        self.llm = llm or build_agentic_llm()
        self.tool_executor = tool_executor

    def _max_turns(self, request: AgentRunRequest) -> int:
        if request.options.max_turns is not None:
            return int(request.options.max_turns)
        return int(settings.agentic_max_turns)

    def run_events(
        self,
        *,
        request: AgentRunRequest,
        identity: AgentIdentity | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Iterator[SseEvent]:
        run_id = f"run-{uuid4().hex[:12]}"
        owner = str(identity.username if identity is not None else "__anonymous__").strip() or "__anonymous__"
        actor = owner
        run_store.register_run(run_id, owner)
        trace_id = f"trace-{uuid4().hex[:12]}"
        task_id = f"task-{uuid4().hex[:12]}"
        workflow_id = f"workflow-{uuid4().hex[:12]}"
        session_id = str(request.session_id or "").strip() or None
        ctx = build_planning_context(request.message, identity=identity)
        allowed = [str(t) for t in (ctx.get("allowed_tools") or []) if str(t).strip()]
        llm_tools = [str(t) for t in (ctx.get("llm_tools") or select_tools_for_llm(request.message, identity)) if str(t).strip()]
        page_state = PageRunState()
        ui_intent = classify_agent_intent(request.message)
        page_roots, page_actions, ui_phase = build_hierarchical_ui_tool_ids(
            request.message,
            identity=identity,
            state=page_state,
            ui_intent=ui_intent,
        )
        tools_schema = build_agentic_openai_tools(
            llm_tools,
            identity=identity,
            user_text=request.message,
            page_state=page_state,
            ui_intent=ui_intent,
        )
        allowed_with_ui = [*allowed, *_operation_tool_names_from_schema(tools_schema)]
        current_message = request.message.strip()
        if session_id and session_store.exists(session_id):
            messages = session_store.build_llm_messages(
                session_id,
                system_prompt=AGENTIC_SYSTEM_PROMPT,
                current_user_message=current_message,
            )
        else:
            messages = [
                {"role": "system", "content": AGENTIC_SYSTEM_PROMPT},
                {"role": "user", "content": current_message},
            ]
        tool_count = 0
        max_turns = self._max_turns(request)

        yield (
            "run_start",
            {
                "run_id": run_id,
                "trace_id": trace_id,
                "session_id": session_id,
                "architecture": "mcp_agentic",
                "thinking_enabled": settings.agent_model_thinking_enabled,
                "llm_streaming": settings.agent_model_stream_enabled,
                "llm_tool_count": len(llm_tools),
                "llm_ui_action_count": len(page_roots) + len(page_actions),
                "ui_phase": ui_phase,
            },
        )
        audit_logger.log_agentic_run(
            action="agentic_run_started",
            trace_id=trace_id,
            task_id=task_id,
            run_id=run_id,
            status="running",
            summary=request.message.strip()[:240],
            metadata={"session_id": session_id, "architecture": "mcp_agentic"},
            username=actor,
        )

        def _finish_run(status: str, *, turns: int, summary: str) -> SseEvent:
            if status in {"completed", "failed"}:
                terminal_action = "agentic_run_completed" if status == "completed" else "agentic_run_failed"
                audit_logger.log_agentic_run(
                    action=terminal_action,
                    trace_id=trace_id,
                    task_id=task_id,
                    run_id=run_id,
                    status=status,
                    summary=summary[:240],
                    metadata={"turns": turns, "tool_count": tool_count},
                    username=actor,
                )
            payload: dict[str, Any] = {
                "status": status,
                "turns": turns,
                "tool_count": tool_count,
                "run_id": run_id,
                "trace_id": trace_id,
            }
            if summary:
                payload["summary"] = summary
            return ("run_done", payload)

        for turn in range(1, max_turns + 1):
            if cancel_check and cancel_check():
                yield _finish_run("stopped", turns=turn - 1, summary="run cancelled")
                return

            page_roots, page_actions, ui_phase = build_hierarchical_ui_tool_ids(
                current_message,
                identity=identity,
                state=page_state,
                ui_intent=ui_intent,
            )
            if ui_phase == "navigate" and not page_roots:
                no_match = no_match_message(phase="navigate")
                yield ("assistant_message", {"content": no_match, "turn": turn})
                yield _finish_run("completed", turns=turn, summary=no_match)
                return
            if ui_phase == "action" and not page_actions:
                scope_op = get_operation(action_scope_parent(page_state)) or {}
                no_match = no_match_message(
                    phase="action",
                    scope_label=str(scope_op.get("label") or ""),
                )
                yield ("assistant_message", {"content": no_match, "turn": turn})
                yield _finish_run("completed", turns=turn, summary=no_match)
                return

            tools_schema = build_agentic_openai_tools(
                llm_tools,
                identity=identity,
                user_text=current_message,
                page_state=page_state,
                ui_intent=ui_intent,
            )
            allowed_with_ui = [*allowed, *_operation_tool_names_from_schema(tools_schema)]

            out = None
            try:
                for stream_event in self.llm.stream_turn(messages=messages, tools=tools_schema, turn=turn):
                    if stream_event.kind == "reasoning_delta" and stream_event.delta:
                        yield ("reasoning_delta", {"delta": stream_event.delta, "turn": turn})
                    elif stream_event.kind == "text_delta" and stream_event.delta:
                        yield ("assistant_delta", {"delta": stream_event.delta, "turn": turn})
                    elif stream_event.kind == "turn_complete":
                        out = stream_event.output
            except Exception as exc:
                if (
                    settings.agent_model_fallback_to_rules
                    and not isinstance(self.llm, MockAgenticLlm)
                ):
                    self.llm = MockAgenticLlm()
                    try:
                        for stream_event in self.llm.stream_turn(
                            messages=messages, tools=tools_schema, turn=turn
                        ):
                            if stream_event.kind == "reasoning_delta" and stream_event.delta:
                                yield ("reasoning_delta", {"delta": stream_event.delta, "turn": turn})
                            elif stream_event.kind == "text_delta" and stream_event.delta:
                                yield ("assistant_delta", {"delta": stream_event.delta, "turn": turn})
                            elif stream_event.kind == "turn_complete":
                                out = stream_event.output
                    except Exception as retry_exc:
                        yield ("error", {"message": str(retry_exc), "code": "llm_error", "turn": turn})
                        yield _finish_run("failed", turns=turn, summary=str(retry_exc))
                        return
                else:
                    yield ("error", {"message": str(exc), "code": "llm_error", "turn": turn})
                    yield _finish_run("failed", turns=turn, summary=str(exc))
                    return

            if out is None:
                yield ("error", {"message": "LLM stream ended without turn_complete", "code": "llm_error", "turn": turn})
                yield _finish_run("failed", turns=turn, summary="LLM stream incomplete")
                return

            if out.reasoning_content:
                yield ("reasoning_message", {"content": out.reasoning_content, "turn": turn})

            if not out.tool_calls:
                if out.content:
                    yield ("assistant_message", {"content": out.content, "turn": turn})
                    messages.append({"role": "assistant", "content": out.content})
                yield _finish_run("completed", turns=turn, summary=out.content or "完成")
                return

            assistant_tool_calls: list[dict[str, Any]] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": json.dumps(call.arguments, ensure_ascii=False)},
                }
                for call in out.tool_calls
            ]
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": out.content or None,
                "tool_calls": assistant_tool_calls,
            }
            if out.reasoning_content:
                assistant_msg["reasoning_content"] = out.reasoning_content
            messages.append(assistant_msg)

            tool_calls = list(out.tool_calls[: int(settings.agentic_max_tools_per_turn)])
            for index, call in enumerate(tool_calls):
                if call.name == HAP_CLARIFY_TOOL:
                    question = str(call.arguments.get("question") or "").strip()
                    if not question:
                        question = "请补充继续操作所需的信息："
                    raw_fields = call.arguments.get("fields")
                    fields = (
                        [str(item).strip() for item in raw_fields if str(item).strip()]
                        if isinstance(raw_fields, list)
                        else None
                    )
                    placeholder = str(call.arguments.get("placeholder") or "").strip() or None
                    raw_choices = call.arguments.get("choices")
                    choices = (
                        [str(item).strip() for item in raw_choices if str(item).strip()]
                        if isinstance(raw_choices, list)
                        else None
                    )
                    yield (
                        "tool_start",
                        {
                            "tool_call_id": call.id,
                            "tool_name": call.name,
                            "arguments_preview": call.arguments,
                            "turn": turn,
                            "index": index,
                        },
                    )
                    _resume_token, clarify_evt = _clarify_gate_begin(
                        run_id=run_id,
                        tool_call_id=call.id,
                        question=question,
                        turn=turn,
                        index=index,
                        fields=fields,
                        placeholder=placeholder,
                        choices=choices,
                    )
                    yield clarify_evt
                    gate_events, gate = _clarify_gate_complete(
                        run_id=run_id,
                        tool_call_id=call.id,
                        resume_token=_resume_token,
                        turn=turn,
                        index=index,
                        cancel_check=cancel_check,
                    )
                    for evt in gate_events:
                        yield evt
                    if cancel_check and cancel_check():
                        yield _finish_run("stopped", turns=turn, summary="client disconnected")
                        return
                    if not gate.proceed:
                        preview = gate.blocked_preview or "skipped"
                        messages.append(
                            {"role": "tool", "tool_call_id": call.id, "content": json.dumps({"error": preview})}
                        )
                        continue
                    llm_content = json.dumps(
                        {
                            "answer": gate.answer,
                            "fields": fields or [],
                            "choices": choices or [],
                            "skipped": gate.skipped,
                        },
                        ensure_ascii=False,
                    )
                    yield (
                        "tool_result",
                        {
                            "tool_call_id": call.id,
                            "tool_name": call.name,
                            "status": "ok",
                            "duration_ms": 0,
                            "result_preview": gate.answer[:200],
                            "turn": turn,
                        },
                    )
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": llm_content})
                    continue

                if is_operation_tool(call.name):
                    ui_id = ui_action_id_from_operation_tool(call.name) or ""
                    blocked_reason = ""
                    blocked_label = ""
                    if not ui_id:
                        blocked_reason, blocked_label = "ui_action_not_allowed", f"未知页面操作工具 {call.name}"
                    else:
                        blocked_reason, blocked_label = _validate_operation_tool_call(
                            ui_id,
                            state=page_state,
                            identity=identity,
                        )
                    if blocked_reason:
                        yield (
                            "tool_blocked",
                            {
                                "tool_call_id": call.id,
                                "tool_name": call.name,
                                "blocked_reason": blocked_reason,
                                "policy_source": (
                                    "identity.permissions"
                                    if blocked_reason == "permission_denied"
                                    else "executor.restricted"
                                ),
                                "blocked_label": blocked_label,
                                "turn": turn,
                                "index": index,
                            },
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call.id,
                                "content": json.dumps({"error": blocked_label}),
                            }
                        )
                        continue

                    stopped = False
                    tool_msg: dict[str, Any] | None = None
                    for evt, msg_payload in _iter_ui_page_tool_events(
                        run_id=run_id,
                        call=call,
                        tool_name=call.name,
                        ui_id=ui_id,
                        request=request,
                        identity=identity,
                        turn=turn,
                        index=index,
                        cancel_check=cancel_check,
                    ):
                        if msg_payload and msg_payload.get("_stop"):
                            stopped = True
                            break
                        yield evt
                        if msg_payload and not msg_payload.get("_stop"):
                            tool_msg = msg_payload
                    if stopped:
                        yield _finish_run("stopped", turns=turn, summary="client disconnected")
                        return
                    if tool_msg:
                        messages.append(
                            {
                                k: v
                                for k, v in tool_msg.items()
                                if k not in {"_page_success", "_stop"}
                            }
                        )
                        if tool_msg.get("_page_success"):
                            advance_state_after_ui_success(
                                page_state,
                                ui_id=ui_id,
                                tool_name=call.name,
                                identity=identity,
                            )
                            tool_count += 1
                    continue

                if call.name not in allowed_with_ui:
                    yield (
                        "tool_blocked",
                        {
                            "tool_call_id": call.id,
                            "tool_name": call.name,
                            "blocked_reason": "skill_tool_not_allowed",
                            "policy_source": "skill.allowed_tools",
                            "blocked_label": f"工具 {call.name} 不在允许列表",
                            "turn": turn,
                            "index": index,
                        },
                    )
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps({"error": "tool not allowed"})})
                    continue

                exec_args = dict(call.arguments)
                missing_fields = missing_required_tool_arguments(call.name, exec_args)
                if missing_fields:
                    field_labels = {
                        "name": "项目名称",
                        "dataType": "数据类型",
                    }
                    labels = [field_labels.get(field, field) for field in missing_fields]
                    preview = f"缺少必填参数：{', '.join(labels)}"
                    yield (
                        "tool_blocked",
                        {
                            "tool_call_id": call.id,
                            "tool_name": call.name,
                            "blocked_reason": "missing_required_arguments",
                            "policy_source": "executor.restricted",
                            "blocked_label": preview,
                            "missing_fields": missing_fields,
                            "turn": turn,
                            "index": index,
                        },
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(
                                {
                                    "error": preview,
                                    "missing_fields": missing_fields,
                                    "hint": "请调用 hap_request_clarification 向用户补充，不要猜测或自动填充参数",
                                },
                                ensure_ascii=False,
                            ),
                        }
                    )
                    continue

                tool_risk = _tool_risk_level(call.name)
                confirmed = tool_risk == "low"
                approved_by = str(identity.username) if identity and confirmed else None
                risk_level = _needs_confirm(call.name, confirm_high_risk=request.options.confirm_high_risk)
                if risk_level:
                    _resume_token, confirm_evt = _confirm_gate_begin(
                        run_id=run_id,
                        tool_call_id=call.id,
                        tool_name=call.name,
                        risk_level=risk_level,
                        turn=turn,
                        index=index,
                    )
                    yield confirm_evt
                    gate_events, gate = _confirm_gate_complete(
                        run_id=run_id,
                        tool_call_id=call.id,
                        tool_name=call.name,
                        resume_token=_resume_token,
                        turn=turn,
                        index=index,
                        risk_level=risk_level,
                        cancel_check=cancel_check,
                    )
                    for evt in gate_events:
                        yield evt
                    if cancel_check and cancel_check():
                        yield _finish_run("stopped", turns=turn, summary="client disconnected")
                        return
                    if not gate.proceed:
                        preview = gate.blocked_preview or "rejected"
                        messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps({"error": preview})})
                        continue
                    confirmed = gate.confirmed
                    approved_by = gate.approved_by or approved_by

                yield (
                    "tool_start",
                    {
                        "tool_call_id": call.id,
                        "tool_name": call.name,
                        "arguments_preview": exec_args,
                        "turn": turn,
                        "index": index,
                    },
                )
                started = time.monotonic()
                try:
                    raw = self.tool_executor(
                        call.name,
                        exec_args,
                        trace_id=trace_id,
                        task_id=task_id,
                        workflow_id=workflow_id,
                        node_id=f"agentic-{turn}-{index}",
                        confirmed=confirmed,
                        approved_by=approved_by,
                    )
                    duration_ms = int((time.monotonic() - started) * 1000)
                    llm_content = format_tool_result_for_llm(raw, tool_name=call.name)
                    preview = _preview_result(raw, tool_name=call.name)
                    tool_count += 1
                    audit_logger.log_tool_execution(
                        trace_id=trace_id,
                        task_id=task_id,
                        skill_id=AGENT_RUN_ID,
                        workflow_id=workflow_id,
                        node_id=f"agentic-{turn}-{index}",
                        tool_name=call.name,
                        context={"run_id": run_id, "execution_entry": "agentic_runner"},
                        result=raw if isinstance(raw, dict) else {"payload": raw},
                        status="succeeded",
                        summary=preview[:240],
                        source=str(raw.get("source", "mock")) if isinstance(raw, dict) else "mock",
                        username=actor,
                    )
                    yield (
                        "tool_result",
                        {
                            "tool_call_id": call.id,
                            "tool_name": call.name,
                            "status": "ok",
                            "duration_ms": duration_ms,
                            "result_preview": preview,
                            "turn": turn,
                        },
                    )
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": llm_content})
                except Exception as exc:
                    duration_ms = int((time.monotonic() - started) * 1000)
                    err = str(exc)
                    yield (
                        "tool_result",
                        {
                            "tool_call_id": call.id,
                            "tool_name": call.name,
                            "status": "error",
                            "duration_ms": duration_ms,
                            "result_preview": err[:500],
                            "turn": turn,
                        },
                    )
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps({"error": err})})

        yield _finish_run("failed", turns=max_turns, summary="agentic_max_turns")

    async def run_stream_async(
        self,
        *,
        request: AgentRunRequest,
        identity: AgentIdentity | None = None,
        disconnect_check: Callable[[], bool] | None = None,
    ) -> AsyncIterator[SseEvent]:
        for event in self.run_events(request=request, identity=identity, cancel_check=disconnect_check):
            yield event
