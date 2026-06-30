"""P1/P2 fixes: dataset_catalog_query registry and expanded frontend scan."""

from __future__ import annotations

from services.mcp_server import mcp_server
from services.tool_registry import tool_registry
from scripts.generate_mcp_api_tools import scan_frontend_services, FRONTEND_SCAN_DIRS
from scripts.audit_mcp_reality import scan_backend_routes, scan_frontend_signatures


def test_dataset_catalog_query_in_registry() -> None:
    assert tool_registry.get("dataset_catalog_query") is not None
    assert "dataset_catalog_query" in mcp_server._handlers


def test_frontend_scan_includes_pages() -> None:
    ops = scan_frontend_services()
    sources = {op.source_file for op in ops}
    assert any(path.startswith("frontend/src/pages/") for path in sources)
    assert len(FRONTEND_SCAN_DIRS) >= 3


def test_frontend_scan_finds_inline_unified_lineage() -> None:
    sigs = scan_frontend_signatures()
    assert ("GET", "/api/unified-lineage") in sigs or any(
        "unified-lineage" in path for _, path in sigs
    )


def test_backend_scan_includes_pipeline_proxy_routes() -> None:
    routes = scan_backend_routes()
    assert ("GET", "/api/pipelines") in routes
    assert ("GET", "/api/pipeline-runs") in routes
    assert ("GET", "/api/pipeline-templates") in routes


def test_data_split_execute_alias_points_to_governance_api() -> None:
    from services.mcp_alias_registry import resolve_canonical_tool_name
    from services.platform_api_bindings import resolve_binding

    canonical = resolve_canonical_tool_name("data_split_execute")
    assert canonical == "hap_api_post_governance_split_execute"
    binding = resolve_binding(canonical)
    assert binding is not None
    assert binding.get("path") == "/governance/split/execute"


def test_cicd_deploy_binding_matches_frontend() -> None:
    from services.platform_api_bindings import resolve_binding

    binding = resolve_binding("cicd_deploy_request")
    assert binding is not None
    assert binding.get("path") == "/cicd/pipelines/{pipeline_id}/trigger"


def test_data_ingestion_paths_normalized_to_api_prefix() -> None:
    from scripts.generate_mcp_api_tools import _normalize_frontend_api_path
    from services.platform_api_bindings import iter_tool_bindings

    assert _normalize_frontend_api_path("/data-ingestion/sources") == "/api/data-ingestion/sources"
    bindings = [b for b in iter_tool_bindings() if "/data-ingestion" in str(b.get("path"))]
    assert bindings, "expected generated data-ingestion bindings"


def test_backend_scan_includes_all_services() -> None:
    routes = scan_backend_routes()
    assert ("GET", "/api/all-services") in routes
