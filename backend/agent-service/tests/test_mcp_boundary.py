from services.mcp_tool_catalog import build_planning_context
from services.tool_registry import tool_registry


def test_planning_context_has_tools() -> None:
    ctx = build_planning_context("查询服务")
    assert ctx["architecture"] == "mcp_agentic"
    assert len(ctx["allowed_tools"]) > 0


def test_tool_registry_non_empty() -> None:
    assert "platform_service_inventory" in tool_registry.list()
