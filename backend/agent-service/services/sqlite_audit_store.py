from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from pathlib import Path
from threading import Lock
from typing import Any


class SqliteAuditStore:
    """Append-only SQLite audit event table.

    This is the formal audit store used by agent-service. The table intentionally
    exposes only insert/list operations: audit events are immutable and state
    changes must be represented by a new audit/compensation event.
    """

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_events (
                        seq INTEGER PRIMARY KEY AUTOINCREMENT,
                        audit_id TEXT NOT NULL UNIQUE,
                        timestamp TEXT NOT NULL,
                        action TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        trace_id TEXT,
                        task_id TEXT,
                        workflow_id TEXT,
                        node_id TEXT,
                        plan_id TEXT,
                        skill_name TEXT,
                        tool_name TEXT,
                        mcp_tool_name TEXT,
                        risk_level TEXT,
                        status TEXT,
                        source TEXT,
                        summary TEXT,
                        parent_event_id TEXT,
                        correlation_id TEXT,
                        record_json TEXT NOT NULL
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_trace ON audit_events(trace_id, seq)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_task ON audit_events(task_id, seq)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_plan ON audit_events(plan_id, seq)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_action ON audit_events(action, seq)")
                conn.commit()

    def append(self, record: dict[str, Any]) -> None:
        row = {
            "audit_id": str(record.get("audit_id") or ""),
            "timestamp": str(record.get("timestamp") or ""),
            "action": str(record.get("action") or record.get("event_type") or "audit_event"),
            "event_type": str(record.get("event_type") or record.get("action") or "audit_event"),
            "trace_id": str(record.get("trace_id") or ""),
            "task_id": str(record.get("task_id") or ""),
            "workflow_id": str(record.get("workflow_id") or ""),
            "node_id": str(record.get("node_id") or ""),
            "plan_id": str(record.get("plan_id") or ""),
            "skill_name": str(record.get("skill_name") or record.get("skill_id") or ""),
            "tool_name": str(record.get("tool_name") or ""),
            "mcp_tool_name": str(record.get("mcp_tool_name") or ""),
            "risk_level": str(record.get("risk_level") or ""),
            "status": str(record.get("status") or ""),
            "source": str(record.get("source") or ""),
            "summary": str(record.get("summary") or ""),
            "parent_event_id": str(record.get("parent_event_id") or ""),
            "correlation_id": str(record.get("correlation_id") or ""),
            "record_json": json.dumps(record, ensure_ascii=False, sort_keys=True),
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO audit_events (
                        audit_id, timestamp, action, event_type, trace_id, task_id,
                        workflow_id, node_id, plan_id, skill_name, tool_name,
                        mcp_tool_name, risk_level, status, source, summary,
                        parent_event_id, correlation_id, record_json
                    ) VALUES (
                        :audit_id, :timestamp, :action, :event_type, :trace_id,
                        :task_id, :workflow_id, :node_id, :plan_id, :skill_name,
                        :tool_name, :mcp_tool_name, :risk_level, :status, :source,
                        :summary, :parent_event_id, :correlation_id, :record_json
                    )
                    """,
                    row,
                )
                conn.commit()

    def list(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        query = "SELECT record_json FROM audit_events ORDER BY seq DESC"
        params: tuple[Any, ...] = ()
        if limit is not None and limit >= 0:
            query += " LIMIT ?"
            params = (limit,)
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(query, params).fetchall()
        records: list[dict[str, Any]] = []
        for row in rows:
            try:
                parsed = json.loads(str(row["record_json"]))
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
        return [deepcopy(record) for record in records]
