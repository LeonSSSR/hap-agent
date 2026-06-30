from __future__ import annotations

from typing import Any

from services.audit_store import audit_store
from services.compensation_executor import compensation_executor
from services.observability_metrics import build_log_links, compute_rates, evaluate_alerts


class TraceViewService:
    def build_by_trace_id(self, trace_id: str, *, limit: int | None = 200) -> dict[str, Any]:
        trace_view = audit_store.build_trace_view(trace_id=trace_id, limit=limit)
        trace_view["items"] = self._sort_trace_items(trace_view.get("items", []))
        trace_view["count"] = len(trace_view["items"])
        return self._attach_observability(trace_view)

    def _attach_observability(self, trace_view: dict[str, Any]) -> dict[str, Any]:
        trace_id = str(trace_view.get("trace_id") or "")
        rates = compute_rates(trace_id=trace_id or None)
        alerts = evaluate_alerts(rates)
        compensation_records = [
            item
            for item in trace_view.get("items", [])
            if isinstance(item, dict) and str(item.get("action") or item.get("event_type") or "") == "compensation_appended"
        ]
        last_failure = next(
            (
                item
                for item in reversed(trace_view.get("items", []))
                if isinstance(item, dict)
                and str(item.get("status") or "").lower() in {"failed", "blocked", "error"}
            ),
            None,
        )
        suggested_strategy = None
        if isinstance(last_failure, dict):
            tool_name = str(last_failure.get("tool_name") or last_failure.get("mcp_tool_name") or "")
            suggested_strategy = compensation_executor.resolve_strategy(tool_name=tool_name or None)
        trace_view["observability"] = {
            "metrics": rates,
            "alerts": alerts,
            "log_links": build_log_links(trace_id=trace_id) if trace_id else {},
            "compensation": {
                "append_only": True,
                "no_physical_delete": True,
                "available_strategies": compensation_executor.list_strategies(),
                "suggested_strategy": suggested_strategy,
                "records": compensation_records,
                "trigger_endpoint": f"/api/agent/traces/{trace_id}/compensate" if trace_id else None,
            },
            "recovery_hints": [
                hint.get("message")
                for hint in alerts
                if isinstance(hint, dict) and hint.get("message")
            ],
        }
        trace_view["section"] = "trace_page"
        return trace_view

    def _sort_trace_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self._with_section(item, "audit") for item in items if isinstance(item, dict)]

    def _with_section(self, item: dict[str, Any], section: str) -> dict[str, Any]:
        enriched = dict(item)
        enriched["section"] = section
        enriched["type"] = "audit"
        enriched.setdefault("event_type", enriched.get("action") or "audit_event")
        enriched.setdefault("kind", "audit_event")
        enriched.setdefault("audit_id", enriched.get("id") or f"audit:{enriched.get('action', 'event')}:{enriched.get('timestamp', '')}")
        enriched.setdefault(
            "lineage",
            {
                "trace_id": enriched.get("trace_id"),
                "plan_id": enriched.get("plan_id"),
                "workflow_id": enriched.get("workflow_id"),
                "task_id": enriched.get("task_id"),
                "node_id": enriched.get("node_id"),
                "tool_name": enriched.get("tool_name"),
            },
        )
        return enriched


trace_view_service = TraceViewService()
