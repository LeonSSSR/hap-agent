from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import yaml

from audit.logger import audit_logger

ToolExecutor = Callable[..., dict[str, Any]]

FORBIDDEN_MUTATIONS = frozenset({"delete", "truncate", "drop", "purge", "overwrite", "clear", "erase"})


class CompensationError(ValueError):
    pass


class CompensationExecutor:
    """Execute append-only compensation workflows from strategy metadata."""

    def __init__(self, registry_path: str | Path | None = None) -> None:
        self.registry_path = Path(registry_path) if registry_path else None
        self._registry = self._load_registry()

    def _load_registry(self) -> dict[str, Any]:
        if self.registry_path and self.registry_path.exists():
            data = yaml.safe_load(self.registry_path.read_text(encoding="utf-8")) or {}
            return data if isinstance(data, dict) else {}
        return {
            "default_strategy": "append_compensation_record",
            "tool_default_strategies": {},
            "strategies": {
                "append_compensation_record": {
                    "record_type": "compensation",
                    "mutation": "append_record",
                    "target_status": "compensated",
                }
            },
        }

    @property
    def append_only_policy(self) -> bool:
        return bool(self._registry.get("append_only_policy", True))

    def list_strategies(self) -> list[str]:
        strategies = self._registry.get("strategies")
        if not isinstance(strategies, dict):
            return []
        return sorted(strategies.keys())

    def get_strategy_definition(self, strategy: str) -> dict[str, Any]:
        strategies = self._registry.get("strategies")
        if not isinstance(strategies, dict):
            raise CompensationError(f"unknown compensation strategy: {strategy}")
        definition = strategies.get(strategy)
        if not isinstance(definition, dict):
            raise CompensationError(f"unknown compensation strategy: {strategy}")
        mutation = str(definition.get("mutation") or "append_record").strip().lower()
        if mutation in FORBIDDEN_MUTATIONS:
            raise CompensationError(f"compensation strategy {strategy} uses forbidden mutation: {mutation}")
        return definition

    def build_trigger_payload(
        self,
        *,
        strategy: str,
        definition: dict[str, Any],
        record: dict[str, Any],
        execution_context: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        trigger_tool = str(definition.get("trigger_tool") or "model_governance_audit_query").strip()
        trigger_action = str(definition.get("trigger_action") or strategy).strip()
        payload = {
            **execution_context,
            "action": trigger_action,
            "compensation_strategy": strategy,
            "compensation_record_id": record.get("compensation_record_id"),
            "record_type": definition.get("record_type"),
            "target_status": definition.get("target_status"),
            "append_only": True,
            "no_physical_delete": True,
            "failed_node_id": record.get("failed_node_id"),
            "failed_tool_name": record.get("failed_tool_name"),
            "error": record.get("error"),
        }
        return trigger_tool, payload

    def invoke_trigger(
        self,
        *,
        strategy: str,
        record: dict[str, Any],
        execution_context: dict[str, Any],
        trace_id: str,
        task_id: str,
        workflow_id: str,
        node_id: str,
        tool_executor: ToolExecutor | None,
    ) -> dict[str, Any] | None:
        if tool_executor is None:
            return None
        definition = self.get_strategy_definition(strategy)
        trigger_tool, payload = self.build_trigger_payload(
            strategy=strategy,
            definition=definition,
            record=record,
            execution_context=execution_context,
        )
        try:
            result = tool_executor(
                trigger_tool,
                {
                    **payload,
                    "trace_id": trace_id,
                    "task_id": task_id,
                    "workflow_id": workflow_id,
                    "node_id": node_id,
                },
                trace_id=trace_id,
                task_id=task_id,
                workflow_id=workflow_id,
                node_id=node_id,
            )
            return {
                "trigger_tool": trigger_tool,
                "trigger_action": payload.get("action"),
                "status": "triggered",
                "result": result,
            }
        except Exception as exc:
            return {
                "trigger_tool": trigger_tool,
                "trigger_action": payload.get("action"),
                "status": "degraded",
                "error": str(exc),
            }

    def resolve_strategy(
        self,
        *,
        tool_name: str | None = None,
        compensation_metadata: dict[str, Any] | None = None,
        node_compensation_action: str | None = None,
    ) -> str:
        metadata = compensation_metadata if isinstance(compensation_metadata, dict) else {}
        strategy = str(metadata.get("strategy") or "").strip()
        if strategy == "append_only_compensation":
            strategy = str(metadata.get("on_failure") or metadata.get("action") or "").strip()
        if strategy:
            return strategy
        node_action = str(node_compensation_action or "").strip()
        if node_action and node_action not in {"none", "skip"}:
            return node_action
        tool_defaults = self._registry.get("tool_default_strategies")
        if isinstance(tool_defaults, dict) and tool_name:
            mapped = str(tool_defaults.get(tool_name) or "").strip()
            if mapped:
                return mapped
        return str(self._registry.get("default_strategy") or "append_compensation_record").strip()

    def execute(
        self,
        *,
        trace_id: str,
        task_id: str,
        workflow_id: str,
        failed_node_id: str,
        failed_tool_name: str | None = None,
        error: str | None = None,
        strategy: str | None = None,
        compensation_metadata: dict[str, Any] | None = None,
        node_compensation_action: str | None = None,
        execution_context: dict[str, Any] | None = None,
        parent_event_id: str | None = None,
        tool_executor: ToolExecutor | None = None,
    ) -> dict[str, Any]:
        resolved_strategy = strategy or self.resolve_strategy(
            tool_name=failed_tool_name,
            compensation_metadata=compensation_metadata,
            node_compensation_action=node_compensation_action,
        )
        definition = self.get_strategy_definition(resolved_strategy)
        context = execution_context if isinstance(execution_context, dict) else {}
        record_id = f"comp-{uuid4().hex[:12]}"
        record = {
            "compensation_record_id": record_id,
            "strategy": resolved_strategy,
            "record_type": definition.get("record_type"),
            "mutation": definition.get("mutation"),
            "target_status": definition.get("target_status"),
            "append_only": True,
            "no_physical_delete": True,
            "failed_node_id": failed_node_id,
            "failed_tool_name": failed_tool_name,
            "error": error,
            "context_refs": {
                key: value
                for key, value in context.items()
                if not str(key).startswith("_") and value not in (None, "")
            },
        }
        trigger_result = self.invoke_trigger(
            strategy=resolved_strategy,
            record=record,
            execution_context=context,
            trace_id=trace_id,
            task_id=task_id,
            workflow_id=workflow_id,
            node_id=failed_node_id,
            tool_executor=tool_executor,
        )
        audit_event = audit_logger.log_compensation_appended(
            trace_id=trace_id,
            task_id=task_id,
            workflow_id=workflow_id,
            node_id=failed_node_id,
            compensation_action=resolved_strategy,
            reason=f"Append-only compensation executed for {failed_node_id}.",
            parent_event_id=parent_event_id,
        )
        return {
            "status": "appended",
            "compensation_state": "appended",
            "compensation_record_id": record_id,
            "strategy": resolved_strategy,
            "append_only": True,
            "no_physical_delete": True,
            "audit_id": audit_event.get("audit_id"),
            "record": record,
            "trigger_result": trigger_result,
            "triggerable": tool_executor is not None,
            "governance_result": (trigger_result or {}).get("result") if isinstance(trigger_result, dict) else None,
        }


compensation_executor = CompensationExecutor()
