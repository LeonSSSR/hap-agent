"""Structured MCP-style tool gateway for platform capabilities."""

from __future__ import annotations

from typing import Any

from config import settings
from mock_provider import mock_provider
from services.mcp_mock_tool_handler import invoke_mock_tool
from services.lineage_project_tool import build_create_project_body, format_create_project_result
from services.mcp_binding_invoker import invoke_binding_tool
from services.mcp_alias_registry import resolve_canonical_tool_name
from services.platform_api_bindings import resolve_binding
from services.mcp_readonly_contract_client import MCPReadonlyContractClient
from services.platform_probe import PlatformProbe
from services.tool_registry import tool_registry


class MCPServer:
    def __init__(self) -> None:
        self.platform_probe = PlatformProbe()
        self._readonly_client = MCPReadonlyContractClient(
            platform_probe=self.platform_probe,
            resolve_mock_payload=self._resolve_mock_payload,
            live_or_mock=self._live_or_mock,
            unwrap_platform_data=self._unwrap_platform_data,
            page_list=self._page_list,
            extract_lineage_query=self._extract_lineage_query,
            normalize_mock_contract=self._normalize_mock_contract,
        )
        self._handlers = self._build_handlers()

    def list_tools(self) -> list[str]:
        return tool_registry.list()

    def get_tool(self, tool_name: str) -> dict[str, Any] | None:
        return tool_registry.get(tool_name)

    def invoke(self, tool_name: str, payload: dict[str, Any], *, skill: dict[str, Any] | None = None) -> dict[str, Any]:
        canonical = resolve_canonical_tool_name(tool_name)
        handler = self._handlers.get(canonical)
        if handler is not None:
            return handler(payload)
        if canonical in {"approval_gate", "risk_policy_checker"}:
            return {
                "status": "ok",
                "approved": bool(payload.get("confirmed", True)),
                "tool_name": canonical,
            }
        if canonical == "lineage_project_create":
            meta = tool_registry.get(canonical) or {}
            return self._live_or_mock(
                tool_name=canonical,
                live_builder=self._lineage_project_create_live,
                mock_builder=lambda payload: invoke_mock_tool(canonical, payload, metadata=meta),
                payload=payload,
            )
        if canonical == "hap_ui_action":
            return {"status": "ok", "ui_action_id": payload.get("ui_action_id")}
        binding = resolve_binding(canonical) or resolve_binding(tool_name)
        if binding is not None:
            meta = tool_registry.get(canonical) or tool_registry.get(tool_name) or {}
            return self._live_or_mock(
                tool_name=canonical,
                live_builder=lambda client, payload: invoke_binding_tool(client, canonical, payload),
                mock_builder=lambda payload: invoke_mock_tool(canonical, payload, metadata=meta),
                payload=payload,
            )
        meta = tool_registry.get(canonical) or tool_registry.get(tool_name)
        if meta is not None:
            provider = meta.get("provider") if isinstance(meta.get("provider"), dict) else {}
            mode = str(settings.platform_api_mode).lower()
            if provider.get("real") and mode in {"live", "hybrid"}:
                raise ValueError(f"MCP tool {canonical} has no real execution path (binding/handler missing)")
            return invoke_mock_tool(canonical, payload, metadata=meta)
        raise ValueError(f"unknown MCP tool: {tool_name}")

    def _build_handlers(self) -> dict[str, Any]:
        c = self._readonly_client
        pairs = {
            "platform_service_inventory": c.call_service_inventory,
            "platform_audit_query": c.call_platform_audit_query,
            "platform_task_status": c.call_task_status,
            "platform_lineage_query": c.call_lineage_query,
            "dataset_catalog_query": c.call_dataset_catalog_query,
            "training_job_status": c.call_training_job_status,
            "model_evaluation_query": c.call_model_evaluation_query,
            "model_versions_list": c.call_model_versions_list,
            "inference_services_list": c.call_inference_services_list,
            "inference_service_status": c.call_inference_service_status,
            "model_monitor_query": c.call_model_monitor_query,
            "model_governance_audit_query": c.call_model_governance_audit_query,
        }
        return pairs

    def _resolve_mock_payload(
        self,
        resource_key: str,
        payload: dict[str, Any] | None = None,
        *,
        fallback: dict[str, Any] | None = None,
        scenario: str | None = None,
    ) -> dict[str, Any]:
        resolved = mock_provider.resolve_payload(resource_key=resource_key, scenario=scenario)
        if not isinstance(resolved, dict):
            resolved = {}
        base = dict(fallback or {})
        base.update(resolved)
        if isinstance(payload, dict):
            base.update(payload)
        return base

    def _unwrap_platform_data(self, envelope: dict[str, Any]) -> Any:
        if isinstance(envelope, dict) and "data" in envelope:
            return envelope.get("data")
        return envelope

    def _page_list(self, payload: dict[str, Any]) -> tuple[list[Any], int]:
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        return items, len(items)

    def _extract_lineage_query(self, payload: dict[str, Any]) -> str:
        return str(payload.get("query") or payload.get("table") or payload.get("resource") or "").strip()

    def _normalize_mock_contract(self, resource_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"resource_key": resource_key, **payload}

    def _live_or_mock(
        self,
        *,
        tool_name: str,
        live_builder: Any,
        mock_builder: Any,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        mode = str(settings.platform_api_mode).lower()
        if mode == "mock":
            return mock_builder(payload)
        if mode in {"live", "hybrid"}:
            try:
                from services.platform_api_client import get_platform_api_client

                client = get_platform_api_client()
                return live_builder(client, payload)
            except Exception as exc:
                if mode == "live":
                    raise PermissionError(f"live MCP call failed for {tool_name}: {exc}") from exc
                mock_result = mock_builder(payload)
                if isinstance(mock_result, dict):
                    mock_result.setdefault("live_fallback", True)
                    mock_result.setdefault("live_error", str(exc))
                return mock_result
        return mock_builder(payload)

    def _lineage_project_create_live(self, client: Any, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name") or "").strip()
        if not name:
            return {"status": "error", "error": "name 不能为空"}
        data_type = str(payload.get("dataType") or "").strip()
        if not data_type:
            return {"status": "error", "error": "dataType 不能为空"}
        body = build_create_project_body(payload)
        envelope = client.create_lineage_project(body)
        return format_create_project_result(
            envelope,
            fallback_name=name,
            fallback_data_type=body["dataType"],
            source="real",
        )


mcp_server = MCPServer()
