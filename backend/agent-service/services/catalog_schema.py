from __future__ import annotations

from typing import Any


CATALOG_SOURCE_VALUES = {"mock", "real"}


class CatalogSchemaError(ValueError):
    pass


def _validate_common_catalog(payload: dict[str, Any], *, skill_id: str) -> None:
    if not isinstance(payload, dict):
        raise CatalogSchemaError(f"catalog payload for {skill_id} must be a mapping")
    if str(payload.get("source") or "") not in CATALOG_SOURCE_VALUES:
        raise CatalogSchemaError(f"catalog payload for {skill_id} has invalid source")
    if not str(payload.get("summary") or "").strip():
        raise CatalogSchemaError(f"catalog payload for {skill_id} requires summary")


def validate_platform_services_catalog(payload: dict[str, Any]) -> None:
    _validate_common_catalog(payload, skill_id="query_platform_services")
    if not isinstance(payload.get("services"), list):
        raise CatalogSchemaError("platform services catalog requires services list")
    for service in payload.get("services", []):
        if not isinstance(service, dict):
            raise CatalogSchemaError("platform services catalog service item must be a mapping")
        if not str(service.get("name") or "").strip():
            raise CatalogSchemaError("platform services catalog service item requires name")
        if not str(service.get("status") or "").strip():
            raise CatalogSchemaError("platform services catalog service item requires status")


def validate_task_status_catalog(payload: dict[str, Any]) -> None:
    _validate_common_catalog(payload, skill_id="query_task_status")
    if not isinstance(payload.get("stats"), dict):
        raise CatalogSchemaError("task status catalog requires stats mapping")
    if not isinstance(payload.get("items"), list):
        raise CatalogSchemaError("task status catalog requires items list")


def validate_lineage_catalog(payload: dict[str, Any]) -> None:
    _validate_common_catalog(payload, skill_id="query_lineage")
    lineage = payload.get("lineage")
    if not isinstance(lineage, dict):
        raise CatalogSchemaError("lineage catalog requires lineage mapping")
    if not isinstance(lineage.get("upstream"), list):
        raise CatalogSchemaError("lineage catalog requires upstream list")
    if not isinstance(lineage.get("downstream"), list):
        raise CatalogSchemaError("lineage catalog requires downstream list")
