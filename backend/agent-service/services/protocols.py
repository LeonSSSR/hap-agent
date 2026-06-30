"""Shared protocol types for agent-service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

SOURCE_VALUES = frozenset({"mock", "real"})
RISK_LEVEL_VALUES = frozenset({"low", "medium", "high"})
WORKFLOW_STATE_VALUES = frozenset(
    {
        "draft",
        "failed",
        "cancelled",
        "executing",
        "succeeded",
        "rolled_back",
        "skill_selected",
        "confirm_pending",
        "intent_confirmed",
        "permission_checked",
    }
)


class SkillProtocol(Protocol):
    skill_id: str


class McpToolProtocol(Protocol):
    tool_name: str


@dataclass
class StructuredDataEnvelope:
    resource_key: str
    source: str = "mock"
    replaceable: bool = True
    version: str = "1.0.0"
    scenario: str = "default"
    payload: dict[str, Any] = field(default_factory=dict)
    schema_ref: str = ""
    fallback_to_real: bool = False
    description: str = ""
    status: str = "mock"
    trace_id: str = ""
    audit_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_key": self.resource_key,
            "source": self.source,
            "replaceable": self.replaceable,
            "version": self.version,
            "scenario": self.scenario,
            "payload": self.payload,
            "schema_ref": self.schema_ref,
            "fallback_to_real": self.fallback_to_real,
            "description": self.description,
            "status": self.status,
            "trace_id": self.trace_id,
            "audit_id": self.audit_id,
        }


@dataclass
class AuditEventEnvelope:
    action: str
    event_type: str = ""
    trace_id: str = ""
    task_id: str = ""
    workflow_id: str = ""
    node_id: str = ""
    skill_id: str = ""
    source: str = "mock"
    risk_level: str = "low"
    status: str = "succeeded"
    summary: str = ""
    tool_name: str | None = None
    mcp_tool_name: str | None = None
    execution_entry: str | None = None
    blocked_by: str | None = None
    blocked_reason: str | None = None
    approval_state: str | None = None
    execution_mode: str | None = None
    bypass: bool = False
    resource_key: str | None = None
    parent_event_id: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "event_type": self.event_type or self.action,
            "trace_id": self.trace_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "node_id": self.node_id,
            "skill_id": self.skill_id,
            "source": self.source,
            "risk_level": self.risk_level,
            "status": self.status,
            "summary": self.summary,
            "tool_name": self.tool_name,
            "mcp_tool_name": self.mcp_tool_name,
            "execution_entry": self.execution_entry,
            "blocked_by": self.blocked_by,
            "blocked_reason": self.blocked_reason,
            "approval_state": self.approval_state,
            "execution_mode": self.execution_mode,
            "bypass": self.bypass,
            "resource_key": self.resource_key,
            "parent_event_id": self.parent_event_id,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }
