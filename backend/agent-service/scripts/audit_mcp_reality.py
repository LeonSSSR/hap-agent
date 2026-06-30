#!/usr/bin/env python3
"""Code-level audit: MCP registry vs bindings vs handlers vs frontend vs backend."""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

AGENT_SERVICE = Path(__file__).resolve().parents[1]
ROOT = AGENT_SERVICE.parents[1]
FRONTEND_SERVICES = ROOT / "frontend" / "src" / "services"
FRONTEND_SCAN_DIRS = (
  FRONTEND_SERVICES,
  ROOT / "frontend" / "src" / "pages",
  ROOT / "frontend" / "src" / "components",
)
CORE_ROUTERS = ROOT / "backend" / "core-service" / "routers"
CORE_MAIN = ROOT / "backend" / "core-service" / "main.py"
REPORT_PATH = AGENT_SERVICE / "reports" / "mcp_reality_audit.json"

sys.path.insert(0, str(AGENT_SERVICE))

from scripts.generate_mcp_api_tools import (  # noqa: E402
  EXCLUDE_PATH_CONTAINS,
  EXCLUDE_PATH_PREFIXES,
  EXCLUDE_PATH_SUFFIXES,
  scan_frontend_services,
  _should_exclude,
  _normalize_path,
)
from services.mcp_alias_registry import resolve_canonical_tool_name  # noqa: E402
from services.mcp_server import mcp_server  # noqa: E402
from services.platform_api_bindings import iter_tool_bindings, resolve_binding  # noqa: E402
from services.tool_registry import tool_registry  # noqa: E402

ROUTER_DEF_RE = re.compile(
  r"(\w+)\s*=\s*APIRouter\([^)]*prefix\s*=\s*['\"]([^'\"]+)['\"]",
  re.MULTILINE,
)
ROUTE_DECORATOR_RE = re.compile(
  r"@(\w+)\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]*)['\"]",
  re.IGNORECASE,
)
API_ROUTE_RE = re.compile(
  r"@(\w+)\.api_route\(\s*['\"]([^'\"]*)['\"][^)]*methods\s*=\s*\[([^\]]+)\]",
  re.IGNORECASE | re.MULTILINE,
)
METHODS_LIST_RE = re.compile(r"['\"](\w+)['\"]")

# 语义化 MCP 工具 → 期望的前端 API 签名（method + path）
SEMANTIC_API_EXPECTATIONS: dict[str, tuple[str, str]] = {
  "algorithm_catalog_query": ("GET", "/api/algorithms"),
  "algorithm_register": ("POST", "/api/algorithms"),
  "labeling_project_list": ("GET", "/api/labeling/projects"),
  "labeling_project_create": ("POST", "/api/labeling/projects"),
  "notebook_catalog_query": ("GET", "/api/notebooks"),
  "notebook_session_create": ("POST", "/api/notebooks"),
  "ml_pipeline_catalog_query": ("GET", "/api/pipelines"),
  "ml_pipeline_create": ("POST", "/api/pipelines"),
  "ml_pipeline_run_list": ("GET", "/api/runs"),
  "ml_pipeline_run_submit": ("POST", "/api/runs"),
  "hyperparam_experiment_list": ("GET", "/api/tuning-proxy/experiments"),
  "hyperparam_experiment_create": ("POST", "/api/tuning-proxy/experiments"),
  "data_exploration_query": ("POST", "/api/governance/explore"),
  "data_split_execute": ("POST", "/api/datasets/{id}/split"),
  "dataset_catalog_query": ("GET", "/api/datasets"),
  "dataset_version_create": ("POST", "/api/datasets/{dataset_id}/split"),
  "transform_pipeline_list": ("GET", "/api/data-transform/jobs"),
  "transform_job_create": ("POST", "/api/data-transform/jobs"),
  "feature_registry_catalog_query": ("GET", "/api/features"),
  "feature_registry_register": ("POST", "/api/features"),
  "cicd_pipeline_catalog_query": ("GET", "/api/cicd/pipelines"),
  "infer_logs_query": ("GET", "/api/inference/services/{name}/logs"),
  "model_evaluation_run": ("POST", "/api/model-versions/evaluate"),
  "collaboration_space_query": ("GET", "/api/collaboration/workspaces"),
}

SPECIAL_TOOLS = frozenset(
  {
    "approval_gate",
    "risk_policy_checker",
    "hap_ui_action",
    "platform_mock_catalog",
    "service_monitor_query",
    "platform_code_search",
    "platform_dependency_graph",
    "catalog_lookup",
    "lineage_query",
  }
)


@dataclass
class AuditReport:
  summary: dict[str, int] = field(default_factory=dict)
  registry_tools: list[dict] = field(default_factory=list)
  binding_issues: list[dict] = field(default_factory=list)
  semantic_tool_gaps: list[dict] = field(default_factory=list)
  generated_binding_issues: list[dict] = field(default_factory=list)
  frontend_gaps: list[dict] = field(default_factory=list)
  recommendations: list[str] = field(default_factory=list)


