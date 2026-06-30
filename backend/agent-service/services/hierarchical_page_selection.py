"""Hierarchical page → action selection for Agent UI tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from config import settings
from services.identity_service import AgentIdentity
from services.platform_operations_catalog import (
    _intent_boost_for_text,
    _ui_action_ancestors,
    filter_ui_actions_for_identity,
    get_operation,
    identity_allows_ui_action,
    load_platform_operations,
    resolve_operations_from_text,
    valid_ui_action_ids,
)

AgentIntentKind = Literal["query", "page", "mixed"]

_QUERY_TOKENS = ("查询", "列出", "查看", "检查", "统计", "获取", "搜索", "健康", "状态", "审计")
_PAGE_TOKENS = ("打开", "跳转", "进入", "前往", "点击", "新建", "创建", "保存", "提交", "发布", "填写", "页面")


@dataclass(slots=True)
class PageRunState:
    active_page_id: str = ""
    navigate_ok: bool = False
    active_parent_id: str = ""


def classify_agent_intent(text: str) -> AgentIntentKind:
    lowered = str(text or "").strip()
    if not lowered:
        return "mixed"
    has_query = any(token in lowered for token in _QUERY_TOKENS)
    has_page = any(token in lowered for token in _PAGE_TOKENS)
    if has_query and not has_page:
        return "query"
    if has_page and not has_query:
        return "page"
    return "mixed"


def is_page_root(ui_action_id: str) -> bool:
    op = get_operation(ui_action_id) or {}
    return bool(op) and not str(op.get("parent_ui_action_id") or "").strip()


def page_root_of(ui_action_id: str) -> str:
    ancestors = _ui_action_ancestors(ui_action_id)
    return ancestors[-1] if ancestors else ""


def _allowed_set(identity: AgentIdentity | None) -> set[str]:
    if identity is None:
        return set(valid_ui_action_ids())
    allowed = set(filter_ui_actions_for_identity(identity))
    if allowed:
        return allowed
    from services.identity_service import permissions_for_role

    fallback = AgentIdentity(
        username=identity.username,
        role=identity.role,
        permissions=permissions_for_role(identity.role),
        auth_source=identity.auth_source,
    )
    return set(filter_ui_actions_for_identity(fallback))


def page_root_ids(*, identity: AgentIdentity | None = None) -> list[str]:
    allowed = _allowed_set(identity)
    roots = [
        str(op.get("ui_action_id") or "").strip()
        for op in load_platform_operations()
        if op.get("ui_action_id") and not op.get("parent_ui_action_id")
    ]
    return sorted(uid for uid in roots if uid in allowed)


def children_of(parent_id: str, *, identity: AgentIdentity | None = None) -> list[str]:
    parent = str(parent_id or "").strip()
    if not parent:
        return []
    allowed = _allowed_set(identity)
    kids = [
        str(op.get("ui_action_id") or "").strip()
        for op in load_platform_operations()
        if str(op.get("parent_ui_action_id") or "").strip() == parent
    ]
    return sorted(uid for uid in kids if uid in allowed)


def has_child_actions(parent_id: str, *, identity: AgentIdentity | None = None) -> bool:
    return bool(children_of(parent_id, identity=identity))


def action_scope_parent(state: PageRunState) -> str:
    return str(state.active_parent_id or state.active_page_id or "").strip()


def select_page_roots_for_llm(
    text: str,
    *,
    identity: AgentIdentity | None = None,
    limit: int | None = None,
) -> list[str]:
    cap = int(limit if limit is not None else settings.agentic_page_roots_schema_limit)
    allowed_roots = set(page_root_ids(identity=identity))
    if len(allowed_roots) <= cap:
        return sorted(allowed_roots)

    picked: list[str] = []
    seen: set[str] = set()

    def add(ui_id: str) -> None:
        if ui_id in allowed_roots and ui_id not in seen:
            seen.add(ui_id)
            picked.append(ui_id)

    for ui_id in resolve_operations_from_text(text, limit=cap):
        root = page_root_of(ui_id)
        if root:
            add(root)

    scored: list[tuple[int, str]] = []
    for ui_id in allowed_roots:
        op = get_operation(ui_id) or {}
        score = _intent_boost_for_text(text, op)
        if str(op.get("action_type") or "") == "navigate":
            score += 2
        scored.append((score, ui_id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    for score, ui_id in scored:
        if score <= 0 and picked:
            break
        add(ui_id)
        if len(picked) >= cap:
            break
    if not picked:
        for _, ui_id in scored[:cap]:
            add(ui_id)
            if len(picked) >= cap:
                break
    return picked[:cap]


def select_page_actions_for_llm(
    text: str,
    *,
    scope_parent_id: str,
    identity: AgentIdentity | None = None,
    limit: int | None = None,
) -> list[str]:
    cap = int(limit if limit is not None else settings.agentic_page_actions_schema_limit)
    parent = str(scope_parent_id or "").strip()
    if not parent:
        return []
    allowed_children = set(children_of(parent, identity=identity))
    if len(allowed_children) <= cap:
        return sorted(allowed_children)

    picked: list[str] = []
    seen: set[str] = set()

    def add(ui_id: str) -> None:
        if ui_id in allowed_children and ui_id not in seen:
            seen.add(ui_id)
            picked.append(ui_id)

    for ui_id in resolve_operations_from_text(text, limit=cap * 2):
        if str((get_operation(ui_id) or {}).get("parent_ui_action_id") or "") == parent:
            add(ui_id)
        if len(picked) >= cap:
            return picked[:cap]

    scored: list[tuple[int, str]] = []
    lowered = text.lower()
    create_tokens = ("创建", "新建", "项目", "名称", "数据类型", "text", "txt", "tabular")
    has_create_intent = any(token in lowered or token in text for token in create_tokens)
    for ui_id in allowed_children:
        op = get_operation(ui_id) or {}
        score = _intent_boost_for_text(text, op)
        label = str(op.get("label") or "").strip().lower()
        if label and label in lowered:
            score += 4
        if has_create_intent and ui_id.startswith("lineage.project."):
            if ui_id in {
                "lineage.project.create",
                "lineage.project.name.fill",
                "lineage.project.datatype.select",
                "lineage.project.submit",
            }:
                score += 12
            elif ui_id == "lineage.project.create.panel":
                score += 4
        scored.append((score, ui_id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    for score, ui_id in scored:
        if score <= 0 and picked:
            break
        add(ui_id)
        if len(picked) >= cap:
            break
    if not picked:
        for _, ui_id in scored[:cap]:
            add(ui_id)
    return picked[:cap]


def validate_navigate_page(page_id: str, *, identity: AgentIdentity | None) -> str | None:
    ui_id = str(page_id or "").strip()
    if not ui_id or ui_id not in valid_ui_action_ids():
        return "invalid page_id"
    if not is_page_root(ui_id):
        return "not a page root"
    if not identity_allows_ui_action(identity, ui_id):
        return "permission_denied"
    return None


def validate_page_action(action_id: str, *, state: PageRunState, identity: AgentIdentity | None) -> str | None:
    ui_id = str(action_id or "").strip()
    if not state.navigate_ok or not state.active_page_id:
        return "navigate_required"
    if not ui_id or ui_id not in valid_ui_action_ids():
        return "invalid action_id"
    if is_page_root(ui_id):
        return "page roots require navigation phase"
    scope = action_scope_parent(state)
    parent = str((get_operation(ui_id) or {}).get("parent_ui_action_id") or "").strip()
    if parent != scope:
        return f"action not under current scope {scope}"
    if not identity_allows_ui_action(identity, ui_id):
        return "permission_denied"
    return None


def no_match_message(*, phase: str, scope_label: str = "") -> str:
    if phase == "navigate":
        return "未找到与当前意图匹配的平台页面，请换一种说法或指定模块（如数据源、血缘、训练）。"
    if phase == "action":
        label = f"「{scope_label}」" if scope_label else "当前页面"
        return f"在{label}下未找到匹配的操作，请说明具体要点击的按钮或步骤。"
    return "未找到可执行的页面操作。"


def resolve_ui_tool_phase(state: PageRunState, *, ui_intent: AgentIntentKind) -> Literal["navigate", "action", "none"]:
    if ui_intent == "query":
        return "none"
    if not state.navigate_ok:
        return "navigate"
    return "action"


def build_hierarchical_ui_tool_ids(
    text: str,
    *,
    identity: AgentIdentity | None,
    state: PageRunState,
    ui_intent: AgentIntentKind,
) -> tuple[list[str], list[str], Literal["navigate", "action", "none"]]:
    phase = resolve_ui_tool_phase(state, ui_intent=ui_intent)
    if phase == "none":
        return [], [], "none"
    if phase == "navigate":
        return select_page_roots_for_llm(text, identity=identity), [], "navigate"
    scope = action_scope_parent(state)
    return [], select_page_actions_for_llm(text, identity=identity, scope_parent_id=scope), "action"


def advance_state_after_ui_success(
    state: PageRunState,
    *,
    ui_id: str,
    tool_name: str,
    identity: AgentIdentity | None,
) -> None:
    _ = tool_name
    if is_page_root(ui_id):
        state.active_page_id = ui_id
        state.navigate_ok = True
        state.active_parent_id = ""
        return
    if has_child_actions(ui_id, identity=identity):
        state.active_parent_id = ui_id
    elif state.active_parent_id == ui_id:
        state.active_parent_id = ""
    elif state.active_parent_id and not has_child_actions(state.active_parent_id, identity=identity):
        state.active_parent_id = ""
