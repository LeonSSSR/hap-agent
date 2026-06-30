"""UI action intent selection and effective route resolution."""

from services.identity_service import AgentIdentity, permissions_for_role
from services.platform_operations_catalog import (
    apply_route_params,
    clear_catalog_cache,
    identity_allows_ui_action,
    operation_effective_route,
    select_ui_actions_for_llm,
)


def _admin() -> AgentIdentity:
    return AgentIdentity(
        username="admin",
        role="ADMIN",
        permissions=permissions_for_role("ADMIN"),
        auth_source="test",
    )


def setup_function() -> None:
    clear_catalog_cache()


def test_select_ui_actions_for_lineage_query_prioritizes_lineage_pages() -> None:
    identity = _admin()
    selected = select_ui_actions_for_llm("查询血缘关系", identity=identity, limit=32)
    assert "lineage.unified" in selected
    lineage_rank = selected.index("lineage.unified")
    assert lineage_rank < 12


def test_select_ui_actions_for_training_prioritizes_training_pages() -> None:
    identity = _admin()
    selected = select_ui_actions_for_llm("新建训练任务", identity=identity, limit=32)
    assert any(id.startswith("ml.training") for id in selected)


def test_operation_effective_route_falls_back_to_dataset_list() -> None:
    route = operation_effective_route("dg.datasets.edit.save")
    assert route == "/data-governance/datasets"


def test_operation_effective_route_expands_dynamic_id() -> None:
    route = operation_effective_route("dg.datasets.edit.save", params={"id": "ds-001"})
    assert route == "/data-governance/datasets/edit/ds-001"


def test_apply_route_params_skips_projects_without_id() -> None:
    assert apply_route_params("/data-governance/projects/:id") == ""


def test_admin_can_execute_datasource_create() -> None:
    identity = _admin()
    assert identity_allows_ui_action(identity, "dg.sources.create")
