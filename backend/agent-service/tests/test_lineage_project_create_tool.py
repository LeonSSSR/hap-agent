"""lineage_project_create MCP tool registration."""

from services.identity_service import AgentIdentity, permissions_for_role
from services.mcp_tool_catalog import select_tools_for_llm
from services.tool_registry import tool_registry


def test_lineage_project_create_registered() -> None:
    assert tool_registry.is_allowed("lineage_project_create")
    meta = tool_registry.get("lineage_project_create") or {}
    assert meta.get("risk_level") == "medium"


def test_select_tools_may_include_lineage_project_create() -> None:
    identity = AgentIdentity(
        username="admin",
        role="ADMIN",
        permissions=permissions_for_role("ADMIN"),
        auth_source="test",
    )
    selected = select_tools_for_llm("帮我在血缘中新建项目", identity, limit=18)
    assert "lineage_project_create" in selected
