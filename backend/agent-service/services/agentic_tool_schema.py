from __future__ import annotations

from typing import Any

from services.agentic_clarify_tool import HAP_CLARIFY_TOOL, hap_clarify_openai_tool
from services.hierarchical_page_selection import AgentIntentKind, PageRunState
from services.identity_service import AgentIdentity
from services.operation_tools import build_hierarchical_operation_openai_tools
from services.tool_registry import tool_registry


def build_agentic_openai_tools(
    tool_names: list[str],
    *,
    identity: AgentIdentity | None = None,
    user_text: str = "",
    page_state: PageRunState | None = None,
    ui_intent: AgentIntentKind = "mixed",
) -> list[dict[str, Any]]:
    state = page_state or PageRunState()
    tools: list[dict[str, Any]] = [
        hap_clarify_openai_tool(),
        *tool_registry_to_openai_tools(tool_names),
    ]
    operation_tools, _ui_ids, _phase = build_hierarchical_operation_openai_tools(
        user_text,
        identity=identity,
        state=state,
        ui_intent=ui_intent,
    )
    tools.extend(operation_tools)
    return tools


__all__ = ["HAP_CLARIFY_TOOL", "build_agentic_openai_tools", "tool_registry_to_openai_tools"]


def tool_registry_to_openai_tools(tool_names: list[str]) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for name in tool_names:
        meta = tool_registry.normalize_tool_metadata(name, tool_registry.get(name) or {})
        schema = meta.get("input_schema")
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": str(meta.get("description") or meta.get("title") or name)[:512],
                    "parameters": schema,
                },
            }
        )
    return tools
