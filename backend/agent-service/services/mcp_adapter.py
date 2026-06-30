"""Restricted adapter exposing platform MCP tools through the executor boundary."""

from __future__ import annotations

from typing import Any

from services.mcp_alias_registry import resolve_canonical_tool_name, skill_allows_tool
from services.mcp_server import mcp_server


class MCPAdapter:
    def __init__(self, executor: Any) -> None:
        self.executor = executor

    def list_tools(self) -> list[str]:
        return mcp_server.list_tools()

    def get_tool(self, tool_name: str) -> dict[str, Any] | None:
        return mcp_server.get_tool(tool_name)

    def call(
        self,
        *,
        tool_name: str,
        payload: dict[str, Any],
        skill: dict[str, Any],
        trace_id: str,
        task_id: str,
        workflow_id: str,
        node_id: str,
        confirmed: bool = False,
        approved_by: str | None = None,
    ) -> dict[str, Any]:
        canonical = resolve_canonical_tool_name(tool_name)
        allowed = skill.get("allowed_tools")
        if isinstance(allowed, list) and allowed:
            allowed_set = {str(item) for item in allowed if str(item).strip()}
            if not skill_allows_tool(canonical, allowed_set):
                raise PermissionError(f"tool {tool_name} not in allowed_tools | blocked_by=mcp")
        merged = dict(payload or {})
        merged["trace_id"] = trace_id
        merged["task_id"] = task_id
        merged["workflow_id"] = workflow_id
        merged["node_id"] = node_id
        merged["confirmed"] = confirmed
        if approved_by:
            merged["approved_by"] = approved_by
        return mcp_server.invoke(canonical, merged, skill=skill)
