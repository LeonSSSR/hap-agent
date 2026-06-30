"""Access control helpers for agent-service security boundaries."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from services.identity_service import AgentIdentity

AUDIT_ADMIN_ROLES = frozenset({"SYSTEM", "ADMIN", "SUPER_ADMIN", "SUPERADMIN", "TENANT_ADMIN"})


def is_audit_admin(identity: AgentIdentity) -> bool:
    role = str(identity.role or "").strip().upper()
    if role in AUDIT_ADMIN_ROLES:
        return True
    return identity.username == "__internal__"


def audit_record_username(record: dict[str, Any]) -> str:
    direct = str(record.get("username") or "").strip()
    if direct:
        return direct
    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        return str(metadata.get("username") or "").strip()
    return ""


def can_access_audit_record(record: dict[str, Any], identity: AgentIdentity) -> bool:
    if is_audit_admin(identity):
        return True
    owner = audit_record_username(record)
    return bool(owner) and owner == identity.username


def session_owner(session: dict[str, Any]) -> str:
    return str(session.get("owner") or "").strip()


def can_access_session(session: dict[str, Any] | None, identity: AgentIdentity) -> bool:
    if session is None:
        return False
    owner = session_owner(session)
    if not owner:
        return is_audit_admin(identity)
    if is_audit_admin(identity):
        return True
    return owner == identity.username


def assert_session_access(session: dict[str, Any] | None, identity: AgentIdentity) -> None:
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    if not can_access_session(session, identity):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="session access denied")


def assert_audit_trace_access(
    records: list[dict[str, Any]],
    identity: AgentIdentity,
    *,
    trace_exists: bool = False,
) -> None:
    if not records:
        if trace_exists and not is_audit_admin(identity):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="trace access denied")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trace not found")
    if is_audit_admin(identity):
        return
    owners = {audit_record_username(record) for record in records}
    owners.discard("")
    if len(owners) != 1 or identity.username not in owners:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="trace access denied")
