from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from services.mock_protocol import StructuredDataEnvelope, StructuredDataProtocol


DEFAULT_ENVELOPE_VERSION = "1.0.0"


@dataclass
class MockResource:
    resource_key: str
    source: str
    replaceable: bool
    version: str
    scenario: str
    payload: dict[str, Any]
    schema_ref: str
    fallback_to_real: bool
    description: str
    status: str = "mock"

    def to_dict(self) -> dict[str, Any]:
        return StructuredDataEnvelope(
            resource_key=self.resource_key,
            source=self.source,
            replaceable=self.replaceable,
            version=self.version,
            scenario=self.scenario,
            payload=self.payload,
            schema_ref=self.schema_ref,
            fallback_to_real=self.fallback_to_real,
            description=self.description,
            status=self.status,
        ).to_dict()


class MockProvider:
    """Centralized mock data provider for first-stage stable demo."""

    def __init__(self, data_dir: str | None = None) -> None:
        self.data_dir = Path(data_dir or "mock_data")
        self.catalog = self._load_catalog()

    def _load_catalog(self) -> list[MockResource]:
        catalog_file = self.data_dir / "catalog.yaml"
        if not catalog_file.exists():
            return self._build_default_catalog()

        with open(catalog_file, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}

        resources = loaded.get("resources", []) if isinstance(loaded, dict) else []
        catalog: list[MockResource] = []
        for item in resources:
            resource = self._from_dict(item)
            if resource is not None:
                catalog.append(resource)

        return catalog or self._build_default_catalog()

    def _build_default_catalog(self) -> list[MockResource]:
        now = datetime.now(timezone.utc).isoformat()
        return [
            MockResource(
                resource_key="platform.code.search",
                source="mock",
                replaceable=True,
                version="1.0.0",
                scenario="platform_ml_lifecycle_analysis",
                payload={
                    "query": "service health",
                    "results": [
                        {"path": "backend/agent-service/main.py", "line": 1, "snippet": "from fastapi import FastAPI"}
                    ],
                    "updated_at": now,
                },
                schema_ref="mock.schema.platform.code.search",
                fallback_to_real=False,
                description="代码检索 mock 数据",
            ),
            MockResource(
                resource_key="platform.ml.pipeline.node.list",
                source="mock",
                replaceable=True,
                version="1.0.0",
                scenario="platform_ml_lifecycle_analysis",
                payload={
                    "nodes": [
                        {"id": "input", "name": "对话输入", "status": "ready"},
                        {"id": "skill", "name": "Skill 选择", "status": "ready"},
                        {"id": "workflow", "name": "Workflow 编排", "status": "ready"},
                    ],
                    "updated_at": now,
                },
                schema_ref="mock.schema.platform.ml.pipeline.node.list",
                fallback_to_real=False,
                description="平台 ML 生命周期链路分析所需的节点列表 mock 数据",
            ),
            MockResource(
                resource_key="platform.service.inventory",
                source="mock",
                replaceable=True,
                version="1.0.0",
                scenario="query_platform_services",
                payload={
                    "services": [
                        {"name": "agent-service", "status": "healthy", "source": "mock"},
                        {"name": "core-service", "status": "healthy", "source": "mock"},
                        {"name": "workflow-engine", "status": "degraded", "source": "mock"},
                    ]
                },
                schema_ref="mock.schema.platform.service.inventory",
                fallback_to_real=False,
                description="平台服务目录与健康状态 mock 数据",
            ),
            MockResource(
                resource_key="platform.audit.timeline",
                source="mock",
                replaceable=True,
                version="1.0.0",
                scenario="audit_replay",
                payload={"events": [], "source": "mock"},
                schema_ref="mock.schema.platform.audit.timeline",
                fallback_to_real=False,
                description="审计轨迹 mock 数据",
            ),
            MockResource(
                resource_key="platform.code.search",
                source="mock",
                replaceable=True,
                version="1.0.0",
                scenario="platform_ml_lifecycle_analysis",
                payload={"hits": [], "query": "", "source": "mock"},
                schema_ref="mock.schema.platform.code.search",
                fallback_to_real=False,
                description="代码检索 mock 数据",
            ),
            MockResource(
                resource_key="platform.dependency.graph",
                source="mock",
                replaceable=True,
                version="1.0.0",
                scenario="platform_ml_lifecycle_analysis",
                payload={"nodes": [], "edges": [], "source": "mock"},
                schema_ref="mock.schema.platform.dependency.graph",
                fallback_to_real=False,
                description="依赖图 mock 数据",
            ),
        ]

    def list_catalog(self) -> list[dict[str, Any]]:
        return [resource.to_dict() for resource in self.catalog]

    def _default_resource(self, resource_key: str, scenario: str | None = None) -> dict[str, Any]:
        return {
            "resource_key": resource_key,
            "source": "mock",
            "replaceable": True,
            "version": DEFAULT_ENVELOPE_VERSION,
            "scenario": scenario or "default",
            "payload": {},
            "schema_ref": f"mock.schema.{resource_key}",
            "fallback_to_real": False,
            "description": "fallback mock resource",
            "status": "mock",
        }

    def resolve_data(self, resource_key: str, scenario: str | None = None) -> dict[str, Any]:
        for item in self.catalog:
            if item.resource_key == resource_key and (scenario is None or item.scenario == scenario):
                return self._envelope(item.to_dict())
        return self._envelope(self._default_resource(resource_key, scenario=scenario))

    def resolve_envelope(self, resource_key: str, scenario: str | None = None) -> dict[str, Any]:
        return self.resolve_data(resource_key, scenario=scenario)

    def resolve_payload(self, resource_key: str, scenario: str | None = None) -> dict[str, Any]:
        resource = self.resolve_data(resource_key, scenario=scenario)
        payload = resource.get("payload")
        return payload if isinstance(payload, dict) else {}

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        created_at = datetime.now(timezone.utc).isoformat()
        resources = self.list_catalog()
        envelope = self._envelope({
            "resource_key": f"snapshot.{snapshot_id}",
            "source": "mock",
            "replaceable": True,
            "version": DEFAULT_ENVELOPE_VERSION,
            "scenario": snapshot_id,
            "payload": {
                "snapshot_id": snapshot_id,
                "created_at": created_at,
                "resources": resources,
            },
            "schema_ref": "mock.schema.snapshot",
            "fallback_to_real": False,
            "description": "mock snapshot envelope",
            "status": "mock",
        })
        envelope["snapshot_id"] = snapshot_id
        envelope["created_at"] = created_at
        envelope["resources"] = resources
        return envelope

    def get_trace(self, resource_key: str) -> dict[str, Any]:
        resource = self.resolve_data(resource_key)
        trace_id = f"trace_{resource_key.replace('.', '_')}"
        trace_resource_key = f"trace.{resource_key}"
        envelope = self._envelope({
            "resource_key": resource_key,
            "source": str(resource.get("source", "mock")),
            "replaceable": bool(resource.get("replaceable", True)),
            "version": str(resource.get("version", DEFAULT_ENVELOPE_VERSION)),
            "scenario": str(resource.get("scenario", "trace")),
            "payload": {
                "resource_key": resource_key,
                "trace_resource_key": trace_resource_key,
                "trace_id": trace_id,
                "source_trace": resource,
            },
            "schema_ref": "mock.schema.trace",
            "fallback_to_real": bool(resource.get("fallback_to_real", False)),
            "description": str(resource.get("description", "")),
            "status": str(resource.get("status", "mock")),
        })
        envelope["trace_id"] = trace_id
        return envelope

    def validate_schema(self, resource: dict[str, Any]) -> dict[str, Any]:
        validation = StructuredDataProtocol.validate_envelope(resource)
        return {
            "valid": validation["valid"],
            "missing": validation["missing"],
            "resource_key": validation["resource_key"],
            "source": validation["source"],
        }

    def _envelope(self, resource: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_envelope(resource)
        validation = StructuredDataProtocol.validate_envelope(normalized)
        if not validation["valid"]:
            raise ValueError(f"invalid structured data envelope: {validation['missing']}")
        return normalized

    def _normalize_envelope(self, resource: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(resource)
        normalized.setdefault("source", "mock")
        normalized.setdefault("replaceable", True)
        normalized.setdefault("version", DEFAULT_ENVELOPE_VERSION)
        normalized.setdefault("scenario", "default")
        normalized.setdefault("payload", {})
        normalized.setdefault("schema_ref", f"mock.schema.{str(normalized.get('resource_key') or 'unknown')}")
        normalized.setdefault("fallback_to_real", False)
        normalized.setdefault("description", "")
        normalized.setdefault("status", "mock")
        normalized.setdefault("trace_id", f"mock-trace-{str(normalized.get('resource_key') or 'unknown').replace('.', '-')}-{str(normalized.get('scenario') or 'default')}")
        normalized.setdefault("audit_id", f"mock-audit-{str(normalized.get('resource_key') or 'unknown').replace('.', '-')}-{str(normalized.get('scenario') or 'default')}")
        if not isinstance(normalized.get("payload"), dict):
            normalized["payload"] = {}
        return normalized

    def _from_dict(self, item: Any) -> MockResource | None:
        if not isinstance(item, dict):
            return None

        required = ["resource_key", "payload"]
        if any(key not in item for key in required):
            return None

        normalized = self._normalize_envelope(item)
        return MockResource(
            resource_key=str(normalized["resource_key"]),
            source=str(normalized["source"]),
            replaceable=bool(normalized["replaceable"]),
            version=str(normalized["version"]),
            scenario=str(normalized["scenario"]),
            payload=dict(normalized["payload"]),
            schema_ref=str(normalized["schema_ref"]),
            fallback_to_real=bool(normalized["fallback_to_real"]),
            description=str(normalized["description"]),
            status=str(normalized.get("status") or "mock"),
        )


mock_provider = MockProvider()
