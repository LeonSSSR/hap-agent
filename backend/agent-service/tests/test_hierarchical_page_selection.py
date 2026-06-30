"""Hierarchical page → action selection."""

from __future__ import annotations

from services.hierarchical_page_selection import (
    PageRunState,
    advance_state_after_ui_success,
    build_hierarchical_ui_tool_ids,
    classify_agent_intent,
    no_match_message,
    select_page_actions_for_llm,
    select_page_roots_for_llm,
    validate_navigate_page,
    validate_page_action,
)
from services.identity_service import AgentIdentity
from services.operation_tools import operation_tool_name
from services.platform_operations_catalog import clear_catalog_cache
from p6.security_policy import permissions_for_role


def setup_function() -> None:
    clear_catalog_cache()


def test_classify_agent_intent() -> None:
    assert classify_agent_intent("查询平台健康") == "query"
    assert classify_agent_intent("打开数据源页面") == "page"
    assert classify_agent_intent("打开数据源并查询列表") == "mixed"


def test_select_page_roots_includes_dg_sources() -> None:
    roots = select_page_roots_for_llm("打开数据源管理", identity=None)
    assert "dg.sources" in roots


def test_validate_navigate_requires_page_root() -> None:
    assert validate_navigate_page("dg.sources", identity=None) is None
    assert validate_navigate_page("lineage.project.create", identity=None) == "not a page root"


def test_page_action_requires_navigate_first() -> None:
    state = PageRunState()
    assert validate_page_action("lineage.project.create", state=state, identity=None) == "navigate_required"
    state.navigate_ok = True
    state.active_page_id = "lineage.unified"
    assert validate_page_action("lineage.project.create", state=state, identity=None) is None


def test_build_tools_phase_navigate_then_action() -> None:
    state = PageRunState()
    roots, actions, phase = build_hierarchical_ui_tool_ids(
        "打开血缘并新建项目",
        identity=None,
        state=state,
        ui_intent="page",
    )
    assert phase == "navigate"
    assert roots
    assert not actions

    advance_state_after_ui_success(
        state,
        ui_id="lineage.unified",
        tool_name=operation_tool_name("lineage.unified"),
        identity=None,
    )
    _, actions, phase = build_hierarchical_ui_tool_ids(
        "新建血缘项目",
        identity=None,
        state=state,
        ui_intent="page",
    )
    assert phase == "action"
    assert actions
    assert "lineage.project.create" in select_page_actions_for_llm(
        "新建项目",
        scope_parent_id="lineage.unified",
        identity=None,
    )


def test_query_intent_skips_ui_tools() -> None:
    state = PageRunState()
    roots, actions, phase = build_hierarchical_ui_tool_ids(
        "查询服务健康",
        identity=None,
        state=state,
        ui_intent="query",
    )
    assert phase == "none"
    assert roots == []
    assert actions == []


def test_no_match_messages() -> None:
    assert "页面" in no_match_message(phase="navigate")
    assert "当前页面" in no_match_message(phase="action")


def test_sparse_identity_still_gets_navigate_candidates() -> None:
    sparse = AgentIdentity(username="u", role="APPROVER", permissions=set(), auth_source="jwt")
    roots = select_page_roots_for_llm("数据源", identity=sparse)
    assert roots
    assert validate_navigate_page(roots[0], identity=None) is None


def test_super_admin_sees_lineage_project_write_actions() -> None:
    identity = AgentIdentity(
        username="admin",
        role="SUPER_ADMIN",
        permissions=permissions_for_role("SUPER_ADMIN"),
        auth_source="jwt",
    )
    assert "project.write" in identity.permissions
    actions = select_page_actions_for_llm(
        "创建项目 名称测试数据 格式text",
        scope_parent_id="lineage.unified",
        identity=identity,
    )
    for ui_id in (
        "lineage.project.create",
        "lineage.project.name.fill",
        "lineage.project.datatype.select",
        "lineage.project.submit",
    ):
        assert ui_id in actions
