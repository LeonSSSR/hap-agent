from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

BINDINGS_DIR = Path(__file__).resolve().parent.parent / "mcp"
BINDINGS_PATH = BINDINGS_DIR / "platform_api_bindings.yaml"
GENERATED_BINDINGS_PATH = BINDINGS_DIR / "platform_api_bindings.generated.yaml"

PATH_PARAM_ALIASES: dict[str, tuple[str, ...]] = {
  "job_id": ("job_id", "training_job_id"),
  "version_id": ("version_id", "model_version_id"),
  "name": ("name", "service_name"),
  "dataset_id": ("dataset_id"),
  "node_id": ("node_id", "entity"),
  "model_name": ("model_name", "modelName", "modelId"),
  "task_id": ("task_id", "job_id", "schedule_job_id"),
  "pipeline_id": ("pipeline_id", "pipelineId"),
  "run_id": ("run_id", "pipeline_run_id"),
  "rr_id": ("rr_id", "recurring_run_id", "job_id"),
  "service_name": ("service_name", "name"),
}


@lru_cache(maxsize=1)
def load_platform_api_bindings() -> dict[str, Any]:
  with BINDINGS_PATH.open(encoding="utf-8") as handle:
    document = yaml.safe_load(handle) or {}
  if not isinstance(document, dict):
    document = {}
  generated: list[dict[str, Any]] = []
  if GENERATED_BINDINGS_PATH.exists():
    generated_doc = yaml.safe_load(GENERATED_BINDINGS_PATH.read_text(encoding="utf-8")) or {}
    if isinstance(generated_doc, dict):
      raw_tools = generated_doc.get("tools")
      if isinstance(raw_tools, list):
        generated = [item for item in raw_tools if isinstance(item, dict)]
  manual_tools = document.get("tools")
  if not isinstance(manual_tools, list):
    manual_tools = []
  document["tools"] = [*manual_tools, *generated]
  return document


def iter_tool_bindings() -> list[dict[str, Any]]:
  document = load_platform_api_bindings()
  tools = document.get("tools", [])
  if not isinstance(tools, list):
    return []
  return [tool for tool in tools if isinstance(tool, dict) and tool.get("tool_name")]


def resolve_binding(tool_name: str) -> dict[str, Any] | None:
  for binding in iter_tool_bindings():
    if str(binding.get("tool_name")) == tool_name:
      return binding
  return None


def binding_is_readonly(binding: dict[str, Any]) -> bool:
  return bool(binding.get("readonly", False))


def _pick_payload_value(payload: dict[str, Any], *keys: str) -> Any:
  for key in keys:
    value = payload.get(key)
    if value is not None and value != "":
      return value
  return None


def build_path_params(binding: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
  spec = binding.get("path_params")
  if not isinstance(spec, dict):
    return {}
  result: dict[str, Any] = {}
  for key in spec:
    aliases = PATH_PARAM_ALIASES.get(key, (key,))
    value = _pick_payload_value(payload, *aliases)
    if value is not None and value != "":
      result[key] = value
  return result


def build_query_params(binding: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
  spec = binding.get("query_params")
  if not isinstance(spec, dict):
    return {}
  result: dict[str, Any] = {}
  for key, meta in spec.items():
    if not isinstance(meta, dict):
      continue
    aliases = (key, key.replace("_", ""))
    if key == "pageNum":
      aliases = ("pageNum", "page_num", "page")
    elif key == "pageSize":
      aliases = ("pageSize", "page_size", "limit")
    elif key == "q":
      aliases = ("q", "query", "keyword", "entity", "user_input", "target")
    elif key == "modelName":
      aliases = ("modelName", "model_name", "modelId", "model_id")
    elif key == "serviceName":
      aliases = ("serviceName", "service_name", "name")
    elif key == "project_id":
      aliases = ("project_id", "projectId")
    elif key == "keyword":
      aliases = ("keyword", "q", "query", "name")
    elif key == "status":
      aliases = ("status", "state")
    elif key == "type":
      aliases = ("type", "task_type")
    elif key == "hours":
      aliases = ("hours", "hour", "window_hours")
    value = _pick_payload_value(payload, *aliases)
    if value is not None and value != "":
      result[key] = value
    elif meta.get("default") is not None and not meta.get("optional", False):
      result[key] = meta.get("default")
  return result
