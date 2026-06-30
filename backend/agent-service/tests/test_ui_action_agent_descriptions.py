"""Agent-facing descriptions for platform ui_action catalog."""

from __future__ import annotations

from services.operation_tools import build_hierarchical_operation_openai_tools, operation_openai_tool
from services.hierarchical_page_selection import PageRunState
from services.platform_operations_catalog import (
    clear_catalog_cache,
    format_ui_actions_glossary,
    operation_agent_description,
)


def setup_function() -> None:
    clear_catalog_cache()


def test_operation_agent_description_synthesizes_from_catalog() -> None:
    text = operation_agent_description("dg.sources")
    assert "数据源" in text
    assert "dg.sources" not in text or "数据源" in text


def test_operation_agent_description_includes_parent_context() -> None:
    text = operation_agent_description("dg.schedule.create")
    assert "新建" in text
    assert "调度" in text


def test_navigate_operation_tool_includes_page_context() -> None:
    tool = operation_openai_tool("dg.sources", phase="navigate")
    desc = tool["function"]["description"]
    assert "dg.sources" in desc
    assert "数据源" in desc
    assert tool["function"]["name"] == "hap_op_dg_sources"


def test_page_action_operation_tool_includes_action_context() -> None:
    tool = operation_openai_tool("lineage.project.create", phase="action")
    desc = tool["function"]["description"]
    assert "lineage.project.create" in desc
    assert "创建" in desc or "血缘" in desc


def test_hierarchical_tools_include_multiple_operation_names() -> None:
    tools, ui_ids, phase = build_hierarchical_operation_openai_tools(
        "打开数据源或血缘",
        identity=None,
        state=PageRunState(),
        ui_intent="page",
    )
    assert phase == "navigate"
    names = {t["function"]["name"] for t in tools}
    assert "hap_op_dg_sources" in names or "hap_op_lineage_unified" in names
    assert len(ui_ids) == len(tools)


def test_glossary_respects_total_char_budget() -> None:
    ids = [f"op.test.{idx}" for idx in range(80)]
    text = format_ui_actions_glossary(ids, max_chars=400, per_item_max_chars=40)
    assert len(text) <= 450
    assert "…" in text
