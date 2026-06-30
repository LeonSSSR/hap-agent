"""Required tool arguments must come from the user; runner blocks incomplete calls."""

from __future__ import annotations

from services.agentic_clarify_tool import missing_required_tool_arguments


def test_lineage_project_create_requires_name_and_datatype() -> None:
    assert missing_required_tool_arguments("lineage_project_create", {}) == ["name", "dataType"]
    assert missing_required_tool_arguments("lineage_project_create", {"name": "测试38"}) == ["dataType"]
    assert missing_required_tool_arguments(
        "lineage_project_create",
        {"name": "测试38", "dataType": "TABULAR"},
    ) == []
    assert missing_required_tool_arguments(
        "lineage_project_create",
        {"name": "测试38", "dataType": "UNKNOWN"},
    ) == ["dataType"]
