"""Helpers for lineage_project_create MCP tool (live + mock normalization)."""

from __future__ import annotations

from typing import Any

_PROJECT_DATATYPE_ALIASES: dict[str, str] = {
    "TEXT": "text",
    "TXT": "text",
    "文本": "text",
    "IMAGE": "image",
    "图像": "image",
    "TABULAR": "tabular",
    "TABLE": "tabular",
    "表格": "tabular",
    "TIMESERIES": "timeseries",
    "时序": "timeseries",
    "AUDIO": "audio",
    "音频": "audio",
    "VIDEO": "video",
    "视频": "video",
}


def normalize_project_datatype(raw: Any) -> str:
    token = str(raw or "").strip()
    if not token:
        return "tabular"
    upper = token.upper()
    if upper in _PROJECT_DATATYPE_ALIASES:
        return _PROJECT_DATATYPE_ALIASES[upper]
    lower = token.lower()
    if lower in {"text", "image", "tabular", "timeseries", "audio", "video"}:
        return lower
    return lower


def build_create_project_body(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    body: dict[str, Any] = {
        "name": name,
        "dataType": normalize_project_datatype(payload.get("dataType")),
    }
    description = str(payload.get("description") or "").strip()
    if description:
        body["description"] = description
    dataset_ids = payload.get("datasetIds")
    if isinstance(dataset_ids, list) and dataset_ids:
        body["datasetIds"] = dataset_ids
    return body


def format_create_project_result(
    envelope: dict[str, Any],
    *,
    fallback_name: str,
    fallback_data_type: str,
    source: str = "real",
) -> dict[str, Any]:
    data = envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
    project_id = data.get("id") or data.get("projectId") or data.get("project_id")
    return {
        "status": "ok",
        "source": source,
        "real_execution": source == "real",
        "mock_only": source != "real",
        "project_id": str(project_id) if project_id is not None else "",
        "name": str(data.get("name") or fallback_name),
        "dataType": str(data.get("dataType") or fallback_data_type),
        "message": f"血缘项目「{data.get('name') or fallback_name}」已创建",
    }
