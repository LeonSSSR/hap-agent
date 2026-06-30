"""每个页面级 catalog 条目须至少有一个子操作（按钮/表单级）。"""

from __future__ import annotations

from services.platform_operations_catalog import load_platform_operations


def test_every_page_level_operation_has_child() -> None:
    ops = load_platform_operations()
    pages = [op for op in ops if not op.get("parent_ui_action_id")]
    children_by_parent: dict[str, list[str]] = {}
    for op in ops:
        parent = str(op.get("parent_ui_action_id") or "").strip()
        if not parent:
            continue
        children_by_parent.setdefault(parent, []).append(str(op.get("ui_action_id") or ""))

    missing_children = sorted(
        str(page.get("ui_action_id") or "")
        for page in pages
        if not children_by_parent.get(str(page.get("ui_action_id") or ""))
    )
    assert not missing_children, f"page-level ops without child actions: {missing_children}"
