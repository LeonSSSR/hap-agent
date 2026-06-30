from services.operation_tools import operation_openai_tool, operation_tool_name
from services.platform_operations_catalog import (
    load_platform_operations,
    valid_ui_action_ids,
)


def test_catalog_loads() -> None:
    ops = load_platform_operations()
    assert len(ops) >= 30
    assert "dg.sources" in valid_ui_action_ids()


def test_operation_tool_schema_for_page_root() -> None:
    tool = operation_openai_tool("dg.sources", phase="navigate")
    assert tool["function"]["name"] == operation_tool_name("dg.sources")
    assert "数据源" in tool["function"]["description"]
