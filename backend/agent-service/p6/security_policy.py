"""Role → permission codes for agent-service dev/SSO."""

from __future__ import annotations

# MCP tool YAML permission_scope vocabulary (read subset).
_MCP_READ_PERMISSIONS: set[str] = {
    "algorithm.read",
    "catalog.read",
    "code.read",
    "collaboration.read",
    "dataset.read",
    "datasource.read",
    "experiment.read",
    "feature.read",
    "governance.read",
    "inference.deploy.read",
    "inference.read",
    "labeling.read",
    "lineage.read",
    "model.evaluation.read",
    "model.monitor.read",
    "model.read",
    "model.registry.read",
    "notebook.read",
    "pipeline.read",
    "platform.read",
    "processing.read",
    "task.read",
    "training.read",
    "workflow.read",
}

_MCP_WRITE_PERMISSIONS: set[str] = {
    "algorithm.write",
    "dataset.write",
    "experiment.write",
    "feature.write",
    "inference.deploy.write",
    "inference.invoke",
    "labeling.write",
    "model.publish.request",
    "model.registry.write",
    "notebook.write",
    "pipeline.write",
    "platform.write",
    "processing.write",
    "training.write",
    "workflow.write",
}

# HAP SPA catalog permission_scope vocabulary (UI page actions).
_UI_CATALOG_PERMISSIONS: set[str] = {
    "algorithm.read",
    "algorithm.write",
    "augmentation.read",
    "augmentation.write",
    "cicd.write",
    "data_cleaning.read",
    "data_cleaning.write",
    "data_service.read",
    "data_service.write",
    "data_split.write",
    "data_sync.read",
    "data_sync.write",
    "dataset.read",
    "dataset.version.write",
    "datasource.read",
    "datasource.write",
    "feature_engineering.read",
    "feature_engineering.write",
    "feature_registry.read",
    "feature_registry.write",
    "hyperparam.read",
    "hyperparam.write",
    "labeling.read",
    "labeling.write",
    "lineage.read",
    "lineage.write",
    "ml_pipeline.read",
    "ml_pipeline.write",
    "ml_training.write",
    "notebook.read",
    "notebook.write",
    "processing.read",
    "project.read",
    "project.write",
    "schedule.read",
    "schedule.write",
    "sofelink.read",
    "sofelink.write",
    "super_admin",
    "system.audit.read",
    "system.config.write",
    "system.notification.write",
    "system.security.write",
    "system.user.write",
    "transform.read",
    "transform.write",
}

_UI_READ_PERMISSIONS: set[str] = {perm for perm in _UI_CATALOG_PERMISSIONS if perm.endswith(".read") or perm in {"workflow.read", "super_admin"}}

_ROLE_ALIASES: dict[str, str] = {
    "SUPER_ADMIN": "ADMIN",
    "SUPERADMIN": "ADMIN",
    "TENANT_ADMIN": "ADMIN",
}

_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "SYSTEM": _MCP_READ_PERMISSIONS
    | _MCP_WRITE_PERMISSIONS
    | _UI_CATALOG_PERMISSIONS
    | {
        "ml.lifecycle.execute",
        "model.publish.approve",
    },
    "SUPER_ADMIN": _MCP_READ_PERMISSIONS
    | _MCP_WRITE_PERMISSIONS
    | _UI_CATALOG_PERMISSIONS
    | {
        "ml.lifecycle.execute",
        "model.publish.approve",
    },
    "ADMIN": _MCP_READ_PERMISSIONS
    | _MCP_WRITE_PERMISSIONS
    | _UI_CATALOG_PERMISSIONS
    | {
        "ml.lifecycle.execute",
        "model.publish.approve",
    },
    "APPROVER": _MCP_READ_PERMISSIONS
    | _MCP_WRITE_PERMISSIONS
    | _UI_CATALOG_PERMISSIONS
    | {
        "ml.lifecycle.execute",
        "model.publish.approve",
    },
    "USER": _MCP_READ_PERMISSIONS | _UI_READ_PERMISSIONS,
}


def permissions_for_role(role: str) -> set[str]:
    key = str(role or "USER").strip().upper()
    key = _ROLE_ALIASES.get(key, key)
    return set(_ROLE_PERMISSIONS.get(key, _ROLE_PERMISSIONS["USER"]))


def normalize_role(role: str | None) -> str:
    key = str(role or "USER").strip().upper()
    return _ROLE_ALIASES.get(key, key)