def normalize_api_path(path: str) -> str:
  path = _normalize_path(path)
  if "?" in path:
    path = path.split("?", 1)[0]
  path = re.sub(r"\$\{[^}]+\}", "{param}", path)
  path = re.sub(r"\{[^}]+\}", "{param}", path)
  return path


def binding_signature(binding: dict) -> tuple[str, str]:
  method = str(binding.get("method") or "GET").upper()
  path = str(binding.get("path") or "")
  if not path.startswith("/api"):
    path = f"/api{path}"
  return method, normalize_api_path(path)


def _add_route_signature(signatures: set[tuple[str, str]], method: str, prefix: str, route_path: str) -> None:
  full = f"/api{prefix}{route_path}"
  full = re.sub(r"/+", "/", full)
  if not full.startswith("/api"):
    full = f"/api{full}"
  signatures.add((method.upper(), normalize_api_path(full)))


def scan_backend_routes() -> set[tuple[str, str]]:
  signatures: set[tuple[str, str]] = set()
  if CORE_ROUTERS.exists():
    for file_path in sorted(CORE_ROUTERS.rglob("*.py")):
      content = file_path.read_text(encoding="utf-8", errors="ignore")
      router_prefixes = {name: prefix for name, prefix in ROUTER_DEF_RE.findall(content)}
      for router_name, method, route_path in ROUTE_DECORATOR_RE.findall(content):
        prefix = router_prefixes.get(router_name, "")
        _add_route_signature(signatures, method, prefix, route_path)
      for router_name, route_path, methods_blob in API_ROUTE_RE.findall(content):
        prefix = router_prefixes.get(router_name, "")
        for method in METHODS_LIST_RE.findall(methods_blob):
          _add_route_signature(signatures, method, prefix, route_path)
  if CORE_MAIN.exists():
    content = CORE_MAIN.read_text(encoding="utf-8", errors="ignore")
    router_prefixes = {name: prefix for name, prefix in ROUTER_DEF_RE.findall(content)}
    for router_name, method, route_path in ROUTE_DECORATOR_RE.findall(content):
      prefix = router_prefixes.get(router_name, "")
      _add_route_signature(signatures, method, prefix, route_path)
  return signatures


def scan_frontend_signatures() -> dict[tuple[str, str], list[str]]:
  grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
  for op in scan_frontend_services():
    sig = (op.method, normalize_api_path(op.full_path))
    grouped[sig].append(op.source_file)
  return grouped


def tool_execution_kind(tool_name: str) -> str:
  canonical = resolve_canonical_tool_name(tool_name)
  if canonical in mcp_server._handlers:
    return "dedicated_handler"
  if canonical == "lineage_project_create":
    return "special_live_handler"
  if resolve_binding(canonical) or resolve_binding(tool_name):
    return "generic_binding"
  if canonical in SPECIAL_TOOLS:
    return "special_mock_or_probe"
  return "mock_only"


def path_matches_backend(sig: tuple[str, str], backend_sigs: set[tuple[str, str]]) -> bool:
  if sig in backend_sigs:
    return True
  method, path = sig
  # 宽松匹配：参数名归一后比对
  for b_method, b_path in backend_sigs:
    if method == b_method and path == b_path:
      return True
  return False


