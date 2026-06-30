from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4
import hashlib
import json
import re

from config import settings
from services.durable_audit_store import DurableAuditStore
from services.protocols import AuditEventEnvelope
from services.sqlite_audit_store import SqliteAuditStore


SENSITIVE_KEY_PATTERN = re.compile(r"(password|passwd|secret|token|api[_-]?key|authorization|credential|private[_-]?key)", re.IGNORECASE)


def _redact_and_summarize(value: object, *, max_string: int = 160) -> object:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if SENSITIVE_KEY_PATTERN.search(str(key)) else _redact_and_summarize(item, max_string=max_string)
            for key, item in value.items()
        }
    if isinstance(value, list):
        if len(value) > 20:
            return {
                "type": "list",
                "count": len(value),
                "sample": [_redact_and_summarize(item, max_string=max_string) for item in value[:3]],
            }
        return [_redact_and_summarize(item, max_string=max_string) for item in value]
    if isinstance(value, str):
        if len(value) > max_string:
            digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
            return {"type": "string", "length": len(value), "sha256_12": digest, "preview": value[:max_string]}
        return value
    return value


def build_sanitized_summary(value: object) -> object:
    return _redact_and_summarize(value)


_USE_SETTINGS_PATH = object()


class AuditStore:
    """Append-only audit store backed by a formal SQLite table plus process cache."""

    def __init__(self, durable_path: str | None | object = _USE_SETTINGS_PATH) -> None:
        self._records: list[dict[str, object]] = []
        self._records_by_id: dict[str, dict[str, object]] = {}
        self._lock = Lock()
        path = settings.audit_store_path if durable_path is _USE_SETTINGS_PATH else durable_path
        self._durable_store = None
        if path:
            self._durable_store = DurableAuditStore(path) if str(path).endswith(".jsonl") else SqliteAuditStore(path)
            for record in self._durable_store.list(limit=None):
                audit_id = str(record.get("audit_id") or "")
                if audit_id:
                    self._records.append(record)
                    self._records_by_id[audit_id] = record

    def add(
        self,
        *,
        action: str,
        user_input: object = None,
        skill_name: object = None,
        plan_id: object = None,
        risk_level: object = None,
        need_confirm: object = None,
        read_only: object = None,
        dangerous_operation: object = None,
        real_execution: object = False,
        status: object = None,
        summary: object = None,
        metadata: dict[str, object] | None = None,
        trace_id: object = None,
        task_id: object = None,
        workflow_id: object = None,
        node_id: object = None,
        tool_name: object = None,
        mcp_tool_name: object = None,
        execution_entry: object = None,
        blocked_by: object = None,
        blocked_reason: object = None,
        approval_state: object = None,
        execution_mode: object = None,
        approval_id: object = None,
        approval_time: object = None,
        approval_reason: object = None,
        approval_by: object = None,
        approval_state_detail: object = None,
        compensation_state: object = None,
        replay_source: object = None,
        bypass: object = False,
        parent_event_id: object = None,
        event_type: object = None,
        source: object = None,
        resource_key: object = None,
        correlation_id: object = None,
        username: object = None,
    ) -> dict[str, object]:
        audit_id = f"audit-{uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        record = AuditEventEnvelope(
            action=str(action),
            event_type=str(event_type or action),
            trace_id=str(trace_id or ""),
            task_id=str(task_id or ""),
            workflow_id=str(workflow_id or ""),
            node_id=str(node_id or ""),
            skill_id=str(skill_name or ""),
            source=str(source or "mock"),
            risk_level=str(risk_level or "low"),
            status=str(status or "succeeded"),
            summary=str(summary or ""),
            tool_name=str(tool_name) if tool_name is not None else None,
            mcp_tool_name=str(mcp_tool_name) if mcp_tool_name is not None else None,
            execution_entry=str(execution_entry) if execution_entry is not None else None,
            blocked_by=str(blocked_by) if blocked_by is not None else None,
            blocked_reason=str(blocked_reason) if blocked_reason is not None else None,
            approval_state=str(approval_state) if approval_state is not None else None,
            execution_mode=str(execution_mode) if execution_mode is not None else None,
            bypass=bool(bypass),
            resource_key=str(resource_key) if resource_key is not None else None,
            parent_event_id=str(parent_event_id) if parent_event_id is not None else None,
            correlation_id=str(correlation_id) if correlation_id is not None else None,
            metadata=build_sanitized_summary({
                **(metadata or {}),
                **({"username": username} if username else {}),
                **({"approval_id": approval_id} if approval_id is not None else {}),
                **({"approval_time": approval_time} if approval_time is not None else {}),
                **({"approval_reason": approval_reason} if approval_reason is not None else {}),
                **({"approval_by": approval_by} if approval_by is not None else {}),
                **({"approval_state_detail": approval_state_detail} if approval_state_detail is not None else {}),
                **({"compensation_state": compensation_state} if compensation_state is not None else {}),
                **({"replay_source": replay_source} if replay_source is not None else {}),
            }),
        ).to_dict()
        record.update({
            "audit_id": audit_id,
            "timestamp": timestamp,
            "username": str(username or "").strip() or None,
            "user_input": build_sanitized_summary(user_input),
            "skill_name": skill_name,
            "plan_id": plan_id,
            "need_confirm": need_confirm,
            "read_only": read_only,
            "dangerous_operation": dangerous_operation,
            "real_execution": bool(real_execution),
            "lineage": {
                "parent_event_id": parent_event_id,
                "trace_id": trace_id,
                "workflow_id": workflow_id,
                "node_id": node_id,
                "correlation_id": correlation_id,
            },
        })
        with self._lock:
            self._records.append(record)
            self._records_by_id[audit_id] = record
        if self._durable_store is not None:
            self._durable_store.append(record)
        return deepcopy(record)

    def get(self, audit_id: str) -> dict[str, object] | None:
        with self._lock:
            record = self._records_by_id.get(audit_id)
            return deepcopy(record) if record else None

    def list(
        self,
        *,
        action: str | None = None,
        risk_level: str | None = None,
        username: str | None = None,
        include_all: bool = False,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        with self._lock:
            records = list(self._records)

        if action:
            records = [record for record in records if record.get("action") == action]
        if risk_level:
            records = [record for record in records if record.get("risk_level") == risk_level]
        if username and not include_all:
            owner = str(username).strip()
            records = [
                record
                for record in records
                if str(record.get("username") or "").strip() == owner
                or (
                    isinstance(record.get("metadata"), dict)
                    and str(record.get("metadata", {}).get("username") or "").strip() == owner
                )
            ]

        records = list(reversed(records))
        if limit is not None and limit >= 0:
            records = records[:limit]
        return [deepcopy(record) for record in records]

    def list_by_action(self, action: str, *, limit: int | None = None) -> list[dict[str, object]]:
        return self.list(action=action, limit=limit)

    def list_by_risk_level(self, risk_level: str, *, limit: int | None = None) -> list[dict[str, object]]:
        return self.list(risk_level=risk_level, limit=limit)

    def list_by_trace_id(
        self,
        trace_id: str,
        *,
        username: str | None = None,
        include_all: bool = False,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        records = self.list(limit=None, username=username, include_all=include_all)
        filtered = [record for record in records if str(record.get("trace_id")) == trace_id]
        if limit is not None and limit >= 0:
            filtered = filtered[:limit]
        return filtered

    def build_trace_view(
        self,
        *,
        trace_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, object]:
        trace_records = self.list_by_trace_id(trace_id, limit=limit) if trace_id else []
        workflow_id = str(trace_records[0].get("workflow_id") or "") if trace_records else None

        def _shape(record: dict[str, object], item_type: str) -> dict[str, object]:
            metadata = record.get("metadata", {}) if isinstance(record.get("metadata"), dict) else {}
            return {
                "envelope_type": record.get("envelope_type") or "audit_event",
                "type": item_type,
                "audit_id": record.get("audit_id"),
                "event_type": record.get("event_type") or record.get("action"),
                "action": record.get("action"),
                "timestamp": record.get("timestamp"),
                "status": record.get("status"),
                "summary": record.get("summary"),
                "trace_id": record.get("trace_id"),
                "plan_id": record.get("plan_id"),
                "workflow_id": record.get("workflow_id"),
                "node_id": record.get("node_id"),
                "tool_name": record.get("tool_name"),
                "mcp_tool_name": record.get("mcp_tool_name"),
                "execution_entry": record.get("execution_entry"),
                "blocked_by": record.get("blocked_by"),
                "blocked_reason": record.get("blocked_reason"),
                "approval_state": record.get("approval_state"),
                "execution_mode": record.get("execution_mode"),
                "bypass": record.get("bypass"),
                "skill_name": record.get("skill_name"),
                "source": record.get("source"),
                "risk_level": record.get("risk_level"),
                "need_confirm": record.get("need_confirm"),
                "approval_state": metadata.get("approval_state"),
                "real_execution": record.get("real_execution"),
                "metadata": metadata,
                "lineage": record.get("lineage", {}),
                "payload": {
                    "audit_id": record.get("audit_id"),
                    "timestamp": record.get("timestamp"),
                    "summary": record.get("summary"),
                    "metadata": metadata,
                    "lineage": record.get("lineage", {}),
                },
            }

        timeline = [_shape(record, "audit_event") for record in trace_records]

        return {
            "trace_id": trace_id,
            "workflow_id": workflow_id,
            "count": len(timeline),
            "items": timeline,
        }


audit_store = AuditStore()
