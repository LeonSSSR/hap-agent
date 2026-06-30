"""Readable tool result formatting for agent output."""

from __future__ import annotations

from services.agentic_output_format import (
    format_result_preview,
    format_tool_result_for_llm,
    format_tool_result_for_user,
)


def test_format_service_inventory_for_llm() -> None:
    payload = {
        "summary": "平台服务健康检测完成",
        "healthy": 2,
        "down": 1,
        "services": [
            {"name": "agent-service", "reachable": True},
            {"name": "core-api", "reachable": False, "status": "down"},
        ],
    }
    text = format_tool_result_for_llm(payload, tool_name="platform_service_inventory")
    assert "平台服务健康检测完成" in text
    assert "agent-service" in text
    assert "健康 2" in text


def test_format_page_result_preview() -> None:
    preview = format_result_preview({"success": True, "message": "已打开数据源管理"})
    assert "已打开数据源管理" in preview
    assert "{" not in preview


def test_format_user_summary_from_inventory() -> None:
    text = format_tool_result_for_user(
        {
            "summary": "平台服务健康检测完成",
            "healthy": 1,
            "down": 0,
            "services": [{"name": "agent-service", "reachable": True}],
        }
    )
    assert "平台服务健康检测完成" in text
    assert "agent-service" in text
    assert "主要服务状态" in text
