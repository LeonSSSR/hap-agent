"""Format MCP / page tool payloads for LLM context and user-facing previews."""

from __future__ import annotations

import json
from typing import Any

from services.operation_tools import is_operation_tool
from services.platform_operations_catalog import HAP_UI_ACTION_TOOL


def _as_dict(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _service_status_line(svc: dict[str, Any]) -> str:
    name = str(svc.get("name") or svc.get("service") or "未知服务")
    if svc.get("reachable") is True:
        status = "正常"
    elif svc.get("reachable") is False:
        status = "不可达"
    else:
        status = str(svc.get("status") or "未知")
    return f"- {name}：{status}"


def format_tool_result_for_llm(payload: Any, *, tool_name: str = "") -> str:
    """Compress tool JSON into readable text for the next LLM turn."""
    data = payload if isinstance(payload, dict) else _as_dict(payload)
    if data is None:
        text = str(payload)
        return text[:800] + ("…" if len(text) > 800 else "")

    if data.get("error"):
        return f"工具执行失败：{data['error']}"

    if data.get("mock_only") or data.get("real_execution") is False:
        name = str(data.get("name") or "").strip()
        if name and (data.get("project_id") or tool_name == "lineage_project_create"):
            return (
                "【模拟执行】项目创建请求未真实写入平台数据库（mock_only=true）。"
                f" 请勿向用户声称项目已创建。参数：name={name}，dataType={data.get('dataType') or '-'}"
            )

    if data.get("success") is False:
        return f"操作失败：{data.get('message') or data.get('error') or '未知原因'}"

    message = str(data.get("message") or "").strip()
    if message and (data.get("success") is True or is_operation_tool(tool_name) or tool_name == HAP_UI_ACTION_TOOL):
        return f"页面操作结果：{message}"

    summary = str(data.get("summary") or "").strip()
    services = data.get("services")
    if summary or (isinstance(services, list) and services):
        parts: list[str] = []
        if summary:
            parts.append(summary)
        healthy = data.get("healthy")
        down = data.get("down")
        if healthy is not None:
            tail = f"健康 {healthy} 项"
            if down:
                tail += f"，异常 {down} 项"
            parts.append(tail)
        if isinstance(services, list):
            for svc in services[:10]:
                if isinstance(svc, dict):
                    parts.append(_service_status_line(svc))
            total = int(data.get("total") or len(services))
            if len(services) > 10:
                parts.append(f"（共 {total} 项，仅列出前 10 项）")
        return "\n".join(parts)

    items = data.get("items") or data.get("list")
    if isinstance(items, list) and items:
        lines = [f"共 {len(items)} 条记录："]
        for item in items[:8]:
            if isinstance(item, dict):
                label = item.get("name") or item.get("id") or item.get("title")
                lines.append(f"- {label or json.dumps(item, ensure_ascii=False)[:80]}")
            else:
                lines.append(f"- {item}")
        if len(items) > 8:
            lines.append(f"…另有 {len(items) - 8} 条")
        return "\n".join(lines)

    text = json.dumps(data, ensure_ascii=False)
    return text[:800] + ("…" if len(text) > 800 else "")


def format_result_preview(payload: Any, *, limit: int = 200) -> str:
    """Short single-line preview for SSE activity list."""
    formatted = format_tool_result_for_llm(payload).replace("\n", " · ")
    if len(formatted) <= limit:
        return formatted
    return formatted[: limit - 1] + "…"


def format_tool_result_for_user(payload: Any) -> str:
    """Narrative summary for mock/fallback final assistant replies."""
    data = payload if isinstance(payload, dict) else _as_dict(payload)
    if data is None:
        text = str(payload).strip()
        if not text:
            return "已完成处理。如需进一步操作，请告诉我。"
        return f"已完成查询。\n\n{text[:400]}{'…' if len(text) > 400 else ''}"

    if data.get("error"):
        return f"未能完成操作：{data['error']}\n\n您可以换个说法重试，或让我改用其他方式查询。"

    if data.get("mock_only") or data.get("real_execution") is False:
        name = str(data.get("name") or "").strip()
        if name:
            return (
                "本次为模拟执行，项目并未真实写入平台。"
                f"\n\n如需真实创建，请确认平台 API 为 live/hybrid 模式且 core-service 可用，"
                f"或让我在血缘页面通过表单操作完成创建（name={name}）。"
            )

    if data.get("success") is False:
        reason = data.get("message") or data.get("error") or "未知原因"
        return f"操作未成功：{reason}"

    project_id = data.get("project_id") or data.get("id")
    if project_id is not None and str(data.get("name") or "").strip():
        return (
            f"血缘项目「{data['name']}」已创建成功（project_id={project_id}）。"
            f"\n\n可在「统一血缘」页面查看该项目。"
        )

    message = str(data.get("message") or "").strip()
    if message and data.get("success") is True:
        return f"页面操作已完成：{message}"

    summary = str(data.get("summary") or "").strip()
    services = data.get("services")
    if isinstance(services, list) and services:
        healthy = data.get("healthy")
        down = data.get("down")
        intro = summary or "已完成平台服务健康检查。"
        if healthy is not None:
            intro = f"{intro.rstrip('。')}（{healthy} 项正常"
            if down:
                intro += f"，{down} 项需关注"
            intro += "）。"
        lines = [intro, "", "主要服务状态："]
        for svc in services[:6]:
            if isinstance(svc, dict):
                lines.append(_service_status_line(svc))
        total = int(data.get("total") or len(services))
        if len(services) > 6:
            lines.append(f"- …共 {total} 项，完整列表可在执行详情中展开")
        return "\n".join(lines)

    if summary:
        return summary

    preview = format_tool_result_for_llm(data)
    return preview if preview else "已完成处理。如需进一步操作，请告诉我。"
