from __future__ import annotations

from typing import Any, Callable

from services.audit_store import audit_store
from services.catalog_schema import (
    validate_lineage_catalog,
    validate_platform_services_catalog,
    validate_task_status_catalog,
)
from services.platform_api_client import PlatformApiClient, PlatformApiError
from services.task_catalog import task_catalog


class MCPReadonlyContractClient:
    """
    Readonly MCP contract client.

    This client encapsulates readonly business querying logic so MCPServer can
    stay focused on orchestration, policy checks, auth and audit envelopeing.
    """

    def __init__(
        self,
        *,
        platform_probe: Any,
        resolve_mock_payload: Callable[..., dict[str, Any]],
        live_or_mock: Callable[..., dict[str, Any]],
        unwrap_platform_data: Callable[[dict[str, Any]], Any],
        page_list: Callable[[dict[str, Any]], tuple[list[Any], int]],
        extract_lineage_query: Callable[[dict[str, Any]], str],
        normalize_mock_contract: Callable[[str, dict[str, Any]], dict[str, Any]],
    ) -> None:
        self.platform_probe = platform_probe
        self._resolve_mock_payload = resolve_mock_payload
        self._live_or_mock = live_or_mock
        self._unwrap_platform_data = unwrap_platform_data
        self._page_list = page_list
        self._extract_lineage_query = extract_lineage_query
        self._normalize_mock_contract = normalize_mock_contract

    def call_service_inventory(self, payload: dict[str, Any]) -> dict[str, Any]:
        def _mock(payload_data: dict[str, Any]) -> dict[str, Any]:
            probe_result = self.platform_probe.probe_all()
            result = self._resolve_mock_payload(
                "platform.service.inventory",
                payload_data,
                fallback={
                    "services": probe_result.get("services", []),
                    "summary": probe_result.get("summary") or "平台服务健康检测完成",
                    "probe_source": probe_result.get("source"),
                },
                scenario=str(payload_data.get("scenario") or "query_platform_services"),
            )
            result["probe_source"] = str(result.get("probe_source") or probe_result.get("source") or "mock")
            validate_platform_services_catalog(result)
            return result

        def _live(client: PlatformApiClient, payload_data: dict[str, Any]) -> dict[str, Any]:
            items: list[dict[str, Any]] = []
            try:
                items = client.list_inference_services_flat()
            except Exception:
                items = []
            if not items and hasattr(client, "list_inference_services"):
                try:
                    envelope = client.list_inference_services()
                    data = self._unwrap_platform_data(envelope)
                    if isinstance(data, dict):
                        raw_list = data.get("list") if isinstance(data.get("list"), list) else data.get("items")
                        if isinstance(raw_list, list):
                            items = [item for item in raw_list if isinstance(item, dict)]
                    elif isinstance(data, list):
                        items = [item for item in data if isinstance(item, dict)]
                except Exception:
                    items = []
            services = []
            for item in items:
                name = str(item.get("name") or item.get("serviceName") or "unknown")
                status = str(item.get("status") or item.get("phase") or "unknown")
                url = str(item.get("url") or item.get("endpoint") or "")
                host = url.split("://")[-1].split("/")[0].split(":")[0] if url else "platform"
                port_raw = url.split(":")[-1] if ":" in url else ""
                port = int(port_raw) if port_raw.isdigit() else 0
                services.append(
                    {
                        "name": name,
                        "status": status,
                        "host": host,
                        "port": port,
                        "reachable": status.lower() in {"running", "ready", "healthy", "active", "succeeded"},
                        "url": url,
                    }
                )
            result = {
                "source": "real",
                "real_execution": True,
                "resource_key": "platform.service.inventory",
                "summary": f"已查询 {len(services)} 个平台/推理服务实例",
                "total": len(services),
                "healthy": sum(1 for item in services if item.get("reachable")),
                "down": sum(1 for item in services if not item.get("reachable")),
                "services": services,
            }
            validate_platform_services_catalog(result)
            return result

        return self._live_or_mock(
            tool_name="platform_service_inventory",
            live_builder=_live,
            mock_builder=_mock,
            payload=payload,
        )

    def call_platform_audit_query(self, payload: dict[str, Any]) -> dict[str, Any]:
        def _mock(payload_data: dict[str, Any]) -> dict[str, Any]:
            trace_id = payload_data.get("trace_id")
            if trace_id:
                items = audit_store.list_by_trace_id(str(trace_id), limit=payload_data.get("limit"))
            else:
                items = audit_store.list(limit=payload_data.get("limit"))
            result = self._resolve_mock_payload(
                "platform.audit.timeline",
                payload_data,
                fallback={"trace_id": trace_id, "count": len(items), "items": items},
                scenario=str(payload_data.get("scenario") or "audit_replay"),
            )
            result["trace_id"] = trace_id
            result["count"] = len(items)
            result["items"] = items
            return self._normalize_mock_contract("platform_audit_query", result)

        def _live(client: PlatformApiClient, payload_data: dict[str, Any]) -> dict[str, Any]:
            items = audit_store.list(limit=payload_data.get("limit"))
            return {
                "source": "real",
                "real_execution": True,
                "resource_key": "platform.audit.timeline",
                "trace_id": payload_data.get("trace_id"),
                "count": len(items),
                "items": items,
                "platform_response": client.get_governance_summary(),
            }

        return self._live_or_mock(
            tool_name="platform_audit_query",
            live_builder=_live,
            mock_builder=_mock,
            payload=payload,
        )

    def call_task_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        skill_id = str(payload.get("skill_id") or "query_task_status")

        def _mock(payload_data: dict[str, Any]) -> dict[str, Any]:
            result = task_catalog.build(skill_id)
            validate_task_status_catalog(result)
            payload_result = self._resolve_mock_payload(
                "platform.task.status",
                payload_data,
                fallback={
                    "skill_id": skill_id,
                    "summary": result.get("summary", ""),
                    "stats": result.get("stats", {}),
                    "items": result.get("items", []),
                },
                scenario=str(payload_data.get("scenario") or skill_id),
            )
            payload_result["skill_id"] = skill_id
            payload_result["summary"] = str(payload_result.get("summary") or result.get("summary", ""))
            payload_result["stats"] = payload_result.get("stats") or result.get("stats", {})
            payload_result["items"] = payload_result.get("items") or result.get("items", [])
            payload_result["payload"] = payload_result.get("payload") or result
            return payload_result

        def _live(client: PlatformApiClient, payload_data: dict[str, Any]) -> dict[str, Any]:
            status_filter = str(payload_data.get("status") or "").strip() or None
            envelope = client.list_training_jobs(page_num=1, page_size=50, status=status_filter)
            items, total = self._page_list(envelope)
            stats: dict[str, int] = {"total": total}
            for item in items:
                if not isinstance(item, dict):
                    continue
                status = str(item.get("status") or "unknown").lower()
                stats[status] = stats.get(status, 0) + 1
            summary = f"共 {total} 个训练任务"
            if stats.get("running") or stats.get("pending"):
                summary += f"，运行中 {stats.get('running', 0) + stats.get('pending', 0)}"
            catalog = {
                "source": "real",
                "summary": summary,
                "stats": stats,
                "items": items,
            }
            validate_task_status_catalog(catalog)
            return {
                "source": "real",
                "real_execution": True,
                "resource_key": "platform.task.status",
                "skill_id": skill_id,
                "summary": summary,
                "stats": stats,
                "items": items,
                "payload": catalog,
                "platform_response": envelope,
            }

        return self._live_or_mock(
            tool_name="platform_task_status",
            live_builder=_live,
            mock_builder=_mock,
            payload=payload,
        )

    def call_lineage_query(self, payload: dict[str, Any]) -> dict[str, Any]:
        skill_id = str(payload.get("skill_id") or "query_lineage")

        def _mock(payload_data: dict[str, Any]) -> dict[str, Any]:
            result = task_catalog.build(skill_id)
            validate_lineage_catalog(result)
            payload_result = self._resolve_mock_payload(
                "platform.lineage.graph",
                payload_data,
                fallback={"skill_id": skill_id, "summary": result.get("summary", ""), "lineage": result.get("lineage", {})},
                scenario=str(payload_data.get("scenario") or skill_id),
            )
            payload_result["skill_id"] = skill_id
            payload_result["summary"] = str(payload_result.get("summary") or result.get("summary", ""))
            payload_result["lineage"] = payload_result.get("lineage") or result.get("lineage", {})
            payload_result["payload"] = payload_result.get("payload") or result
            return payload_result

        def _live(client: PlatformApiClient, payload_data: dict[str, Any]) -> dict[str, Any]:
            node_id = str(payload_data.get("node_id") or payload_data.get("entity") or "").strip()
            project_id = payload_data.get("project_id") or payload_data.get("projectId")
            query_text = self._extract_lineage_query(payload_data)

            if node_id and not query_text:
                envelope = client.get_lineage_impact(node_id)
                graph = self._unwrap_platform_data(envelope)
                if not isinstance(graph, dict):
                    graph = {}
                downstream = graph.get("downstream") or graph.get("nodes") or []
                upstream = graph.get("upstream") or []
                lineage = {
                    "entity": node_id,
                    "current": graph.get("current") or {"id": node_id, "label": node_id, "type": "node"},
                    "upstream": upstream if isinstance(upstream, list) else [],
                    "downstream": downstream if isinstance(downstream, list) else [],
                    "edges": graph.get("edges") or [],
                }
                summary = f"已查询节点 {node_id} 的血缘影响范围"
            elif project_id:
                envelope = client.get_lineage_graph(project_id=project_id)
                graph = self._unwrap_platform_data(envelope)
                if not isinstance(graph, dict):
                    graph = {}
                nodes = graph.get("nodes") or []
                lineage = {
                    "entity": f"project-{project_id}",
                    "current": {"id": f"project-{project_id}", "label": f"项目 {project_id}", "type": "project"},
                    "upstream": [],
                    "downstream": nodes if isinstance(nodes, list) else [],
                    "edges": graph.get("edges") or [],
                }
                summary = f"已加载项目 {project_id} 的血缘图（{len(lineage['downstream'])} 个节点）"
            else:
                if not query_text:
                    raise PlatformApiError("lineage query requires q/entity/user_input or node_id/project_id")
                envelope = client.search_lineage(query_text)
                data = self._unwrap_platform_data(envelope)
                results = data.get("results") if isinstance(data, dict) else []
                if not isinstance(results, list):
                    results = []
                downstream = [
                    {
                        "id": str(item.get("id") or ""),
                        "label": str(item.get("name") or item.get("id") or ""),
                        "type": str(item.get("type") or "node"),
                        "meta": item.get("meta") or {},
                    }
                    for item in results
                    if isinstance(item, dict)
                ]
                current = downstream[0] if downstream else {"id": query_text, "label": query_text, "type": "search"}
                lineage = {
                    "entity": query_text,
                    "current": current,
                    "upstream": [],
                    "downstream": downstream,
                    "edges": [],
                }
                summary = f"血缘搜索「{query_text}」命中 {len(downstream)} 个节点"

            catalog = {"source": "real", "summary": summary, "lineage": lineage}
            validate_lineage_catalog(catalog)
            return {
                "source": "real",
                "real_execution": True,
                "resource_key": "platform.lineage.graph",
                "skill_id": skill_id,
                "summary": summary,
                "lineage": lineage,
                "payload": catalog,
                "platform_response": envelope,
            }

        return self._live_or_mock(
            tool_name="platform_lineage_query",
            live_builder=_live,
            mock_builder=_mock,
            payload=payload,
        )

    def call_dataset_catalog_query(self, payload: dict[str, Any]) -> dict[str, Any]:
        def _mock(payload_data: dict[str, Any]) -> dict[str, Any]:
            dataset_id = str(payload_data.get("dataset_id") or "dataset-demo")
            result = self._resolve_mock_payload(
                "platform.dataset.catalog",
                payload_data,
                fallback={
                    "dataset_id": dataset_id,
                    "datasets": [{"dataset_id": dataset_id, "name": "demo_training_dataset", "latest_version": "dv-001", "status": "ready"}],
                },
            )
            result["dataset_id"] = str(result.get("dataset_id") or dataset_id)
            return result

        def _live(client: PlatformApiClient, payload_data: dict[str, Any]) -> dict[str, Any]:
            keyword = str(payload_data.get("keyword") or "").strip() or None
            if not keyword:
                raw_input = str(payload_data.get("user_input") or "").strip()
                if raw_input and len(raw_input) <= 64 and not any(
                    token in raw_input for token in ("准备", "发起", "训练任务", "帮我", "请")
                ):
                    keyword = raw_input
            envelope = client.list_datasets(page_num=1, page_size=10, keyword=keyword)
            data = self._unwrap_platform_data(envelope)
            items = data.get("list", []) if isinstance(data, dict) else data
            if not isinstance(items, list):
                items = []
            if not items and keyword:
                envelope = client.list_datasets(page_num=1, page_size=10, keyword=None)
                data = self._unwrap_platform_data(envelope)
                items = data.get("list", []) if isinstance(data, dict) else data
                if not isinstance(items, list):
                    items = []
            first_id = items[0].get("id") if items and isinstance(items[0], dict) else None
            return {
                "source": "real",
                "real_execution": True,
                "resource_key": "platform.dataset.catalog",
                "replaceable": False,
                "version": "1.0.0",
                "scenario": "query_platform_services",
                "data": {
                    "datasets": items,
                    "dataset_id": str(payload_data.get("dataset_id") or first_id or ""),
                    "keyword": keyword,
                    "summary": f"找到 {len(items)} 个数据集",
                },
                "payload": {"datasets": items, "keyword": keyword},
                "schema_ref": "platform.schema.platform.dataset.catalog",
                "fallback_to_real": False,
                "description": "dataset catalog real response",
                "status": "real",
                "platform_response": envelope,
            }

        return self._live_or_mock(
            tool_name="dataset_catalog_query",
            live_builder=_live,
            mock_builder=_mock,
            payload=payload,
        )

    def call_training_job_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        def _mock(payload_data: dict[str, Any]) -> dict[str, Any]:
            training_job_id = str(payload_data.get("training_job_id") or "tj-demo")
            result = self._resolve_mock_payload(
                "platform.training.job.status",
                payload_data,
                fallback={"training_job_id": training_job_id, "status": "succeeded", "metrics": {"accuracy": 0.97, "loss": 0.08}},
            )
            result["training_job_id"] = str(result.get("training_job_id") or training_job_id)
            return self._normalize_mock_contract("training_job_status", result)

        def _live(client: PlatformApiClient, payload_data: dict[str, Any]) -> dict[str, Any]:
            training_job_id = str(payload_data.get("training_job_id") or payload_data.get("job_id") or "")
            if not training_job_id:
                raise PlatformApiError("training_job_id is required")
            envelope = client.get_training_job(training_job_id)
            data = self._unwrap_platform_data(envelope)
            return {
                "source": "real",
                "real_execution": True,
                "resource_key": "platform.training.job.status",
                "replaceable": False,
                "version": "1.0.0",
                "scenario": "training_job_status",
                "data": {"training_job_id": training_job_id, "status": str((data or {}).get("status") or "unknown"), "job": data},
                "payload": {"job": data, "training_job_id": training_job_id},
                "schema_ref": "platform.schema.platform.training.job.status",
                "fallback_to_real": False,
                "description": "training job status real response",
                "status": "real",
                "platform_response": envelope,
            }

        return self._live_or_mock(
            tool_name="training_job_status",
            live_builder=_live,
            mock_builder=_mock,
            payload=payload,
        )

    def call_model_evaluation_query(self, payload: dict[str, Any]) -> dict[str, Any]:
        def _mock(payload_data: dict[str, Any]) -> dict[str, Any]:
            model_version_id = str(payload_data.get("model_version_id") or payload_data.get("version_id") or "mv-demo")
            result = self._resolve_mock_payload(
                "platform.model.evaluation.query",
                payload_data,
                fallback={"model_version_id": model_version_id, "metrics": {"accuracy": 0.96, "auc": 0.93}, "passed": True},
            )
            result["model_version_id"] = str(result.get("model_version_id") or model_version_id)
            return result

        def _live(client: PlatformApiClient, payload_data: dict[str, Any]) -> dict[str, Any]:
            version_id = str(payload_data.get("model_version_id") or payload_data.get("version_id") or "")
            if not version_id:
                raise PlatformApiError("model_version_id is required")
            envelope = client.get_model_version_report(version_id)
            report = self._unwrap_platform_data(envelope)
            metrics = report if isinstance(report, dict) else {}
            return {
                "source": "real",
                "real_execution": True,
                "resource_key": "platform.model.evaluation.query",
                "replaceable": False,
                "version": "1.0.0",
                "scenario": "model_evaluation_query",
                "data": {"model_version_id": version_id, "metrics": metrics.get("metrics") or metrics, "passed": metrics.get("passed", True), "report": metrics},
                "payload": {"report": metrics, "model_version_id": version_id},
                "schema_ref": "platform.schema.platform.model.evaluation.query",
                "fallback_to_real": False,
                "description": "model evaluation query real response",
                "status": "real",
                "platform_response": envelope,
            }

        return self._live_or_mock(
            tool_name="model_evaluation_query",
            live_builder=_live,
            mock_builder=_mock,
            payload=payload,
        )

    def call_model_versions_list(self, payload: dict[str, Any]) -> dict[str, Any]:
        def _mock(payload_data: dict[str, Any]) -> dict[str, Any]:
            model_name = str(payload_data.get("model_name") or "demo-model")
            result = self._resolve_mock_payload(
                "platform.model.versions.list",
                payload_data,
                fallback={"model_name": model_name, "total": 1, "items": [{"id": "mv-demo", "model_name": model_name, "version": "v1", "status": "ready"}]},
                scenario=str(payload_data.get("scenario") or "ml_lifecycle_minimum_closed_loop"),
            )
            result["model_name"] = str(result.get("model_name") or model_name)
            return result

        def _live(client: PlatformApiClient, payload_data: dict[str, Any]) -> dict[str, Any]:
            model_name = str(payload_data.get("model_name") or payload_data.get("modelName") or "").strip() or None
            status = str(payload_data.get("status") or "").strip() or None
            envelope = client.list_model_versions(page_num=1, page_size=20, model_name=model_name, status=status)
            items, total = self._page_list(envelope)
            return {
                "source": "real",
                "real_execution": True,
                "resource_key": "platform.model.versions.list",
                "model_name": model_name,
                "total": total,
                "items": items,
                "platform_response": envelope,
            }

        return self._live_or_mock(
            tool_name="model_versions_list",
            live_builder=_live,
            mock_builder=_mock,
            payload=payload,
        )

    def call_inference_services_list(self, payload: dict[str, Any]) -> dict[str, Any]:
        def _mock(payload_data: dict[str, Any]) -> dict[str, Any]:
            return self._resolve_mock_payload(
                "platform.inference.services.list",
                payload_data,
                fallback={"total": 1, "items": [{"name": "demo-service", "status": "running", "model_name": "demo-model"}]},
                scenario=str(payload_data.get("scenario") or "ml_lifecycle_minimum_closed_loop"),
            )

        def _live(client: PlatformApiClient, payload_data: dict[str, Any]) -> dict[str, Any]:
            model_name = str(payload_data.get("model_name") or payload_data.get("modelName") or "").strip() or None
            status = str(payload_data.get("status") or "").strip() or None
            envelope = client.list_inference_services(page_num=1, page_size=20, model_name=model_name, status=status)
            items, total = self._page_list(envelope)
            return {
                "source": "real",
                "real_execution": True,
                "resource_key": "platform.inference.services.list",
                "total": total,
                "items": items,
                "platform_response": envelope,
            }

        return self._live_or_mock(
            tool_name="inference_services_list",
            live_builder=_live,
            mock_builder=_mock,
            payload=payload,
        )

    def call_inference_service_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        def _mock(payload_data: dict[str, Any]) -> dict[str, Any]:
            service_id = str(payload_data.get("service_id") or payload_data.get("name") or "svc-demo")
            result = self._resolve_mock_payload(
                "platform.inference.service.status",
                payload_data,
                fallback={"service_id": service_id, "status": "healthy", "endpoint": f"https://inference.example/{service_id}"},
            )
            result["service_id"] = str(result.get("service_id") or service_id)
            return result

        def _live(client: PlatformApiClient, payload_data: dict[str, Any]) -> dict[str, Any]:
            name = str(payload_data.get("name") or payload_data.get("service_name") or payload_data.get("service_id") or "")
            if not name:
                raise PlatformApiError("service name is required")
            envelope = client.get_inference_service(name)
            service = self._unwrap_platform_data(envelope)
            if not isinstance(service, dict):
                service = {}
            return {
                "source": "real",
                "real_execution": True,
                "resource_key": "platform.inference.service.status",
                "replaceable": False,
                "version": "1.0.0",
                "scenario": "inference_service_status",
                "data": {
                    "service_id": name,
                    "name": name,
                    "status": str(service.get("status") or "unknown"),
                    "endpoint": str(service.get("url") or service.get("endpoint") or ""),
                    "service": service,
                },
                "payload": {"service": service, "service_id": name},
                "schema_ref": "platform.schema.platform.inference.service.status",
                "fallback_to_real": False,
                "description": "inference service status real response",
                "status": "real",
                "platform_response": envelope,
            }

        return self._live_or_mock(
            tool_name="inference_service_status",
            live_builder=_live,
            mock_builder=_mock,
            payload=payload,
        )

    def call_model_monitor_query(self, payload: dict[str, Any]) -> dict[str, Any]:
        def _mock(payload_data: dict[str, Any]) -> dict[str, Any]:
            model_id = str(payload_data.get("model_id") or payload_data.get("modelId") or "model-demo")
            result = self._resolve_mock_payload(
                "platform.model.monitor.query",
                payload_data,
                fallback={
                    "model_id": model_id,
                    "monitor_summary": {"status": "healthy", "alert_count": 0},
                    "drift_report": {"drift_score": 0.03, "threshold": 0.1},
                },
            )
            result["model_id"] = str(result.get("model_id") or model_id)
            return self._normalize_mock_contract("model_monitor_query", result)

        def _live(client: PlatformApiClient, payload_data: dict[str, Any]) -> dict[str, Any]:
            model_id = str(payload_data.get("model_id") or payload_data.get("modelId") or "").strip()
            service_id = str(payload_data.get("service_id") or payload_data.get("serviceId") or "").strip()
            status = str(payload_data.get("status") or "").strip() or None
            envelope = client.query_model_monitor(model_id=model_id or None, service_id=service_id or None, status=status)
            data = self._unwrap_platform_data(envelope)
            monitor = data if isinstance(data, dict) else {}
            monitor_summary = monitor.get("monitor_summary") or monitor.get("summary") or monitor
            drift_report = monitor.get("drift_report") or {}
            return {
                "source": "real",
                "real_execution": True,
                "resource_key": "platform.model.monitor.query",
                "replaceable": False,
                "version": "1.0.0",
                "scenario": "model_monitor_query",
                "data": {
                    "model_id": model_id or monitor.get("model_id") or "",
                    "service_id": service_id or monitor.get("service_id") or "",
                    "monitor_summary": monitor_summary,
                    "drift_report": drift_report,
                },
                "payload": {"monitor_summary": monitor_summary, "drift_report": drift_report},
                "schema_ref": "platform.schema.platform.model.monitor.query",
                "fallback_to_real": False,
                "description": "model monitor query real response",
                "status": "real",
                "platform_response": envelope,
            }

        return self._live_or_mock(
            tool_name="model_monitor_query",
            live_builder=_live,
            mock_builder=_mock,
            payload=payload,
        )

    def call_model_governance_audit_query(self, payload: dict[str, Any]) -> dict[str, Any]:
        def _mock(payload_data: dict[str, Any]) -> dict[str, Any]:
            model_id = str(payload_data.get("model_id") or payload_data.get("model_name") or "model-demo")
            result = self._resolve_mock_payload(
                "platform.model.governance.audit.query",
                payload_data,
                fallback={
                    "model_id": model_id,
                    "governance_findings": [
                        {"type": "policy_check", "status": "pass"},
                        {"type": "audit_check", "status": "pass"},
                    ],
                },
            )
            result["model_id"] = str(result.get("model_id") or model_id)
            return self._normalize_mock_contract("model_governance_audit_query", result)

        def _live(client: PlatformApiClient, payload_data: dict[str, Any]) -> dict[str, Any]:
            envelope = client.get_governance_summary()
            summary = self._unwrap_platform_data(envelope)
            model_name = str(payload_data.get("model_name") or payload_data.get("model_id") or "")
            findings = [
                {"type": "platform_overview", "status": "ok", "detail": summary},
            ]
            if model_name:
                try:
                    versions_envelope = client.list_model_versions(page_num=1, page_size=5, model_name=model_name)
                    _, total = self._page_list(versions_envelope)
                    findings.append({"type": "model_version_count", "status": "ok", "count": total})
                except PlatformApiError as exc:
                    findings.append({"type": "model_version_count", "status": "degraded", "detail": str(exc)})
            return {
                "source": "real",
                "real_execution": True,
                "resource_key": "platform.model.governance.audit.query",
                "replaceable": False,
                "version": "1.0.0",
                "scenario": "model_governance_audit_query",
                "data": {"model_id": model_name or "platform", "governance_findings": findings, "summary": summary},
                "payload": {"governance_findings": findings, "summary": summary},
                "schema_ref": "platform.schema.platform.model.governance.audit.query",
                "fallback_to_real": False,
                "description": "model governance audit query real response",
                "status": "real",
                "platform_response": envelope,
            }

        return self._live_or_mock(
            tool_name="model_governance_audit_query",
            live_builder=_live,
            mock_builder=_mock,
            payload=payload,
        )
