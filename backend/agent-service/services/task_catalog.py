from __future__ import annotations

from typing import Any

from services.catalog_schema import (
    validate_lineage_catalog,
    validate_platform_services_catalog,
    validate_task_status_catalog,
)
from services.mock_protocol import StructuredDataEnvelope, StructuredDataProtocol
from services.platform_probe import PlatformProbe


class TaskCatalog:
    def __init__(self) -> None:
        self._probe = PlatformProbe()

    def build(self, skill_id: str) -> dict[str, Any]:
        if skill_id == "query_task_status":
            envelope = StructuredDataEnvelope(
                resource_key="platform.task.status",
                source="mock",
                replaceable=True,
                version="1.0.0",
                scenario="query_task_status",
                payload={
                    "summary": "任务状态统计与运行情况已汇总",
                    "source": "mock",
                    "read_only": True,
                    "stats": {"total": 24, "success": 18, "failed": 2, "running": 4},
                    "items": [
                        {"task_name": "daily_sales_sync", "status": "running", "progress": "72%"},
                        {"task_name": "user_profile_build", "status": "success", "progress": "100%"},
                        {"task_name": "feature_quality_check", "status": "failed", "progress": "100%"},
                    ],
                },
                schema_ref="mock.schema.platform.task.status",
                fallback_to_real=False,
                description="任务状态统计与运行情况 mock 数据",
            ).to_dict()
            envelope["summary"] = envelope["payload"]["summary"]
            envelope["stats"] = envelope["payload"]["stats"]
            envelope["items"] = envelope["payload"]["items"]
            envelope["source"] = envelope["payload"]["source"]
            validate_task_status_catalog(envelope)
            return {
                "source": envelope["source"],
                "summary": envelope["summary"],
                "stats": envelope["stats"],
                "items": envelope["items"],
                "read_only": envelope["payload"]["read_only"],
                "payload": envelope["payload"],
            }
        if skill_id == "query_platform_services":
            probe_result = self._probe.probe_all()
            payload = {
                **probe_result,
                "summary": "平台服务健康状态已汇总",
                "source": "mock",
                "probe_source": probe_result.get("source"),
                "read_only": True,
            }
            validate_platform_services_catalog(payload)
            return StructuredDataEnvelope(
                resource_key="platform.service.inventory",
                source="mock",
                replaceable=True,
                version="1.0.0",
                scenario="query_platform_services",
                payload=payload,
                schema_ref="mock.schema.platform.service.inventory",
                fallback_to_real=False,
                description="平台服务目录与健康状态 mock 数据",
            ).to_dict()
        if skill_id == "query_lineage":
            payload = {
                "summary": "数据血缘链路已汇总",
                "source": "mock",
                "read_only": True,
                "lineage": {
                    "upstream": [
                        {"type": "table", "name": "ods.orders", "description": "订单原始表"},
                        {"type": "table", "name": "ods.users", "description": "用户原始表"},
                    ],
                    "current": {"type": "table", "name": "dwd.order_detail", "description": "订单明细宽表"},
                    "downstream": [
                        {"type": "table", "name": "ads.sales_dashboard", "description": "销售看板指标表"},
                        {"type": "task", "name": "daily_sales_report", "description": "每日销售报表任务"},
                    ],
                },
            }
            envelope = StructuredDataEnvelope(
                resource_key="platform.lineage.graph",
                source="mock",
                replaceable=True,
                version="1.0.0",
                scenario="query_lineage",
                payload=payload,
                schema_ref="mock.schema.platform.lineage.graph",
                fallback_to_real=False,
                description="数据血缘链路 mock 数据",
            ).to_dict()
            envelope["summary"] = envelope["payload"]["summary"]
            envelope["lineage"] = envelope["payload"]["lineage"]
            envelope["source"] = envelope["payload"]["source"]
            validate_lineage_catalog(envelope)
            return {
                "source": envelope["source"],
                "summary": envelope["summary"],
                "lineage": envelope["lineage"],
                "read_only": envelope["payload"]["read_only"],
                "payload": envelope["payload"],
            }
        fallback = StructuredDataEnvelope(
            resource_key=f"platform.{skill_id}",
            source="mock",
            replaceable=True,
            version="1.0.0",
            scenario=skill_id,
            payload={"summary": "no catalog result", "source": "mock", "read_only": True},
            schema_ref=f"mock.schema.platform.{skill_id}",
            fallback_to_real=False,
            description="fallback catalog result",
        ).to_dict()
        return fallback


task_catalog = TaskCatalog()
