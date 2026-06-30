"""Tests for generic platform API binding invocation."""

from __future__ import annotations

from services.mcp_binding_invoker import (
  build_path_params_auto,
  build_query_params_auto,
  build_request_body,
  missing_required_path_params,
)
from services.platform_api_bindings import resolve_binding


def test_build_path_params_auto_supports_camel_case_aliases() -> None:
  binding = resolve_binding("training_job_status")
  assert binding is not None
  params = build_path_params_auto(binding, {"jobId": "job-123"})
  assert params.get("job_id") == "job-123"


def test_build_query_params_auto_for_generated_get_binding() -> None:
  binding = resolve_binding("hap_api_get_governance_datasets")
  assert binding is not None
  query = build_query_params_auto(binding, {"pageNum": 2, "keyword": "demo"}, path_params={})
  assert query["pageNum"] == 2
  assert query["keyword"] == "demo"


def test_build_request_body_excludes_path_and_query_keys() -> None:
  binding = resolve_binding("hap_api_post_projects_by_param_versions")
  assert binding is not None
  body = build_request_body(
    binding,
    {"name": "demo", "dataType": "TEXT", "projectId": 9},
    path_params={"projectId": 9},
    query_params={},
  )
  assert body == {"name": "demo", "dataType": "TEXT"}


def test_missing_required_path_params_detected() -> None:
  binding = resolve_binding("training_job_status")
  assert binding is not None
  missing = missing_required_path_params(binding, {})
  assert "job_id" in missing
