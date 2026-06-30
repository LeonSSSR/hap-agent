"""Generic mock invocation for MCP tools without dedicated handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from mock_provider import mock_provider

_TOOL_RESOURCE_KEYS: dict[str, str] = {
    "dataset_catalog_query": "platform.dataset.catalog",
    "dataset_version_create": "platform.dataset.version.create",
    "training_job_create": "platform.training.job.create",
    "training_job_status": "platform.training.job.status",
    "model_version_register": "platform.model.version.register",
    "model_evaluation_query": "platform.model.evaluation.query",
    "model_publish_request": "platform.model.publish.request",
    "model_versions_list": "platform.model.versions.list",
    "inference_service_deploy": "platform.inference.service.deploy",
    "inference_service_status": "platform.inference.service.status",
    "inference_services_list": "platform.inference.services.list",
    "online_inference_invoke": "platform.inference.invoke",
    "model_monitor_query": "platform.model.monitor.query",
    "model_governance_audit_query": "platform.model.governance.audit.query",
    "platform_task_status": "platform.task.status",
    "platform_lineage_query": "platform.lineage.graph",
    "platform_audit_query": "platform.audit.timeline",
    "platform_service_inventory": "platform.service.inventory",
    "platform_code_search": "platform.code.search",
    "platform_dependency_graph": "platform.dependency.graph",
    "lineage_project_create": "platform.lineage.project.create",
}

_WRITE_STAGES = frozenset({"p2_batch_2_append_only_write", "p2_batch_3_high_risk_request"})


def _load_catalog_resource_keys() -> dict[str, str]:
    catalog_path = Path(__file__).resolve().parent.parent / "mock_data" / "catalog.yaml"
    if not catalog_path.exists():
        return {}
    data = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    resources = data.get("resources") if isinstance(data, dict) else []
    mapping: dict[str, str] = {}
    if not isinstance(resources, list):
        return mapping
    for item in resources:
        if not isinstance(item, dict):
            continue
        resource_key = str(item.get("resource_key") or "").strip()
        scenario = str(item.get("scenario") or "").strip()
        if resource_key and scenario and scenario not in mapping:
            mapping[scenario] = resource_key
    return mapping


_CATALOG_SCENARIO_KEYS = _load_catalog_resource_keys()


def resource_key_for_tool(tool_name: str) -> str:
    if tool_name in _TOOL_RESOURCE_KEYS:
        return _TOOL_RESOURCE_KEYS[tool_name]
    if tool_name in _CATALOG_SCENARIO_KEYS:
        return _CATALOG_SCENARIO_KEYS[tool_name]
    return f"platform.mcp.{tool_name.replace('_', '.')}"


def invoke_mock_tool(tool_name: str, payload: dict[str, Any], *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = metadata or {}
    resource_key = resource_key_for_tool(tool_name)
    scenario = str(payload.get("scenario") or tool_name)
    mock_payload = mock_provider.resolve_payload(resource_key=resource_key, scenario=scenario)
    result: dict[str, Any] = {
        "status": "ok",
        "source": "mock",
        "tool_name": tool_name,
        "resource_key": resource_key,
        "real_execution": False,
    }
    if isinstance(mock_payload, dict):
        result.update(mock_payload)
    if isinstance(payload, dict):
        for key, value in payload.items():
            if value is not None and value != "" and key not in result:
                result[key] = value

    stage = str(meta.get("realization_stage") or "")
    risk = str(meta.get("risk_level") or "low")
    if stage in _WRITE_STAGES or risk == "high":
        result.setdefault("accepted", True)
        result.setdefault("requires_confirmation", bool(meta.get("realization_policy", {}).get("requires_confirmation", True)))
        result.setdefault("mock_only", True)
        if tool_name.endswith("_create") or tool_name.endswith("_register") or tool_name.endswith("_deploy"):
            result.setdefault("id", result.get("training_job_id") or result.get("run_id") or result.get("service_id") or f"mock-{tool_name}")
    if tool_name == "platform_mock_catalog":
        result["catalog"] = mock_provider.list_catalog()
    return result
