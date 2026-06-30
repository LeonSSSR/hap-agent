"""Agentic orchestrator: MCP tool execution boundary for AgenticRunner."""

from __future__ import annotations

from typing import Any

from config import settings
from executors.restricted_executor import RestrictedExecutor
from services.identity_service import AgentIdentity
from services.mcp_adapter import MCPAdapter
from services.mcp_tool_catalog import AGENT_RUN_ID, build_planning_context
from services.session_store import session_store
from services.tool_registry import tool_registry


class AgentOrchestrator:
    def __init__(self) -> None:
        self.executor = RestrictedExecutor(tool_registry.list())
        self.mcp_adapter = MCPAdapter(self.executor)

    def build_contextual_input(
        self,
        user_input: str,
        session_id: str | None,
        *,
        identity: AgentIdentity | None = None,
    ) -> str:
        lines: list[str] = []
        owner = str(identity.username).strip() if identity is not None else ""
        session_context = None
        if session_id and identity is not None:
            from services.access_control import can_access_session

            session = session_store.get(session_id)
            if can_access_session(session, identity):
                session_context = session_store.build_context(session_id)
        min_score = float(getattr(settings, "long_term_memory_min_score", 0.0) or 0.0)
        for hit in session_store.search_long_term_memory(
            user_input,
            session_id=session_id or None,
            owner=owner or None,
        ):
            if float(hit.get("score") or 0.0) < min_score:
                continue
            if not lines:
                lines.append("[长期记忆]")
            text = str(hit.get("text") or "").strip()
            if text:
                lines.append(text[:220])
            if len(lines) >= 4:
                break
        if session_context:
            summary = str(session_context.get("summary") or "").strip()
            if summary:
                lines.append("[会话上下文]")
                lines.append(summary[:600])
        if not lines:
            return user_input
        lines.append(f"[当前请求] {user_input}")
        return "\n".join(lines)

    def bind_tool_executor(
        self,
        execution_context: dict[str, Any],
        *,
        identity: AgentIdentity | None = None,
        allow_real_write: bool = False,
    ) -> Any:
        if identity is not None:
            execution_context = build_planning_context(
                str(execution_context.get("user_input") or ""),
                identity=identity,
            )

        def _executor(
            tool_name: str,
            payload: dict[str, Any],
            *,
            trace_id: str,
            task_id: str,
            workflow_id: str,
            node_id: str,
            confirmed: bool = False,
            approved_by: str | None = None,
        ) -> dict[str, Any]:
            merged = dict(payload)
            merged["allow_real_write"] = allow_real_write
            merged["confirmed"] = confirmed
            if trace_id:
                merged["trace_id"] = trace_id
            if approved_by:
                merged["approved_by"] = approved_by
            if allow_real_write and confirmed:
                merged["write_approval_token"] = {
                    "source_node": "confirmation_node",
                    "workflow_id": workflow_id,
                    "approved_by": approved_by or "agent-approver",
                    "confirmed": True,
                }
            return self.execute_tool(
                tool_name,
                merged,
                execution_context,
                trace_id=trace_id,
                task_id=task_id,
                workflow_id=workflow_id,
                node_id=node_id,
                confirmed=confirmed,
                approved_by=approved_by,
            )

        return _executor

    def execute_tool(
        self,
        tool_name: str,
        payload: dict[str, Any],
        execution_context: dict[str, Any],
        *,
        trace_id: str,
        task_id: str,
        workflow_id: str,
        node_id: str,
        confirmed: bool = False,
        approved_by: str | None = None,
    ) -> dict[str, Any]:
        if tool_name not in tool_registry.list():
            raise PermissionError(f"tool not allowed: {tool_name}")
        allowed_tools = execution_context.get("allowed_tools")
        if isinstance(allowed_tools, list) and allowed_tools:
            allowed_set = {str(item) for item in allowed_tools}
            if tool_name not in allowed_set:
                raise PermissionError(f"tool {tool_name} not in allowed_tools | blocked_by=mcp")
        effective = {**execution_context, "skill_id": AGENT_RUN_ID, "source": "mcp", "architecture": "mcp_agentic"}
        result = self.mcp_adapter.call(
            tool_name=tool_name,
            payload=payload,
            skill=effective,
            trace_id=trace_id,
            task_id=task_id,
            workflow_id=workflow_id,
            node_id=node_id,
            confirmed=confirmed,
            approved_by=approved_by,
        )
        return {**result, "status": "succeeded", "summary": f"MCP {tool_name} executed."}
