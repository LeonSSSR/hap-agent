"""Per-operation hierarchical tool registry."""

from __future__ import annotations

from services.agentic_tool_schema import build_agentic_openai_tools
from services.hierarchical_page_selection import PageRunState, advance_state_after_ui_success
from services.operation_tools import (
    build_hierarchical_operation_openai_tools,
    clear_operation_tool_cache,
    is_operation_tool,
    operation_openai_tool,
    operation_tool_name,
    ui_action_id_from_operation_tool,
)
from services.platform_operations_catalog import clear_catalog_cache


def setup_function() -> None:
    clear_catalog_cache()
    clear_operation_tool_cache()


def test_operation_tool_name_roundtrip() -> None:
    ui_id = "dg.sources.create"
    tool_name = operation_tool_name(ui_id)
    assert tool_name == "hap_op_dg_sources_create"
    assert ui_action_id_from_operation_tool(tool_name) == ui_id
    assert is_operation_tool(tool_name)


def test_every_catalog_operation_has_unique_tool_name() -> None:
    from services.platform_operations_catalog import load_platform_operations

    names: set[str] = set()
    for op in load_platform_operations():
        ui_id = str(op.get("ui_action_id") or "").strip()
        if not ui_id:
            continue
        name = operation_tool_name(ui_id)
        assert name not in names, ui_id
        names.add(name)
        assert ui_action_id_from_operation_tool(name) == ui_id


def test_navigate_phase_exposes_page_root_tools() -> None:
    state = PageRunState()
    tools, ui_ids, phase = build_hierarchical_operation_openai_tools(
        "打开数据源管理",
        identity=None,
        state=state,
        ui_intent="page",
    )
    assert phase == "navigate"
    assert "dg.sources" in ui_ids
    names = {t["function"]["name"] for t in tools}
    assert operation_tool_name("dg.sources") in names
    assert all(is_operation_tool(name) for name in names)


def test_action_phase_exposes_child_tools() -> None:
    state = PageRunState()
    advance_state_after_ui_success(
        state,
        ui_id="lineage.unified",
        tool_name=operation_tool_name("lineage.unified"),
        identity=None,
    )
    tools, ui_ids, phase = build_hierarchical_operation_openai_tools(
        "新建血缘项目",
        identity=None,
        state=state,
        ui_intent="page",
    )
    assert phase == "action"
    assert "lineage.project.create" in ui_ids
    tool = next(t for t in tools if t["function"]["name"] == operation_tool_name("lineage.project.create"))
    assert "创建" in tool["function"]["description"] or "血缘" in tool["function"]["description"]


def test_build_agentic_openai_tools_includes_operation_tools() -> None:
    tools = build_agentic_openai_tools(
        [],
        identity=None,
        user_text="打开数据源",
        page_state=PageRunState(),
        ui_intent="page",
    )
    op_tools = [t for t in tools if is_operation_tool(t["function"]["name"])]
    assert op_tools
    assert operation_tool_name("dg.sources") in {t["function"]["name"] for t in op_tools}


def test_operation_openai_tool_fill_requires_value_param() -> None:
    tool = operation_openai_tool("lineage.project.name.fill", phase="action")
    params = tool["function"]["parameters"]["properties"]["params"]
    assert "value" in params["properties"]
