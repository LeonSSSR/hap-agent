"""Per-operation OpenAI tools derived from platform_operations_catalog."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from config import settings
from services.hierarchical_page_selection import (
    AgentIntentKind,
    PageRunState,
    action_scope_parent,
    build_hierarchical_ui_tool_ids,
    is_page_root,
)
from services.identity_service import AgentIdentity
from services.platform_operations_catalog import (
    get_operation,
    load_platform_operations,
    operation_agent_description,
)

OPERATION_TOOL_PREFIX = "hap_op_"

UiToolPhase = Literal["navigate", "action", "none"]


def operation_tool_name(ui_action_id: str) -> str:
    token = str(ui_action_id or "").strip()
    if not token:
        return ""
    safe = token.replace(".", "_").replace("-", "_")
    return f"{OPERATION_TOOL_PREFIX}{safe}"


@lru_cache(maxsize=1)
def _operation_tool_index() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for op in load_platform_operations():
        ui_id = str(op.get("ui_action_id") or "").strip()
        if not ui_id:
            continue
        mapping[operation_tool_name(ui_id)] = ui_id
    return mapping


def ui_action_id_from_operation_tool(tool_name: str) -> str | None:
    name = str(tool_name or "").strip()
    if not name:
        return None
    return _operation_tool_index().get(name)


def is_operation_tool(tool_name: str) -> bool:
    return str(tool_name or "").startswith(OPERATION_TOOL_PREFIX)


def clear_operation_tool_cache() -> None:
    _operation_tool_index.cache_clear()


def _layer_label(ui_action_id: str, *, phase: UiToolPhase) -> str:
    if phase == "navigate":
        return "L0 页面"
    op = get_operation(ui_action_id) or {}
    parent = str(op.get("parent_ui_action_id") or "").strip()
    if not parent:
        return "L0 页面"
    if str(op.get("action_type") or "") in {"open_panel", "page_action"}:
        return "L2 面板/步骤"
    return "L1 页内操作"


def _operation_parameters_schema(op: dict[str, Any]) -> dict[str, Any]:
    action_type = str(op.get("action_type") or "").strip().lower()
    route = str(op.get("route") or "")
    param_props: dict[str, Any] = {}
    param_required: list[str] = []
    if ":id" in route.split("?")[0]:
        param_props["id"] = {"type": "string", "description": "动态路由参数（如资源 id）"}
    if action_type == "fill":
        param_props["value"] = {"type": "string", "description": "需要填入的文本"}
        param_required.append("value")
    if not param_props:
        return {"type": "object", "properties": {}}
    return {
        "type": "object",
        "properties": {
            "params": {
                "type": "object",
                "description": "页面操作可选参数",
                "properties": param_props,
                **({"required": param_required} if param_required else {}),
            }
        },
    }


def operation_openai_tool(
    ui_action_id: str,
    *,
    phase: UiToolPhase = "action",
) -> dict[str, Any]:
    ui_id = str(ui_action_id or "").strip()
    op = get_operation(ui_id) or {}
    label = str(op.get("label") or ui_id)
    summary = operation_agent_description(ui_id)
    layer = _layer_label(ui_id, phase=phase)
    tool_name = operation_tool_name(ui_id)
    if phase == "navigate":
        usage = "先调用此类页面工具完成导航，成功后再调用页内操作工具。"
    else:
        usage = "在当前已打开页面/步骤下执行；须先完成对应页面导航。"
    description = f"[{layer}] {label}（{ui_id}）。{summary} {usage}"[:512]
    return {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": description,
            "parameters": _operation_parameters_schema(op),
        },
    }


def build_hierarchical_operation_openai_tools(
    text: str,
    *,
    identity: AgentIdentity | None,
    state: PageRunState,
    ui_intent: AgentIntentKind,
) -> tuple[list[dict[str, Any]], list[str], UiToolPhase]:
    page_roots, page_actions, phase = build_hierarchical_ui_tool_ids(
        text,
        identity=identity,
        state=state,
        ui_intent=ui_intent,
    )
    if phase == "navigate" and page_roots:
        tools = [operation_openai_tool(ui_id, phase="navigate") for ui_id in page_roots]
        return tools, page_roots, phase
    if phase == "action" and page_actions:
        tools = [operation_openai_tool(ui_id, phase="action") for ui_id in page_actions]
        return tools, page_actions, phase
    return [], [], phase


def all_operation_tool_names() -> frozenset[str]:
    return frozenset(_operation_tool_index().keys())


__all__ = [
    "OPERATION_TOOL_PREFIX",
    "UiToolPhase",
    "all_operation_tool_names",
    "build_hierarchical_operation_openai_tools",
    "clear_operation_tool_cache",
    "is_operation_tool",
    "operation_openai_tool",
    "operation_tool_name",
    "ui_action_id_from_operation_tool",
]
