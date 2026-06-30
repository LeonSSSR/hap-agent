#!/usr/bin/env python3
"""Scan frontend service APIs and generate MCP bindings + registry tools."""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
FRONTEND_SERVICES = ROOT / "frontend" / "src" / "services"
FRONTEND_SCAN_DIRS = (
  FRONTEND_SERVICES,
  ROOT / "frontend" / "src" / "pages",
  ROOT / "frontend" / "src" / "components",
)
AGENT_SERVICE = Path(__file__).resolve().parents[1]
MANUAL_BINDINGS = AGENT_SERVICE / "mcp" / "platform_api_bindings.yaml"
GENERATED_BINDINGS = AGENT_SERVICE / "mcp" / "platform_api_bindings.generated.yaml"
GENERATED_TOOLS = AGENT_SERVICE / "mcp" / "tools" / "generated_frontend_apis.yaml"

EXCLUDE_PATH_PREFIXES = (
  "/api/agent/",
  "/api/auth/",
)
EXCLUDE_PATH_CONTAINS = (
  "/artifacts/upload",
  "/artifacts/chunk/upload",
  "/artifacts/chunk/abort",
  "/chunk/upload",
  "/import-template",
  "/export/download",
  "/presign",
  "/entry-preview",
  "/entry?",
  "/recognize",
)
EXCLUDE_PATH_SUFFIXES = (
  "/upload",
)

CONST_PREFIX_RE = re.compile(r"const\s+(\w+)\s*=\s*['\"]([^'\"]+)['\"]")
METHOD_RE = re.compile(r"method\s*:\s*['\"](\w+)['\"]", re.IGNORECASE)
TEMPLATE_EXPR_RE = re.compile(r"\$\{([^}]+)\}")


def _extract_request_calls(content: str) -> list[tuple[str, str | None]]:
  """Extract request()/bizRequest() url + options, supporting nested generics."""
  results: list[tuple[str, str | None]] = []
  for match in re.finditer(r"\b(?:request|bizRequest)\b", content):
    pos = match.end()
    if pos < len(content) and content[pos] == "<":
      depth = 0
      while pos < len(content):
        char = content[pos]
        if char == "<":
          depth += 1
        elif char == ">":
          depth -= 1
          if depth == 0:
            pos += 1
            break
        pos += 1
    while pos < len(content) and content[pos].isspace():
      pos += 1
    if pos >= len(content) or content[pos] != "(":
      continue
    pos += 1
    while pos < len(content) and content[pos].isspace():
      pos += 1
    if pos >= len(content):
      continue
    quote = content[pos]
    if quote not in ("`", "'", '"'):
      continue
    pos += 1
    url_start = pos
    while pos < len(content):
      if content[pos] == "\\":
        pos += 2
        continue
      if content[pos] == quote:
        url_expr = content[url_start:pos]
        pos += 1
        break
      pos += 1
    else:
      continue
    options = None
    while pos < len(content) and content[pos].isspace():
      pos += 1
    if pos < len(content) and content[pos] == ",":
      pos += 1
      while pos < len(content) and content[pos].isspace():
        pos += 1
      if pos < len(content) and content[pos] == "{":
        depth = 0
        opt_start = pos
        while pos < len(content):
          char = content[pos]
          if char == "{":
            depth += 1
          elif char == "}":
            depth -= 1
            if depth == 0:
              options = content[opt_start : pos + 1]
              break
          pos += 1
    results.append((url_expr, options))
  return results


@dataclass(frozen=True)
class ApiOperation:
  method: str
  full_path: str
  source_file: str

  @property
  def binding_path(self) -> str:
    path = self.full_path
    if path.startswith("/api"):
      path = path[4:] or "/"
    if "?" in path:
      path = path.split("?", 1)[0]
    return path if path.startswith("/") else f"/{path}"

  @property
  def normalized_path(self) -> str:
    return TEMPLATE_EXPR_RE.sub(lambda match: f"{{{match.group(1).split('.')[-1].strip()}}}", self.binding_path)


@dataclass
class GenerationStats:
  scanned_files: int = 0
  extracted_calls: int = 0
  skipped_excluded: int = 0
  skipped_manual: int = 0
  skipped_duplicate: int = 0
  generated_tools: int = 0


