"""HAP SPA page operations catalog (from data/platform_operations_catalog.json)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from config import settings
from services.identity_service import AgentIdentity

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "platform_operations_catalog.json"
HAP_UI_ACTION_TOOL = "hap_ui_action"

_DEFAULT_READ_SCOPE = ["workflow.read"]
_MODULE_READ_SCOPE: dict[str, list[str]] = {
    "data_governance": ["workflow.read"],
    "data_processing": ["workflow.read"],
    "model_development": ["workflow.read"],
    "model_application": ["workflow.read"],
    "lineage": ["workflow.read"],
    "platform": ["workflow.read"],
    "project_operations": ["workflow.read", "platform.read"],
    "project_development": ["workflow.read", "ml_pipeline.read", "training.read"],
}

_MODULE_LABELS: dict[str, str] = {
    "data_governance": "数据治理",
    "data_processing": "数据处理",
    "model_development": "模型开发",
    "model_application": "模型应用",
    "lineage": "血缘",
    "platform": "平台运维",
    "project_operations": "项目运营",
    "project_development": "项目开发",
}

_ACTION_TYPE_HINTS: dict[str, str] = {
    "navigate": "打开页面",
    "click": "点击按钮",
    "fill": "填写输入",
    "highlight": "高亮元素",
    "open_panel": "打开面板",
    "page_action": "页面内操作",
}

_MODULE_SUGGESTED_MCP_TOOLS: dict[str, list[str]] = {
    "data_governance": ["dataset_catalog_query", "platform_lineage_query"],
    "data_processing": ["data_cleaning_job_list", "augmentation_job_list", "feature_engineering_catalog_query"],
    "model_development": ["training_job_status", "algorithm_catalog_query", "model_versions_list"],
    "model_application": ["inference_services_list", "inference_service_status", "model_monitor_query"],
    "lineage": ["platform_lineage_query"],
    "platform": ["platform_service_inventory", "platform_audit_query"],
    "project_operations": ["platform_task_status", "platform_audit_query"],
    "project_development": ["training_job_status", "model_evaluation_query"],
}

# Dynamic detail routes → list/entry routes when :id param is absent (matches Umi routes).
_ROUTE_LIST_FALLBACKS: dict[str, str] = {
    "/data-governance/datasets/edit/:id": "/data-governance/datasets",
    "/data-processing/labeling/projects/:id": "/data-processing/labeling?tab=projects",
    "/data-governance/annotation/projects/:id": "/data-processing/labeling?tab=projects",
}

# Routes with no list parent — skip auto-navigation without explicit params.id.
_ROUTE_NO_AUTO_NAV: frozenset[str] = frozenset(
    {
        "/data-governance/projects/:id",
    }
)


def _normalize_route_params(params: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(params, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in params.items():
        token = str(key or "").strip()
        if not token:
            continue
        text = str(value or "").strip()
        if text:
            normalized[token] = text
    return normalized


def apply_route_params(route: str, params: dict[str, Any] | None = None) -> str:
    """Substitute :param segments; return concrete path or list fallback."""
    raw = str(route or "").strip()
    if not raw:
        return ""
    path_only = raw.split("?")[0]
    query = raw.split("?", 1)[1] if "?" in raw else ""
    resolved = path_only
    route_params = _normalize_route_params(params)
    for key, value in route_params.items():
        resolved = resolved.replace(f":{key}", value)
    if ":" not in resolved:
        return f"{resolved}?{query}" if query else resolved
    if path_only in _ROUTE_NO_AUTO_NAV:
        return ""
    fallback = _ROUTE_LIST_FALLBACKS.get(path_only)
    if not fallback:
        prefix = path_only.split("/:")[0]
        for pattern, target in _ROUTE_LIST_FALLBACKS.items():
            if pattern.startswith(prefix) or prefix.startswith(pattern.split("/:")[0]):
                fallback = target
                break
    return fallback or ""


_DEFAULT_MCP_BINDINGS: dict[str, dict[str, Any]] = {
    "dg.datasets": {"mcp_tools": ["dataset_catalog_query"], "mode": "readonly_query"},
    "lineage.unified": {"mcp_tools": ["platform_lineage_query"], "mode": "readonly_query"},
    "ml.training.submit": {"mcp_tools": ["training_job_status", "training_job_create"], "mode": "read_write"},
    "ml.training.monitor": {"mcp_tools": ["training_job_status"], "mode": "readonly_query"},
    "ma.inference.services": {"mcp_tools": ["inference_services_list", "inference_service_status"], "mode": "readonly_query"},
    "ma.model.versions": {"mcp_tools": ["model_versions_list", "model_evaluation_query"], "mode": "readonly_query"},
    "ma.model.monitor": {"mcp_tools": ["model_monitor_query"], "mode": "readonly_query"},
    "agent.workflow": {"mcp_tools": ["platform_audit_query", "platform_task_status"], "mode": "readonly_query"},
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _normalize_operation(raw: dict[str, Any], *, default_action_type: str = "navigate") -> dict[str, Any]:
    op = dict(raw)
    ui_id = str(op.get("ui_action_id") or "").strip()
    if not ui_id:
        return {}
    op["ui_action_id"] = ui_id
    op["action_type"] = str(op.get("action_type") or default_action_type).strip().lower()
    risk = str(op.get("risk_level") or "low").strip().lower()
    op["risk_level"] = risk if risk in {"low", "medium", "high"} else "low"
    scope = op.get("permission_scope")
    if not isinstance(scope, list) or not scope:
        module = str(op.get("module") or "").strip()
        base = list(_MODULE_READ_SCOPE.get(module, _DEFAULT_READ_SCOPE))
        if risk == "medium":
            base.append("ml.lifecycle.execute")
        if risk == "high":
            base.extend(["model.publish.approve", "inference.deploy.write"])
        op["permission_scope"] = sorted({str(item).strip() for item in base if str(item).strip()})
    else:
        op["permission_scope"] = [str(item).strip() for item in scope if str(item).strip()]
    suggested = op.get("suggested_mcp_tools")
    if not isinstance(suggested, list) or not suggested:
        module = str(op.get("module") or "").strip()
        op["suggested_mcp_tools"] = list(_MODULE_SUGGESTED_MCP_TOOLS.get(module, []))
    return op


@lru_cache(maxsize=1)
def load_mcp_bindings() -> dict[str, dict[str, Any]]:
    bindings = _read_json(CATALOG_PATH).get("mcp_bindings")
    result: dict[str, dict[str, Any]] = {key: dict(value) for key, value in _DEFAULT_MCP_BINDINGS.items()}
    if not isinstance(bindings, list):
        return result
    for item in bindings:
        if not isinstance(item, dict):
            continue
        ui_id = str(item.get("ui_action_id") or "").strip()
        if ui_id:
            result[ui_id] = item
    return result


@lru_cache(maxsize=1)
def load_platform_operations() -> list[dict[str, Any]]:
    operations = _read_json(CATALOG_PATH).get("operations")
    if not isinstance(operations, list):
        return []
    merged = [
        normalized
        for item in operations
        if isinstance(item, dict)
        for normalized in [_normalize_operation(item, default_action_type="navigate")]
        if normalized
    ]
    return sorted(merged, key=lambda item: str(item.get("ui_action_id") or ""))


@lru_cache(maxsize=1)
def valid_ui_action_ids() -> frozenset[str]:
    return frozenset(str(op.get("ui_action_id") or "").strip() for op in load_platform_operations() if op.get("ui_action_id"))


def get_operation(ui_action_id: str) -> dict[str, Any] | None:
    needle = str(ui_action_id or "").strip()
    if not needle:
        return None
    for op in load_platform_operations():
        if str(op.get("ui_action_id") or "") == needle:
            return op
    return None


def operation_risk_level(ui_action_id: str) -> str:
    op = get_operation(ui_action_id) or {}
    explicit = str(op.get("risk_level") or "").strip().lower()
    if explicit in {"low", "medium", "high"}:
        return explicit
    return "low"


def operation_permission_scope(ui_action_id: str) -> list[str]:
    op = get_operation(ui_action_id) or {}
    scope = op.get("permission_scope")
    if isinstance(scope, list):
        return [str(item).strip() for item in scope if str(item).strip()]
    return list(_DEFAULT_READ_SCOPE)


def operation_action_type(ui_action_id: str) -> str:
    op = get_operation(ui_action_id) or {}
    action = str(op.get("action_type") or "navigate").strip().lower()
    if action in {"navigate", "highlight", "click", "fill", "scrollintoview"}:
        return "scrollIntoView" if action == "scrollintoview" else action
    return "navigate"


def identity_allows_ui_action(identity: AgentIdentity | None, ui_action_id: str) -> bool:
    if identity is None:
        return True
    required = set(operation_permission_scope(ui_action_id))
    if not required:
        return True
    return required.issubset(identity.permissions)


def filter_ui_actions_for_identity(identity: AgentIdentity | None) -> list[str]:
    return [
        str(op.get("ui_action_id") or "")
        for op in load_platform_operations()
        if op.get("ui_action_id") and identity_allows_ui_action(identity, str(op["ui_action_id"]))
    ]


def operation_agent_description(
    ui_action_id: str,
    *,
    max_keywords: int = 4,
) -> str:
    """Human-readable summary for LLM tool glossary (catalog description overrides synthesis)."""
    op = get_operation(ui_action_id) or {}
    if not op:
        return str(ui_action_id or "").strip()

    explicit = str(op.get("agent_description") or op.get("description") or "").strip()
    if explicit:
        return explicit

    label = str(op.get("label") or ui_action_id).strip()
    module = str(op.get("module") or "").strip()
    module_label = _MODULE_LABELS.get(module, module)
    action_type = operation_action_type(ui_action_id)
    action_hint = _ACTION_TYPE_HINTS.get(action_type, action_type)
    route = str(op.get("route") or "").strip()
    parent_id = str(op.get("parent_ui_action_id") or "").strip()
    parent_label = ""
    if parent_id:
        parent_label = str((get_operation(parent_id) or {}).get("label") or parent_id).strip()

    keywords = [str(k).strip() for k in (op.get("keywords") or []) if str(k).strip()][:max_keywords]
    parts: list[str] = [label]
    if parent_label:
        parts.append(f"位于「{parent_label}」")
    if module_label:
        parts.append(module_label)
    if action_hint:
        parts.append(action_hint)
    if route:
        parts.append(route)
    if keywords:
        parts.append("关键词：" + "、".join(keywords))
    risk = operation_risk_level(ui_action_id)
    if risk in {"medium", "high"}:
        parts.append(f"风险{risk}")
    return "；".join(parts)


def format_ui_actions_glossary(
    ui_action_ids: list[str],
    *,
    id_param: str = "ui_action_id",
    max_chars: int | None = None,
    per_item_max_chars: int | None = None,
) -> str:
    """Build a compact id → description glossary for OpenAI tool descriptions."""
    cap = int(max_chars if max_chars is not None else settings.agentic_ui_action_glossary_max_chars)
    item_cap = int(
        per_item_max_chars if per_item_max_chars is not None else settings.agentic_ui_action_desc_max_chars
    )
    header = f"本轮可选 {id_param}（须精确匹配）："
    lines: list[str] = []
    used = len(header) + 1
    for ui_id in sorted({str(uid).strip() for uid in ui_action_ids if str(uid).strip()}):
        summary = operation_agent_description(ui_id)
        if len(summary) > item_cap:
            summary = summary[: item_cap - 1] + "…"
        line = f"- {ui_id}：{summary}"
        if used + len(line) + 1 > cap:
            lines.append("- …（更多候选见 catalog，请结合用户意图选择最相关 id）")
            break
        lines.append(line)
        used += len(line) + 1
    if not lines:
        return header
    return header + "\n" + "\n".join(lines)


def list_operations_for_prompt(*, identity: AgentIdentity | None = None, max_keywords: int = 6, limit: int = 96) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for op in load_platform_operations():
        ui_id = str(op.get("ui_action_id") or "")
        if not ui_id:
            continue
        if identity is not None and not identity_allows_ui_action(identity, ui_id):
            continue
        keywords = [str(k) for k in (op.get("keywords") or []) if k][:max_keywords]
        items.append(
            {
                "ui_action_id": ui_id,
                "label": str(op.get("label") or ""),
                "description": operation_agent_description(ui_id, max_keywords=max_keywords),
                "module": str(op.get("module") or ""),
                "route": str(op.get("route") or ""),
                "action_type": operation_action_type(ui_id),
                "risk_level": operation_risk_level(ui_id),
                "permission_scope": operation_permission_scope(ui_id),
                "keywords": keywords,
            }
        )
        if len(items) >= limit:
            break
    return items


_INTENT_PROFILES: tuple[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]], ...] = (
    (("血缘", "lineage", "上下游", "影响", "表名"), ("lineage",), ("lineage.", "dg.lineage")),
    (("训练", "training", "算法", "katib", "调优", "notebook"), ("model_development",), ("ml.training", "md.", "ml.")),
    (("推理", "inference", "部署", "在线预测", "服务发布"), ("model_application",), ("ma.", "ma.inference", "ma.deploy")),
    (("数据源", "数据集", "dataset", "同步", "调度"), ("data_governance",), ("dg.sources", "dg.datasets", "dg.sync", "dg.")),
    (("清洗", "增强", "标注", "质量", "探索"), ("data_processing",), ("dp.",)),
    (("审计", "任务状态", "服务健康"), ("platform", "project_operations"), ("agent.workflow",)),
)

_ESSENTIAL_UI_BY_INTENT: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("血缘", "lineage"), ("lineage.unified", "lineage.navigate", "lineage.tableInput")),
    (("数据源", "dataset"), ("dg.sources",)),
    (("训练", "training"), ("ml.training.submit", "ml.training.monitor")),
    (("推理", "inference", "部署"), ("ma.inference.services",)),
)


def _intent_boost_for_text(text: str, op: dict[str, Any]) -> int:
    lowered = str(text or "").lower()
    ui_id = str(op.get("ui_action_id") or "")
    module = str(op.get("module") or "")
    boost = 0
    for keywords, modules, prefixes in _INTENT_PROFILES:
        if not any(kw.lower() in lowered or kw in text for kw in keywords):
            continue
        if module in modules:
            boost += 8
        if any(ui_id.startswith(prefix) for prefix in prefixes):
            boost += 6
        label = str(op.get("label") or "").lower()
        if any(kw.lower() in label for kw in keywords):
            boost += 3
    return boost


def _essential_ui_for_text(text: str) -> list[str]:
    lowered = str(text or "").lower()
    result: list[str] = []
    for keywords, ui_ids in _ESSENTIAL_UI_BY_INTENT:
        if any(kw.lower() in lowered or kw in text for kw in keywords):
            result.extend(ui_ids)
    return result


def operation_effective_route(ui_action_id: str, *, params: dict[str, Any] | None = None) -> str:
    """Resolve a navigable route for page actions (supports :id via params or list fallback)."""
    for ancestor in _ui_action_ancestors(ui_action_id):
        op = get_operation(ancestor) or {}
        route = str(op.get("route") or "").strip()
        if route and ":" not in route.split("?")[0]:
            return route
    op = get_operation(ui_action_id) or {}
    route = str(op.get("route") or "").strip()
    if not route:
        return ""
    if ":" not in route.split("?")[0]:
        return route
    return apply_route_params(route, params)


def _ui_action_ancestors(ui_action_id: str) -> list[str]:
    chain: list[str] = []
    current = str(ui_action_id or "").strip()
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        chain.append(current)
        op = get_operation(current) or {}
        current = str(op.get("parent_ui_action_id") or "").strip()
    return chain


def select_ui_actions_for_llm(
    text: str,
    *,
    identity: AgentIdentity | None = None,
    limit: int | None = None,
) -> list[str]:
    """Subset hap_ui_action enum for LLM schema; runtime still validates full catalog."""
    cap = int(limit if limit is not None else settings.agentic_ui_actions_schema_limit)
    if identity is None:
        allowed_set = set(valid_ui_action_ids())
    else:
        allowed_set = set(filter_ui_actions_for_identity(identity))
        if not allowed_set:
            from services.identity_service import permissions_for_role

            fallback_identity = AgentIdentity(
                username=identity.username,
                role=identity.role,
                permissions=permissions_for_role(identity.role),
                auth_source=identity.auth_source,
            )
            allowed_set = set(filter_ui_actions_for_identity(fallback_identity))
    if len(allowed_set) <= cap:
        return sorted(allowed_set)

    picked: list[str] = []
    seen: set[str] = set()

    def add(ui_id: str) -> None:
        if ui_id in allowed_set and ui_id not in seen:
            seen.add(ui_id)
            picked.append(ui_id)

    for essential in _essential_ui_for_text(text):
        add(essential)

    for ui_id in resolve_operations_from_text(text, limit=cap):
        for ancestor in _ui_action_ancestors(ui_id):
            add(ancestor)
            if len(picked) >= cap:
                return picked[:cap]

    lowered = text.lower()
    scored: list[tuple[int, str]] = []
    for ui_id in allowed_set:
        op = get_operation(ui_id) or {}
        score = _intent_boost_for_text(text, op)
        label = str(op.get("label") or "").strip().lower()
        if label and label in lowered:
            score += 4
        for kw in op.get("keywords") or []:
            token = str(kw).strip().lower()
            if len(token) >= 2 and token in lowered:
                score += 2
        module = str(op.get("module") or "").lower()
        if module and module in lowered:
            score += 1
        if str(op.get("action_type") or "") == "navigate":
            score += 1
        scored.append((score, ui_id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    for _, ui_id in scored:
        add(ui_id)
        if len(picked) >= cap:
            break
    return picked[:cap]


def hap_ui_action_openai_tool(
    *,
    identity: AgentIdentity | None = None,
    ui_action_ids: list[str] | None = None,
) -> dict[str, Any]:
    if ui_action_ids is not None:
        if identity is None:
            allowed_set = set(valid_ui_action_ids())
        else:
            allowed_set = set(filter_ui_actions_for_identity(identity))
            if not allowed_set:
                from services.identity_service import permissions_for_role

                fallback_identity = AgentIdentity(
                    username=identity.username,
                    role=identity.role,
                    permissions=permissions_for_role(identity.role),
                    auth_source=identity.auth_source,
                )
                allowed_set = set(filter_ui_actions_for_identity(fallback_identity))
        ids = sorted(uid for uid in ui_action_ids if uid in allowed_set)
    elif identity is None:
        ids = sorted(valid_ui_action_ids())
    else:
        ids = sorted(filter_ui_actions_for_identity(identity))
        if not ids:
            # Safety: never expose an empty enum to the LLM (breaks tool selection UX).
            from services.identity_service import permissions_for_role

            fallback_identity = AgentIdentity(
                username=identity.username,
                role=identity.role,
                permissions=permissions_for_role(identity.role),
                auth_source=identity.auth_source,
            )
            ids = sorted(filter_ui_actions_for_identity(fallback_identity))
    ui_action_id_schema: dict[str, Any] = {
        "type": "string",
        "description": "platform_operations_catalog 中的 ui_action_id（含页面级与按钮级）",
    }
    if ids:
        ui_action_id_schema["enum"] = ids
    return {
        "type": "function",
        "function": {
            "name": HAP_UI_ACTION_TOOL,
            "description": (
                "在 HAP 平台 SPA 内执行已登记的页面操作（跳转、高亮、点击按钮等）。"
                "仅可调用当前账号有权限的操作。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ui_action_id": ui_action_id_schema,
                    "params": {
                        "type": "object",
                        "description": "可选页面参数（fill 的 value、动态路由的 id）",
                        "properties": {
                            "value": {"type": "string", "description": "fill 动作填入的文本"},
                            "id": {"type": "string", "description": "动态路由占位符（如 datasets/edit/:id）"},
                        },
                    },
                },
                "required": ["ui_action_id"],
            },
        },
    }


def resolve_operations_from_text(text: str, *, limit: int = 5) -> list[str]:
    lowered = text.lower()
    scored: list[tuple[int, str]] = []
    for op in load_platform_operations():
        ui_id = str(op.get("ui_action_id") or "").strip()
        if not ui_id:
            continue
        score = _intent_boost_for_text(text, op)
        label = str(op.get("label") or "").strip().lower()
        if label and label in lowered:
            score += 4
        for kw in op.get("keywords") or []:
            token = str(kw).strip().lower()
            if len(token) >= 2 and token in lowered:
                score += 2
        if score > 0:
            scored.append((score, ui_id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    seen: set[str] = set()
    result: list[str] = []
    for _, ui_id in scored:
        if ui_id in seen:
            continue
        seen.add(ui_id)
        result.append(ui_id)
        if len(result) >= limit:
            break
    return result


def clear_catalog_cache() -> None:
    load_mcp_bindings.cache_clear()
    load_platform_operations.cache_clear()
    valid_ui_action_ids.cache_clear()
    from services.operation_tools import clear_operation_tool_cache

    clear_operation_tool_cache()
