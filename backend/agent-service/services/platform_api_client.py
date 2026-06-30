from __future__ import annotations

import inspect
import uuid
from typing import Any

import httpx

from config import settings
from services.platform_api_bindings import (
  load_platform_api_bindings,
  resolve_binding,
)


class PlatformApiError(RuntimeError):
  pass


class PlatformApiClient:
  """HTTP client for core-service APIs described in platform_api_bindings.yaml.

  This client is intentionally locked down so it can only be constructed from
  the controlled MCP execution boundary. Direct instantiation from business
  logic is forbidden and will raise unless an internal trust token is supplied.
  """

  _INTERNAL_TRUST_TOKEN = object()

  def __init__(
    self,
    *,
    base_url: str | None = None,
    api_prefix: str | None = None,
    internal_token: str | None = None,
    api_key: str | None = None,
    timeout_seconds: float = 30.0,
    _trust_token: object | None = None,
  ) -> None:
    if _trust_token is not self._INTERNAL_TRUST_TOKEN:
      raise PlatformApiError("PlatformApiClient is restricted to the MCP boundary | blocked_by=mcp")
    document = load_platform_api_bindings()
    self.base_url = (base_url or settings.core_service_url or document.get("default_base_url", "http://127.0.0.1:8085")).rstrip("/")
    self.api_prefix = api_prefix or str(document.get("api_prefix") or "/api")
    self.internal_token = internal_token if internal_token is not None else settings.internal_api_token
    self.api_key = api_key if api_key is not None else settings.core_api_key
    policies = document.get("policies", {}) if isinstance(document.get("policies"), dict) else {}
    self.timeout_seconds = float(policies.get("default_timeout_seconds", timeout_seconds))

  @classmethod
  def create_for_mcp(
    cls,
    *,
    base_url: str | None = None,
    api_prefix: str | None = None,
    internal_token: str | None = None,
    api_key: str | None = None,
    timeout_seconds: float = 30.0,
  ) -> "PlatformApiClient":
    if not cls._called_from_mcp_server():
      raise PlatformApiError("PlatformApiClient.create_for_mcp is restricted to mcp_server | blocked_by=mcp")
    return cls(
      base_url=base_url,
      api_prefix=api_prefix,
      internal_token=internal_token,
      api_key=api_key,
      timeout_seconds=timeout_seconds,
      _trust_token=cls._INTERNAL_TRUST_TOKEN,
    )

  @staticmethod
  def _called_from_mcp_server() -> bool:
    for frame in inspect.stack()[1:8]:
      module = inspect.getmodule(frame.frame)
      module_name = str(getattr(module, "__name__", "") or "")
      filename = str(getattr(frame, "filename", "") or "")
      if module_name == "services.mcp_server":
        return True
      if filename.endswith("/services/mcp_server.py") or filename.endswith("\\services\\mcp_server.py"):
        return True
    return False

  @property
  def enabled(self) -> bool:
    return settings.platform_api_mode != "mock"

  def _headers(self) -> dict[str, str]:
    headers = {
      "Accept": "application/json",
      "Content-Type": "application/json",
      "X-Request-Id": f"hap-agent-{uuid.uuid4().hex[:12]}",
    }
    if self.internal_token:
      headers["X-Internal-Token"] = self.internal_token
    if self.api_key:
      headers["X-API-Key"] = self.api_key
    return headers

  def _build_url(self, path: str, path_params: dict[str, Any] | None = None) -> str:
    resolved = str(path)
    for key, value in (path_params or {}).items():
      resolved = resolved.replace(f"{{{key}}}", str(value))
    if not resolved.startswith("/"):
      resolved = f"/{resolved}"
    prefix = self.api_prefix if self.api_prefix.startswith("/") else f"/{self.api_prefix}"
    if resolved.startswith(prefix):
      return f"{self.base_url}{resolved}"
    return f"{self.base_url}{prefix}{resolved}"

  def request(
    self,
    binding: dict[str, Any],
    *,
    path_params: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
  ) -> dict[str, Any]:
    method = str(binding.get("method") or "GET").upper()
    url = self._build_url(str(binding.get("path") or "/"), path_params)
    with httpx.Client(timeout=self.timeout_seconds) as client:
      response = client.request(method, url, headers=self._headers(), params=query or None, json=body)
    if response.status_code >= 400:
      detail = response.text[:500]
      raise PlatformApiError(f"{method} {url} failed ({response.status_code}): {detail}")
    try:
      payload = response.json()
    except ValueError as exc:
      raise PlatformApiError(f"{method} {url} returned non-JSON response") from exc
    if not isinstance(payload, dict):
      raise PlatformApiError(f"{method} {url} returned unexpected payload")
    if payload.get("code") not in (0, None) and payload.get("message") not in ("success", "ok"):
      raise PlatformApiError(str(payload.get("message") or payload.get("detail") or "platform api error"))
    return payload

  def call_binding(
    self,
    tool_name: str,
    *,
    path_params: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
  ) -> dict[str, Any]:
    binding = resolve_binding(tool_name)
    if binding is None:
      raise PlatformApiError(f"no platform api binding for tool: {tool_name}")
    return self.request(binding, path_params=path_params, query=query, body=body)

  def list_datasets(self, *, page_num: int = 1, page_size: int = 10, keyword: str | None = None) -> dict[str, Any]:
    query: dict[str, Any] = {"pageNum": page_num, "pageSize": page_size}
    if keyword:
      query["keyword"] = keyword
    return self.call_binding("platform_api.datasets.list", query=query)

  def split_dataset(self, dataset_id: int | str, *, train_ratio: float = 0.7, val_ratio: float = 0.15, test_ratio: float = 0.15, random_seed: int = 42) -> dict[str, Any]:
    body = {
      "trainRatio": train_ratio,
      "valRatio": val_ratio,
      "testRatio": test_ratio,
      "randomSeed": random_seed,
    }
    return self.call_binding(
      "dataset_version_create",
      path_params={"dataset_id": int(dataset_id)},
      body=body,
    )

  def create_training_job(self, body: dict[str, Any]) -> dict[str, Any]:
    return self.call_binding("training_job_create", body=body)

  def get_training_job(self, job_id: str) -> dict[str, Any]:
    return self.call_binding("training_job_status", path_params={"job_id": job_id})

  def get_json_path(self, path: str, *, query: dict[str, Any] | None = None) -> Any:
    url = self._build_url(path)
    with httpx.Client(timeout=self.timeout_seconds) as client:
      response = client.request("GET", url, headers=self._headers(), params=query or None)
    if response.status_code >= 400:
      detail = response.text[:500]
      raise PlatformApiError(f"GET {url} failed ({response.status_code}): {detail}")
    try:
      return response.json()
    except ValueError as exc:
      raise PlatformApiError(f"GET {url} returned non-JSON response") from exc

  def list_training_jobs(self, *, page_num: int = 1, page_size: int = 20, status: str | None = None) -> dict[str, Any]:
    query: dict[str, Any] = {"pageNum": page_num, "pageSize": page_size}
    if status:
      query["status"] = status
    return self.call_binding("platform_task_status", query=query)

  def search_lineage(self, query_text: str) -> dict[str, Any]:
    return self.call_binding("platform_lineage_query", query={"q": query_text})

  def get_lineage_graph(self, *, project_id: int | str | None = None) -> dict[str, Any]:
    query = {"project_id": int(project_id)} if project_id is not None else None
    return self.call_binding("platform_api.lineage.graph.get", query=query)

  def get_lineage_node(self, node_id: str) -> dict[str, Any]:
    return self.call_binding("platform_api.lineage.node.get", path_params={"node_id": node_id})

  def get_lineage_impact(self, node_id: str) -> dict[str, Any]:
    return self.call_binding("platform_api.lineage.impact", path_params={"node_id": node_id})

  def list_model_versions(
    self,
    *,
    page_num: int = 1,
    page_size: int = 20,
    model_name: str | None = None,
    status: str | None = None,
  ) -> dict[str, Any]:
    query: dict[str, Any] = {"pageNum": page_num, "pageSize": page_size}
    if model_name:
      query["modelName"] = model_name
    if status:
      query["status"] = status
    return self.call_binding("model_versions_list", query=query)

  def list_inference_services(
    self,
    *,
    page_num: int = 1,
    page_size: int = 20,
    model_name: str | None = None,
    status: str | None = None,
  ) -> dict[str, Any]:
    query: dict[str, Any] = {"pageNum": page_num, "pageSize": page_size}
    if model_name:
      query["modelName"] = model_name
    if status:
      query["status"] = status
    return self.call_binding("inference_services_list", query=query)

  def get_inference_service(self, name: str) -> dict[str, Any]:
    return self.call_binding("inference_service_status", path_params={"name": name})

  def get_model_version_report(self, version_id: str) -> dict[str, Any]:
    return self.call_binding("model_evaluation_query", path_params={"version_id": version_id})

  def register_model_version(self, body: dict[str, Any]) -> dict[str, Any]:
    return self.call_binding("model_version_register", body=body)

  def promote_model_version(self, version_id: str | int) -> dict[str, Any]:
    return self.call_binding("model_publish_request", path_params={"version_id": version_id})

  def evaluate_model_version(self, body: dict[str, Any]) -> dict[str, Any]:
    return self.call_binding("platform_api.model_versions.evaluate", body=body)

  def create_inference_service(self, body: dict[str, Any]) -> dict[str, Any]:
    return self.call_binding("inference_service_deploy", body=body)

  def invoke_inference(self, service_name: str, body: dict[str, Any]) -> dict[str, Any]:
    return self.call_binding(
      "online_inference_invoke",
      path_params={"name": service_name},
      body=body,
    )

  def get_governance_summary(self) -> dict[str, Any]:
    return self.call_binding("model_governance_audit_query")

  def query_model_monitor(
    self,
    *,
    model_id: str | None = None,
    service_id: str | None = None,
    status: str | None = None,
  ) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if model_id:
      query["modelId"] = model_id
    if service_id:
      query["serviceId"] = service_id
    if status:
      query["status"] = status
    return self.call_binding("model_monitor_query", query=query or None)

  def create_lineage_project(self, body: dict[str, Any]) -> dict[str, Any]:
    return self.call_binding("lineage_project_create", body=body)

  def list_inference_services_flat(self) -> list[dict[str, Any]]:
    payload = self.get_json_path("/all-services")
    if isinstance(payload, list):
      return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
      data = payload.get("data")
      if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def get_platform_api_client() -> PlatformApiClient:
  return PlatformApiClient.create_for_mcp()
