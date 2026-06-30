"""Generic live/mock invocation for tools backed by platform_api_bindings."""

from __future__ import annotations

import re
from typing import Any

from services.platform_api_bindings import (
  build_path_params,
  build_query_params,
  resolve_binding,
)

_PATH_PARAM_RE = re.compile(r"\{(\w+)\}")
_RESERVED_PAYLOAD_KEYS = frozenset(
  {
    "scenario",
    "confirmed",
    "tool_name",
    "ui_action_id",
    "user_input",
    "target",
  }
)


def _snake_to_camel(value: str) -> str:
  parts = value.split("_")
  if not parts:
    return value
  return parts[0] + "".join(part.capitalize() for part in parts[1:])


def _aliases_for_param(key: str) -> tuple[str, ...]:
  candidates = [key, key.replace("_", "")]
  camel = _snake_to_camel(key)
  if camel != key:
    candidates.append(camel)
  if key.endswith("_id"):
    short = key[:-3]
    candidates.extend([short, _snake_to_camel(short)])
  ordered: list[str] = []
  for item in candidates:
    if item and item not in ordered:
      ordered.append(item)
  return tuple(ordered)


def _pick_payload_value(payload: dict[str, Any], *keys: str) -> Any:
  for key in keys:
    value = payload.get(key)
    if value is not None and value != "":
      return value
  return None


def path_param_keys(binding: dict[str, Any]) -> list[str]:
  spec = binding.get("path_params")
  if isinstance(spec, dict) and spec:
    return list(spec.keys())
  path = str(binding.get("path") or "")
  return _PATH_PARAM_RE.findall(path)


def build_path_params_auto(binding: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
  explicit = build_path_params(binding, payload)
  if explicit:
    return explicit
  result: dict[str, Any] = {}
  for key in path_param_keys(binding):
    value = _pick_payload_value(payload, *_aliases_for_param(key))
    if value is not None and value != "":
      result[key] = value
  return result


def build_query_params_auto(
  binding: dict[str, Any],
  payload: dict[str, Any],
  *,
  path_params: dict[str, Any],
) -> dict[str, Any]:
  explicit = build_query_params(binding, payload)
  if explicit:
    return explicit
  method = str(binding.get("method") or "GET").upper()
  if method not in {"GET", "DELETE", "HEAD"}:
    return {}
  reserved = set(path_params) | _RESERVED_PAYLOAD_KEYS
  for key in path_param_keys(binding):
    reserved.update(_aliases_for_param(key))
  query: dict[str, Any] = {}
  for key, value in payload.items():
    if key in reserved or key.startswith("_"):
      continue
    if value is not None and value != "":
      query[key] = value
  return query


def build_request_body(
  binding: dict[str, Any],
  payload: dict[str, Any],
  *,
  path_params: dict[str, Any],
  query_params: dict[str, Any],
) -> dict[str, Any] | None:
  method = str(binding.get("method") or "GET").upper()
  if method not in {"POST", "PUT", "PATCH"}:
    return None
  reserved = set(path_params) | set(query_params) | _RESERVED_PAYLOAD_KEYS
  for key in path_param_keys(binding):
    reserved.update(_aliases_for_param(key))
  body = {
    key: value
    for key, value in payload.items()
    if key not in reserved and not key.startswith("_") and value is not None
  }
  return body or {}


def missing_required_path_params(binding: dict[str, Any], path_params: dict[str, Any]) -> list[str]:
  spec = binding.get("path_params")
  missing: list[str] = []
  if isinstance(spec, dict) and spec:
    for key, meta in spec.items():
      if isinstance(meta, dict) and meta.get("required") and key not in path_params:
        missing.append(key)
    return missing
  for key in path_param_keys(binding):
    if key not in path_params:
      missing.append(key)
  return missing


def format_binding_result(
  *,
  tool_name: str,
  binding: dict[str, Any],
  envelope: dict[str, Any],
) -> dict[str, Any]:
  data = envelope.get("data") if isinstance(envelope, dict) else envelope
  method = str(binding.get("method") or "GET").upper()
  path = str(binding.get("path") or "")
  summary = f"{method} {path}"
  if isinstance(data, list):
    summary = f"{summary} 返回 {len(data)} 条记录"
  elif isinstance(data, dict):
    for key in ("total", "count", "items"):
      if key in data and isinstance(data.get(key), (int, list)):
        value = data[key]
        summary = f"{summary} 返回 {len(value) if isinstance(value, list) else value} 条记录"
        break
  return {
    "status": "ok",
    "source": "real",
    "tool_name": tool_name,
    "real_execution": True,
    "api_method": method,
    "api_path": path,
    "data": data,
    "summary": summary,
  }


def invoke_binding_tool(client: Any, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
  binding = resolve_binding(tool_name)
  if binding is None:
    raise ValueError(f"no platform api binding for tool: {tool_name}")
  path_params = build_path_params_auto(binding, payload)
  missing = missing_required_path_params(binding, path_params)
  if missing:
    raise ValueError(f"missing required path params: {', '.join(missing)}")
  query_params = build_query_params_auto(binding, payload, path_params=path_params)
  body = build_request_body(binding, payload, path_params=path_params, query_params=query_params)
  envelope = client.request(binding, path_params=path_params, query=query_params or None, body=body)
  return format_binding_result(tool_name=tool_name, binding=binding, envelope=envelope)
