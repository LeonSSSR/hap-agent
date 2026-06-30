"""Each catalog ui_action_id maps to a unique per-operation tool name."""

from services.operation_tools import operation_tool_name, ui_action_id_from_operation_tool
from services.platform_operations_catalog import load_platform_operations, valid_ui_action_ids


def test_every_ui_action_has_operation_tool_mapping() -> None:
    catalog_ids = valid_ui_action_ids()
    assert len(catalog_ids) >= 30
    for ui_id in catalog_ids:
        tool_name = operation_tool_name(ui_id)
        assert ui_action_id_from_operation_tool(tool_name) == ui_id


def test_catalog_ids_match_operation_tool_index() -> None:
    catalog_ids = {str(op.get("ui_action_id") or "").strip() for op in load_platform_operations()}
    catalog_ids.discard("")
    mapped = {ui_action_id_from_operation_tool(operation_tool_name(ui_id)) for ui_id in catalog_ids}
    assert mapped == catalog_ids
