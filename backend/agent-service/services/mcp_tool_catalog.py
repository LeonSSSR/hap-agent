"""MCP tool catalog for LLM planning (no Skill layer)."""

from __future__ import annotations

from typing import Any

from config import settings
from services.identity_service import AgentIdentity
from services.mcp_registry_loader import collect_registry_tools, load_registry_root
from services.platform_operations_catalog import get_operation, resolve_operations_from_text
from services.tool_registry import tool_registry

AGENT_RUN_ID = "mcp_agent"
MCP_ALL_TOOLS_SENTINEL = "__all_mcp__"

_DANGEROUS_KEYWORDS = ("删除", "清空", "drop", "truncate", "回滚", "覆盖", "强制发布", "force publish")


def list_registered_tool_names() -> list[str]:
    return sorted(tool_registry.list())


def _tool_permission_scope(tool_name: str) -> set[str]:
    meta = tool_registry.normalize_tool_metadata(tool_name, tool_registry.get(tool_name) or {})
    return {str(p).strip() for p in (meta.get("permission_scope") or []) if str(p).strip()}


def identity_allows_tool(identity: AgentIdentity | None, tool_name: str) -> bool:
    if identity is None:
        return True
    required = _tool_permission_scope(tool_name)
    if not required:
        return True
    return required.issubset(identity.permissions)


def filter_tools_for_identity(
    identity: AgentIdentity | None,
    *,
    tool_names: list[str] | None = None,
) -> list[str]:
    names = tool_names or list_registered_tool_names()
    return [name for name in names if identity_allows_tool(identity, name)]


def union_permission_scope(tool_names: list[str]) -> list[str]:
    merged: set[str] = set()
    for name in tool_names:
        merged.update(_tool_permission_scope(name))
    return sorted(merged)


def list_tools_for_prompt(*, identity: AgentIdentity | None = None, limit: int = 96) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for tool_name in filter_tools_for_identity(identity):
        meta = tool_registry.normalize_tool_metadata(tool_name, tool_registry.get(tool_name) or {})
        items.append(
            {
                "tool_name": tool_name,
                "title": str(meta.get("title") or tool_name),
                "description": str(meta.get("description") or "")[:240],
                "risk_level": str(meta.get("risk_level") or "low"),
                "permission_scope": list(meta.get("permission_scope") or []),
            }
        )
        if len(items) >= limit:
            break
    return items


def load_yaml_catalog_entries(*, limit: int = 96) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in collect_registry_tools(load_registry_root()):
        if not isinstance(item, dict):
            continue
        name = str(item.get("tool_name") or "").strip()
        if not name:
            continue
        entries.append(
            {
                "tool_name": name,
                "title": str(item.get("title") or name),
                "description": str(item.get("description") or "")[:240],
                "risk_level": str(item.get("risk_level") or "low"),
                "permission_scope": [str(p) for p in (item.get("permission_scope") or []) if p],
            }
        )
        if len(entries) >= limit:
            break
    return entries


def _score_tool_for_text(tool_name: str, user_input: str, *, boosted: set[str]) -> int:
    meta = tool_registry.normalize_tool_metadata(tool_name, tool_registry.get(tool_name) or {})
    title = str(meta.get("title") or tool_name).lower()
    desc = str(meta.get("description") or "").lower()
    norm_name = tool_name.lower()
    text = user_input.strip().lower()
    score = 0
    if tool_name in boosted:
        score += 12
    if norm_name.replace("_", " ") in text or norm_name in text:
        score += 8
    for token in text.split():
        if len(token) >= 2 and (token in title or token in desc or token in norm_name):
            score += 2
    if any(k in user_input for k in ("血缘", "lineage")) and "lineage" in norm_name:
        score += 6
    if "项目" in user_input and "project" in norm_name:
        score += 5
    if any(k in user_input for k in ("质量", "quality")) and "quality" in norm_name:
        score += 5
    if any(k in user_input for k in ("查询", "列出", "查看", "检查", "统计")) and (
        "query" in norm_name or str(meta.get("risk_level") or "low") == "low"
    ):
        score += 3
    return score


def select_tools_for_llm(
    user_input: str,
    identity: AgentIdentity | None = None,
    *,
    limit: int | None = None,
) -> list[str]:
    """Subset MCP tools for LLM schema; full allowlist still enforced at execution."""
    cap = int(limit if limit is not None else settings.agentic_tools_schema_limit)
    allowed = filter_tools_for_identity(identity)
    if len(allowed) <= cap:
        return allowed

    boosted: set[str] = set()
    for ui_id in resolve_operations_from_text(user_input, limit=24):
        op = get_operation(ui_id) or {}
        for raw in op.get("suggested_mcp_tools") or []:
            name = str(raw).strip()
            if name in allowed:
                boosted.add(name)

    scored = [(_score_tool_for_text(name, user_input, boosted=boosted), name) for name in allowed]
    scored.sort(key=lambda item: (-item[0], item[1]))
    picked = [name for score, name in scored if score > 0][:cap]
    if len(picked) < cap:
        for essential in ("platform_task_status", "platform_audit_query"):
            if essential in allowed and essential not in picked:
                picked.append(essential)
        for _, name in scored:
            if name not in picked:
                picked.append(name)
            if len(picked) >= cap:
                break
    return picked[:cap]


def build_planning_context(
    user_input: str,
    *,
    identity: AgentIdentity | None = None,
) -> dict[str, Any]:
    """MCP agent planning context: allowed tools + permission union."""
    allowed = filter_tools_for_identity(identity)
    selected = select_tools_for_llm(user_input, identity)
    return {
        "agent_run_id": AGENT_RUN_ID,
        "architecture": "mcp_agentic",
        "display_name": "MCP Agent",
        "allowed_tools": allowed,
        "llm_tools": selected,
        "permission_scope": union_permission_scope(allowed),
    }