def _resolve_template(url_expr: str, prefixes: dict[str, str]) -> str | None:
  expr = url_expr.strip().strip("`'\"").strip()
  if not expr:
    return None
  if expr.startswith("/api") or expr.startswith("/data-ingestion") or expr.startswith("/annotation-api"):
    if "${" in expr:
      expr = TEMPLATE_EXPR_RE.sub(
        lambda match: f"{{{match.group(1).split('.')[-1].strip()}}}",
        expr,
      )
    return _normalize_frontend_api_path(_normalize_path(expr))
  if "${" not in expr:
    return None

  def replacer(match: re.Match[str]) -> str:
    token = match.group(1).strip()
    if token in prefixes:
      return prefixes[token]
    if "." in token:
      root = token.split(".", 1)[0]
      if root in prefixes:
        return prefixes[root]
    return f"{{{token.split('.')[-1]}}}"

  resolved = TEMPLATE_EXPR_RE.sub(replacer, expr)
  if "${" in resolved:
    return None
  return _normalize_frontend_api_path(_normalize_path(resolved))


def _normalize_path(path: str) -> str:
  path = path.strip()
  if not path.startswith("/"):
    path = f"/{path}"
  path = re.sub(r"/+", "/", path)
  return path


def _normalize_frontend_api_path(path: str) -> str:
  path = _normalize_path(path)
  if path.startswith("/data-ingestion"):
    return f"/api{path}"
  if path.startswith("/annotation-api"):
    remainder = path[len("/annotation-api"):] or "/"
    return _normalize_path(remainder)
  return path


def _infer_method(options: str | None) -> str:
  if not options:
    return "GET"
  match = METHOD_RE.search(options)
  if match:
    return match.group(1).upper()
  return "GET"


def _should_exclude(path: str) -> bool:
  if not path.startswith("/api"):
    return True
  for prefix in EXCLUDE_PATH_PREFIXES:
    if path.startswith(prefix):
      return True
  for marker in EXCLUDE_PATH_CONTAINS:
    if marker in path:
      return True
  for suffix in EXCLUDE_PATH_SUFFIXES:
    if path.endswith(suffix):
      return True
  return False


def _normalize_signature_path(path: str) -> str:
  path = _normalize_path(path)
  if "${" in path:
    path = TEMPLATE_EXPR_RE.sub(
      lambda match: f"{{{match.group(1).split('.')[-1].strip()}}}",
      path,
    )
  if path.startswith("/api"):
    path = path[3:] or "/"
  path = re.sub(r"\{[^}]+\}", "{param}", path)
  return path if path.startswith("/") else f"/{path}"


def _load_manual_signatures() -> set[tuple[str, str]]:
  if not MANUAL_BINDINGS.exists():
    return set()
  document = yaml.safe_load(MANUAL_BINDINGS.read_text(encoding="utf-8")) or {}
  signatures: set[tuple[str, str]] = set()
  for item in document.get("tools") or []:
    if not isinstance(item, dict):
      continue
    method = str(item.get("method") or "GET").upper()
    path = str(item.get("path") or "")
    if not path.startswith("/api"):
      path = f"/api{path}"
    signatures.add((method, _normalize_signature_path(path)))
  return signatures


def _path_to_tool_name(method: str, path: str) -> str:
  clean = path
  if clean.startswith("/api"):
    clean = clean[4:] or "/"
  clean = clean.strip("/")
  clean = re.sub(r"\{[^}]+\}", "by_param", clean)
  clean = re.sub(r"[^a-zA-Z0-9]+", "_", clean).strip("_").lower()
  if not clean:
    clean = "root"
  name = f"hap_api_{method.lower()}_{clean}"
  return name[:96]


def _path_params_spec(path: str) -> dict[str, dict[str, bool]] | None:
  keys = TEMPLATE_EXPR_RE.findall(path)
  if not keys:
    keys = re.findall(r"\{(\w+)\}", path)
  if not keys:
    return None
  return {key: {"required": True} for key in dict.fromkeys(keys)}


def _risk_and_permissions(method: str) -> tuple[str, list[str]]:
  if method == "GET":
    return "low", ["workflow.read"]
  if method == "DELETE":
    return "high", ["workflow.read", "ml.lifecycle.execute"]
  return "medium", ["workflow.read", "ml.lifecycle.execute"]


