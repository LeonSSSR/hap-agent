"""MCP registry invoke coverage and platform API bindings integrity."""

from __future__ import annotations

import pytest

from services.identity_service import AgentIdentity, permissions_for_role
from services.mcp_alias_registry import resolve_canonical_tool_name
from services.mcp_server import mcp_server
from services.mcp_tool_catalog import filter_tools_for_identity
from services.platform_api_bindings import iter_tool_bindings, load_platform_api_bindings, resolve_binding
from services.platform_operations_catalog import load_mcp_bindings
from services.tool_registry import tool_registry

_CLIENT_BINDING_NAMES = (
    "platform_api.datasets.list",
    "dataset_version_create",
    "training_job_create",
    "training_job_status",
    "platform_task_status",
    "platform_lineage_query",
    "platform_api.lineage.graph.get",
    "platform_api.lineage.node.get",
    "platform_api.lineage.impact",
    "model_versions_list",
    "inference_services_list",
    "inference_service_status",
    "model_evaluation_query",
    "model_version_register",
    "model_publish_request",
    "platform_api.model_versions.evaluate",
    "inference_service_deploy",
    "online_inference_invoke",
    "model_governance_audit_query",
    "model_monitor_query",
    "lineage_project_create",
)


def test_platform_api_bindings_file_loads() -> None:
    document = load_platform_api_bindings()
    assert document.get("api_prefix") == "/api"
    tool_names = {str(item.get("tool_name")) for item in iter_tool_bindings()}
    for name in _CLIENT_BINDING_NAMES:
        assert name in tool_names, f"missing binding: {name}"


def test_resolve_binding_for_readonly_tools() -> None:
    for name in ("training_job_status", "platform_task_status", "inference_services_list"):
        binding = resolve_binding(name)
        assert binding is not None
        assert str(binding.get("method") or "GET").upper() in {"GET", "POST"}


@pytest.mark.parametrize("tool_name", tool_registry.list())
def test_registry_tool_invoke_does_not_unknown(tool_name: str) -> None:
    if tool_name in {"hap_ui_action"}:
        pytest.skip("hap_ui_action is not an MCP registry tool")
    canonical = resolve_canonical_tool_name(tool_name)
    payload: dict[str, object] = {}
    if canonical == "lineage_project_create":
        payload = {"name": "_coverage_probe_", "dataType": "TEXT"}
    result = mcp_server.invoke(canonical, payload)
    assert isinstance(result, dict)
    assert result.get("status") == "ok" or result.get("source") in {"mock", "real"} or "summary" in result


def test_admin_identity_sees_full_mcp_registry() -> None:
    identity = AgentIdentity(
        username="admin",
        role="ADMIN",
        permissions=permissions_for_role("ADMIN"),
        auth_source="test",
    )
    allowed = filter_tools_for_identity(identity)
    assert len(allowed) == len(tool_registry.list())


def test_mcp_bindings_defaults_present() -> None:
    bindings = load_mcp_bindings()
    assert "agent.workflow" in bindings
    assert bindings["agent.workflow"].get("mcp_tools")


def test_canonical_handler_keys_work() -> None:
    for name in ("platform_task_status", "platform_lineage_query", "platform_audit_query"):
        result = mcp_server.invoke(name, {})
        assert isinstance(result, dict)
