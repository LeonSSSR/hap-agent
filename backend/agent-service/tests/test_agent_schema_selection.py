"""LLM schema subset selection for faster agent turns."""

from services.identity_service import AgentIdentity, permissions_for_role
from services.mcp_tool_catalog import build_planning_context, select_tools_for_llm
from services.platform_operations_catalog import select_ui_actions_for_llm


def _approver() -> AgentIdentity:
    return AgentIdentity(
        username="approver",
        role="APPROVER",
        permissions=permissions_for_role("APPROVER"),
        auth_source="test",
    )


def test_select_tools_for_intent_is_bounded_subset() -> None:
    identity = _approver()
    selected = select_tools_for_llm("查询审计日志", identity, limit=18)
    allowed = build_planning_context("查询审计日志", identity=identity)["allowed_tools"]
    assert len(allowed) >= len(selected)
    assert len(selected) <= 18
    assert len(selected) > 0


def test_select_ui_actions_for_lineage_create_includes_flow() -> None:
    identity = _approver()
    selected = select_ui_actions_for_llm("血缘新建项目测试67", identity=identity, limit=32)
    assert "lineage.unified" in selected


def test_planning_context_exposes_llm_tools_subset() -> None:
    identity = _approver()
    ctx = build_planning_context("查询审计日志", identity=identity)
    assert len(ctx["llm_tools"]) <= len(ctx["allowed_tools"])
    assert len(ctx["llm_tools"]) > 0