def scan_frontend_services() -> list[ApiOperation]:
  """Scan services/, pages/, and components/ for request()/bizRequest() API calls."""
  operations: list[ApiOperation] = []
  scanned_files = 0
  for scan_dir in FRONTEND_SCAN_DIRS:
    if not scan_dir.exists():
      continue
    for file_path in sorted(scan_dir.rglob("*.ts")) + sorted(scan_dir.rglob("*.tsx")):
      scanned_files += 1
      content = file_path.read_text(encoding="utf-8", errors="ignore")
      prefixes = {name: value for name, value in CONST_PREFIX_RE.findall(content)}
      for url_expr, options in _extract_request_calls(content):
        method = _infer_method(options)
        full_path = _resolve_template(url_expr, prefixes)
        if not full_path:
          continue
        operations.append(
          ApiOperation(
            method=method,
            full_path=full_path,
            source_file=str(file_path.relative_to(ROOT)),
          )
        )
  scan_frontend_services.scanned_files = scanned_files  # type: ignore[attr-defined]
  return operations


def build_generated_payload(operations: list[ApiOperation]) -> tuple[list[dict], list[dict], GenerationStats]:
  stats = GenerationStats()
  manual_signatures = _load_manual_signatures()
  grouped: dict[tuple[str, str], ApiOperation] = {}
  stats.extracted_calls = len(operations)

  for op in operations:
    if _should_exclude(op.full_path):
      stats.skipped_excluded += 1
      continue
    signature = (op.method, _normalize_signature_path(op.full_path))
    if signature in manual_signatures:
      stats.skipped_manual += 1
      continue
    if signature in grouped:
      stats.skipped_duplicate += 1
      continue
    grouped[signature] = op

  bindings: list[dict] = []
  tools: list[dict] = []
  for signature, op in sorted(grouped.items(), key=lambda item: (item[0][1], item[0][0])):
    method, _ = signature
    tool_name = _path_to_tool_name(method, op.full_path)
    if any(existing.get("tool_name") == tool_name for existing in bindings):
      tool_name = f"{tool_name}_{len(bindings)}"
    readonly = method in {"GET", "HEAD"}
    binding: dict = {
      "tool_name": tool_name,
      "method": method,
      "path": op.normalized_path,
      "readonly": readonly,
      "generated": True,
      "source_file": op.source_file,
    }
    path_params = _path_params_spec(op.normalized_path)
    if path_params:
      binding["path_params"] = path_params
    bindings.append(binding)

    risk, permissions = _risk_and_permissions(method)
    tools.append(
      {
        "tool_name": tool_name,
        "title": f"{method} {op.full_path}",
        "description": f"前端可调用的平台 API：{method} {op.full_path}（来源 {op.source_file}）",
        "source": "platform",
        "risk_level": risk,
        "permission_scope": permissions,
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "resource_type": "api",
        "replaceable_mock": True,
        "append_only_policy": "read_only" if readonly else "append_only",
        "provider": {"mock": True, "real": True},
        "realization_stage": "p2_batch",
        "realization_policy": {"real_enabled_first": True},
        "generated": True,
        "api_method": method,
        "api_path": op.full_path,
      }
    )
    stats.generated_tools += 1

  stats.scanned_files = getattr(scan_frontend_services, "scanned_files", 0) or len(list(FRONTEND_SERVICES.rglob("*.ts")))
  return bindings, tools, stats


def write_outputs(bindings: list[dict], tools: list[dict]) -> None:
  GENERATED_BINDINGS.write_text(
    yaml.safe_dump(
      {
        "registry_id": "znl-platform-api-bindings-generated",
        "version": "1.0.0",
        "generated": True,
        "tools": bindings,
      },
      allow_unicode=True,
      sort_keys=False,
    ),
    encoding="utf-8",
  )
  GENERATED_TOOLS.write_text(
    yaml.safe_dump(
      {
        "domain": "generated_frontend_apis",
        "generated": True,
        "tools": tools,
      },
      allow_unicode=True,
      sort_keys=False,
    ),
    encoding="utf-8",
  )


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--check", action="store_true", help="Only print stats, do not write files")
  args = parser.parse_args()

  operations = scan_frontend_services()
  bindings, tools, stats = build_generated_payload(operations)
  print(
    f"scanned_files={stats.scanned_files} extracted_calls={stats.extracted_calls} "
    f"skipped_excluded={stats.skipped_excluded} skipped_manual={stats.skipped_manual} "
    f"skipped_duplicate={stats.skipped_duplicate} generated_tools={stats.generated_tools}"
  )
  if args.check:
    return
  write_outputs(bindings, tools)
  print(f"wrote {GENERATED_BINDINGS}")
  print(f"wrote {GENERATED_TOOLS}")


if __name__ == "__main__":
  main()
