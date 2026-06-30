"""Virtual OpenAI tool: pause run and ask user for missing information."""

from __future__ import annotations

from typing import Any

HAP_CLARIFY_TOOL = "hap_request_clarification"

LINEAGE_DATA_TYPES: tuple[str, ...] = (
    "TABULAR",
    "TIMESERIES",
    "TEXT",
    "IMAGE",
    "VIDEO",
    "AUDIO",
)


def missing_required_tool_arguments(tool_name: str, args: dict[str, Any] | None) -> list[str]:
    """Return missing required argument names. Never fills or guesses values."""
    payload = dict(args or {})
    if tool_name == "lineage_project_create":
        missing: list[str] = []
        if not str(payload.get("name") or "").strip():
            missing.append("name")
        data_type = str(payload.get("dataType") or "").strip().upper()
        if not data_type or data_type not in LINEAGE_DATA_TYPES:
            missing.append("dataType")
        return missing
    return []


def hap_clarify_openai_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": HAP_CLARIFY_TOOL,
            "description": (
                "继续操作前信息不足时调用。提出明确问题后执行暂停，待用户在界面补充或选择后继续。"
                "不得猜测或自动填充工具参数；缺必填项时必须由用户提供。"
            ),
            "parameters": {
                "type": "object",
                "required": ["question"],
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "向用户提出的补充问题（简体中文，一句话）",
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "待补充字段标识，如 name、dataType",
                    },
                    "placeholder": {
                        "type": "string",
                        "description": "输入框占位提示",
                    },
                    "choices": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "可选：供用户点选的候选项（如数据类型列表）",
                    },
                },
            },
        },
    }
