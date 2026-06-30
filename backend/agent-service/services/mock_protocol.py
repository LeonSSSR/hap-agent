from __future__ import annotations

from typing import Any

from services.protocols import StructuredDataEnvelope


class StructuredDataProtocol:
    """Shared envelope for replaceable mock and real platform data."""

    SOURCE_VALUES = {"mock", "real"}

    @classmethod
    def normalize_envelope(cls, envelope: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(envelope)
        normalized.setdefault("source", "mock")
        normalized.setdefault("replaceable", True)
        normalized.setdefault("version", "1.0.0")
        normalized.setdefault("scenario", "default")
        normalized.setdefault("payload", {})
        normalized.setdefault("schema_ref", f"mock.schema.{str(normalized.get('resource_key') or 'unknown')}")
        normalized.setdefault("fallback_to_real", False)
        normalized.setdefault("description", "")
        normalized.setdefault("status", "mock")
        normalized.setdefault("trace_id", "")
        normalized.setdefault("audit_id", "")
        if not isinstance(normalized.get("payload"), dict):
            normalized["payload"] = {}
        return normalized

    @classmethod
    def validate_envelope(cls, envelope: dict[str, Any]) -> dict[str, Any]:
        normalized = cls.normalize_envelope(envelope)
        required = ["resource_key", "source", "replaceable", "version", "scenario", "payload", "schema_ref", "fallback_to_real", "description", "trace_id", "audit_id"]
        missing = [field for field in required if field not in normalized]
        source = str(normalized.get("source") or "")
        if source not in cls.SOURCE_VALUES:
            missing.append("source must be mock or real")
        if not isinstance(normalized.get("payload"), dict):
            missing.append("payload must be object")
        return {"valid": not missing, "missing": missing, "resource_key": normalized.get("resource_key"), "source": source}

    @classmethod
    def mark_real_if_available(cls, envelope: dict[str, Any], *, available: bool) -> dict[str, Any]:
        updated = dict(envelope)
        updated["source"] = "real" if available else str(envelope.get("source") or "mock")
        updated["status"] = "real" if available else str(envelope.get("status") or "mock")
        return updated