def audit() -> AuditReport:
  report = AuditReport()
  frontend_sigs = scan_frontend_signatures()
  backend_sigs = scan_backend_routes()
  bindings = iter_tool_bindings()
  binding_by_tool = {str(b.get("tool_name")): b for b in bindings}

  handler_tools = set(mcp_server._handlers.keys()) | {"lineage_project_create"}
  tools = tool_registry.list()

  counts = defaultdict(int)
  for tool_name in tools:
    meta = tool_registry.get(tool_name) or {}
    canonical = resolve_canonical_tool_name(tool_name)
    kind = tool_execution_kind(tool_name)
    counts[kind] += 1
    binding = binding_by_tool.get(canonical) or binding_by_tool.get(tool_name)
    provider = meta.get("provider") or {}
    stage = str(meta.get("realization_stage") or "")
    policy = meta.get("realization_policy") or {}
    real_first = bool(policy.get("real_enabled_first") or policy.get("real_enabled_after_readonly"))

    entry = {
      "tool_name": tool_name,
      "execution_kind": kind,
      "has_binding": binding is not None,
      "has_handler": canonical in handler_tools or tool_name in handler_tools,
      "provider_real": bool(provider.get("real")),
      "realization_stage": stage,
      "real_enabled_first": real_first,
      "generated": bool(meta.get("generated") or (binding or {}).get("generated")),
    }
    if binding:
      entry["binding"] = {
        "method": binding.get("method"),
        "path": binding.get("path"),
        "readonly": binding.get("readonly"),
      }
    report.registry_tools.append(entry)

    # 语义工具：无 binding/handler 但声明了 real
    if (
      kind == "mock_only"
      and provider.get("real")
      and tool_name not in SPECIAL_TOOLS
    ):
      expected = SEMANTIC_API_EXPECTATIONS.get(tool_name)
      hap_equiv = [t for t in tools if t.startswith("hap_api_") and expected and binding_signature(binding_by_tool[t]) == (expected[0], normalize_api_path(expected[1]))] if expected and tool_name in binding_by_tool else []
      generated_equiv = []
      if expected:
        exp_sig = (expected[0], normalize_api_path(expected[1]))
        for t, b in binding_by_tool.items():
          if t.startswith("hap_api_") and binding_signature(b) == exp_sig:
            generated_equiv.append(t)
      report.semantic_tool_gaps.append(
        {
          "tool_name": tool_name,
          "expected_api": expected,
          "generated_equivalent": generated_equiv[:3],
          "issue": "声明 provider.real=true 但仅 mock，无 binding/handler",
        }
      )

  # 检查所有 binding
  seen_sigs: dict[tuple[str, str], str] = {}
  for binding in bindings:
    tool_name = str(binding.get("tool_name"))
    sig = binding_signature(binding)
    method, path = sig
    issues = []

    if sig in seen_sigs:
      issues.append(f"duplicate_signature_with:{seen_sigs[sig]}")
    else:
      seen_sigs[sig] = tool_name

    in_frontend = sig in frontend_sigs
    in_backend = path_matches_backend(sig, backend_sigs)

    if not in_frontend and not binding.get("generated"):
      issues.append("not_found_in_frontend_scan")
    if binding.get("generated"):
      if not in_frontend:
        issues.append("generated_not_in_frontend")
      if not in_backend:
        issues.append("generated_not_in_backend_router")
    elif not in_backend and tool_name not in handler_tools:
      issues.append("manual_binding_not_in_backend_router")
    # handler 专用 binding：页面可能走不同路径，去掉 frontend 误报
    if not binding.get("generated") and tool_name in handler_tools:
      issues = [i for i in issues if i != "not_found_in_frontend_scan"]

    if issues:
      payload = {
        "tool_name": tool_name,
        "signature": {"method": method, "path": path},
        "generated": bool(binding.get("generated")),
        "issues": issues,
        "frontend_sources": frontend_sigs.get(sig, [])[:2],
      }
      if binding.get("generated"):
        report.generated_binding_issues.append(payload)
      else:
        report.binding_issues.append(payload)

  # 前端 API 缺少 MCP（排除刻意跳过的）
  binding_sigs = {binding_signature(b) for b in bindings}
  for sig, sources in sorted(frontend_sigs.items()):
    method, path = sig
    full_path = path
    if _should_exclude(full_path):
      continue
    if sig not in binding_sigs:
      report.frontend_gaps.append(
        {
          "method": method,
          "path": path,
          "sources": sources[:2],
          "issue": "frontend_api_without_binding",
        }
      )

  report.summary = {
    "registry_tool_count": len(tools),
    "binding_count": len(bindings),
    "frontend_api_signatures": len(frontend_sigs),
    "backend_route_signatures": len(backend_sigs),
    "execution_kind_counts": dict(counts),
    "semantic_mock_only_with_real_flag": len(report.semantic_tool_gaps),
    "manual_binding_issues": len(report.binding_issues),
    "generated_binding_issues": len(report.generated_binding_issues),
    "frontend_api_without_binding": len(report.frontend_gaps),
  }

  # 统计 generated 问题分类
  gen_issue_types = defaultdict(int)
  for item in report.generated_binding_issues:
    for issue in item["issues"]:
      gen_issue_types[issue] += 1
  report.summary["generated_issue_breakdown"] = dict(gen_issue_types)

  report.recommendations = [
    "43 个语义化 MCP（如 algorithm_catalog_query）仅 mock，应 alias 到对应 hap_api_* 或补 binding",
    "generated 工具中 not_in_backend 多为 proxy/微服务路由，parser 未覆盖 notebooks_proxy 等额外 router",
    "provider.real=true 但 realization_stage=future_or_mock 的工具不应在 live 模式被宣传为已落地",
    "优先为 p2_batch_* 阶段且有 handler/binding 的工具做 live 冒烟，而非 492 个全量探测",
  ]
  return report


def main() -> None:
  report = audit()
  REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
  REPORT_PATH.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8")

  print("=== MCP Reality Audit ===")
  for key, value in report.summary.items():
    print(f"{key}: {value}")
  print(f"\nreport: {REPORT_PATH}")

  if report.binding_issues:
    print("\n--- manual binding issues ---")
    for item in report.binding_issues[:15]:
      print(item)

  if report.generated_binding_issues:
    print("\n--- generated binding issues (sample) ---")
    for item in report.generated_binding_issues[:10]:
      print(item)

  if report.semantic_tool_gaps:
    print("\n--- semantic tools mock-only (sample) ---")
    for item in report.semantic_tool_gaps[:10]:
      print(item)


if __name__ == "__main__":
  main()
