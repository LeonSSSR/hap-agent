"""菜单可见路由须被 platform_operations_catalog 页面级条目覆盖。"""

from __future__ import annotations

import json
from pathlib import Path

from services.platform_operations_catalog import load_platform_operations

# 与 frontend/.umirc.ts 菜单栏可见页面同步（hideInMenu 的详情/重定向页不在此列）
MENU_VISIBLE_ROUTES: frozenset[str] = frozenset(
    {
        "/home",
        "/dashboard",
        "/lineage",
        "/data-map",
        "/data-governance/sources",
        "/data-governance/sync",
        "/data-governance/datasets",
        "/data-governance/schedule",
        "/data-governance/service",
        "/data-governance/sofelink",
        "/data-processing/navigation",
        "/data-processing/labeling",
        "/data-processing/transform",
        "/data-processing/augmentation",
        "/data-processing/quality",
        "/data-processing/cleaning",
        "/data-processing/exploration",
        "/data-processing/feature/processing",
        "/data-processing/feature/registry",
        "/data-processing/feature/monitor",
        "/data-processing/feature/drift-alert",
        "/data-processing/feature/statistics",
        "/data-processing/split",
        "/model-dev/notebooks",
        "/model-dev/pipelines/workspace",
        "/model-dev/pipelines/runs",
        "/model-dev/pipelines/components",
        "/model-dev/pipelines/templates",
        "/model-dev/pipelines/recurring",
        "/model-dev/training",
        "/model-dev/katib",
        "/model-dev/algorithms",
        "/model-dev/collaboration",
        "/model-app/model-versions",
        "/model-app/evaluation",
        "/model-app/service-publish",
        "/model-app/service-deploy",
        "/model-app/service-invoke",
        "/model-app/service-monitor",
        "/model-app/cicd",
        "/model-app/infer-logs",
        "/model-app/feature-drift",
        "/system/users",
        "/system/security",
        "/system/audit",
        "/system/config",
        "/system/notification",
        "/super-admin/tenants",
        "/env/image",
        "/env/storage",
        "/env/monitor",
    }
)


def _page_level_routes() -> set[str]:
    routes: set[str] = set()
    for op in load_platform_operations():
        if op.get("parent_ui_action_id"):
            continue
        route = str(op.get("route") or "").split("?")[0].strip()
        if route:
            routes.add(route)
    return routes


def test_menu_routes_covered_by_catalog() -> None:
    covered = _page_level_routes()
    missing = sorted(MENU_VISIBLE_ROUTES - covered)
    assert not missing, f"menu routes missing from catalog page entries: {missing}"


def test_frontend_catalog_matches_backend() -> None:
    backend_path = Path(__file__).resolve().parents[1] / "data" / "platform_operations_catalog.json"
    frontend_path = (
        Path(__file__).resolve().parents[3]
        / "frontend"
        / "src"
        / "components"
        / "AgentShell"
        / "platformOperationsCatalog.json"
    )
    backend = json.loads(backend_path.read_text(encoding="utf-8"))
    frontend = json.loads(frontend_path.read_text(encoding="utf-8"))
    backend_ids = sorted(str(op.get("ui_action_id") or "") for op in backend.get("operations", []))
    frontend_ids = sorted(str(op.get("ui_action_id") or "") for op in frontend.get("operations", []))
    assert backend_ids == frontend_ids, "frontend/backend catalog ui_action_id lists diverged"
