"""Audit logger persisting append-only events."""

from __future__ import annotations

from typing import Any

from services.audit_store import audit_store

AUDIT_EVENT_TOOL_EXECUTION = "tool_execution"
AUDIT_EVENT_AGENTIC_RUN_STARTED = "agentic_run_started"
AUDIT_EVENT_AGENTIC_RUN_COMPLETED = "agentic_run_completed"
AUDIT_EVENT_AGENTIC_RUN_FAILED = "agentic_run_failed"


class AuditLogger:
    def _emit(self, payload: dict[str, Any]) -> dict[str, Any]:
        record = dict(payload)
        record.setdefault("event", record.get("action"))
        action = str(record.get("action") or record.get("event") or "audit_event")
        return audit_store.add(
            action=action,
            user_input=record.get("user_input"),
            skill_name=record.get("skill_name"),
            plan_id=record.get("plan_id"),
            risk_level=record.get("risk_level"),
            need_confirm=record.get("need_confirm"),
            read_only=record.get("read_only"),
            dangerous_operation=record.get("dangerous_operation"),
            real_execution=record.get("real_execution", False),
            status=record.get("status"),
            summary=record.get("summary"),
            metadata=record.get("metadata") if isinstance(record.get("metadata"), dict) else {},
            trace_id=record.get("trace_id"),
            task_id=record.get("task_id"),
            workflow_id=record.get("workflow_id"),
            node_id=record.get("node_id"),
            tool_name=record.get("tool_name"),
            mcp_tool_name=record.get("mcp_tool_name"),
            execution_entry=record.get("execution_entry"),
            blocked_by=record.get("blocked_by"),
            blocked_reason=record.get("blocked_reason"),
            source=record.get("source"),
            correlation_id=record.get("correlation_id"),
            username=record.get("username"),
        )

    def log_agentic_run(
        self,
        *,
        action: str,
        trace_id: str,
        task_id: str,
        run_id: str,
        status: str,
        summary: str,
        metadata: dict[str, Any] | None = None,
        username: str | None = None,
    ) -> dict[str, Any]:
        return self._emit(
            {
                "action": action,
                "trace_id": trace_id,
                "task_id": task_id,
                "workflow_id": "mcp_agentic",
                "node_id": "agentic_runner",
                "status": status,
                "source": "agentic",
                "summary": summary,
                "execution_entry": "services.agentic_runner.run_events",
                "metadata": {"run_id": run_id, **(metadata or {})},
                "username": username,
            }
        )

    def log_tool_execution(
        self,
        *,
        trace_id: str,
        task_id: str,
        skill_id: str | None = None,
        workflow_id: str | None = None,
        node_id: str | None = None,
        tool_name: str,
        context: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        status: str = "succeeded",
        summary: str = "",
        correlation_id: str | None = None,
        source: str = "mock",
        payload: dict[str, Any] | None = None,
        username: str | None = None,
    ) -> dict[str, Any]:
        meta = dict(context or {})
        if payload:
            meta.update(payload)
        if result:
            meta["result"] = result
        return self._emit(
            {
                "action": AUDIT_EVENT_TOOL_EXECUTION,
                "trace_id": trace_id,
                "task_id": task_id,
                "workflow_id": workflow_id,
                "node_id": node_id,
                "skill_name": skill_id,
                "tool_name": tool_name,
                "mcp_tool_name": tool_name,
                "status": status,
                "summary": summary or f"MCP {tool_name} {status}",
                "source": source,
                "correlation_id": correlation_id,
                "metadata": meta,
                "username": username,
            }
        )

    def log_blocked_execution(self, **kwargs: Any) -> dict[str, Any]:
        payload = dict(kwargs)
        payload.setdefault("action", "blocked_execution")
        payload.setdefault("status", "blocked")
        return self._emit(payload)

    def log_compensation_appended(self, **kwargs: Any) -> dict[str, Any]:
        payload = dict(kwargs)
        payload.setdefault("action", "compensation_appended")
        return self._emit(payload)


audit_logger = AuditLogger()
