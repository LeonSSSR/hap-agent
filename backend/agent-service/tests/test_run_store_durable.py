"""Durable RunStore handoff across logical instances."""

from __future__ import annotations

import threading

from services.run_store import RunStore


def test_cross_instance_page_result_handoff(tmp_path) -> None:
    waiter_store = RunStore(state_path=str(tmp_path / "run_state"))
    reporter_store = RunStore(state_path=str(tmp_path / "run_state"))

    waiter_store.register_run("run-a", "alice")
    waiter_store.register_page_wait("run-a", "tc-1", ui_action_id="dg.sources")

    result_holder: list[dict | None] = []

    def waiter() -> None:
        result_holder.append(
            waiter_store.wait_page_result("run-a", "tc-1", timeout_seconds=3.0, poll_seconds=0.05)
        )

    thread = threading.Thread(target=waiter)
    thread.start()
    assert reporter_store.set_page_result(
        "run-a",
        "tc-1",
        {"success": True, "message": "ok", "ui_action_id": "dg.sources"},
    )
    thread.join(timeout=2.0)
    assert not thread.is_alive()
    assert result_holder == [{"success": True, "message": "ok", "ui_action_id": "dg.sources"}]


def test_cross_instance_run_owner_lookup(tmp_path) -> None:
    writer = RunStore(state_path=str(tmp_path / "run_state"))
    reader = RunStore(state_path=str(tmp_path / "run_state"))
    writer.register_run("run-owner", "bob")
    assert reader.get_run_owner("run-owner") == "bob"


def test_cross_instance_confirm_decision(tmp_path) -> None:
    waiter_store = RunStore(state_path=str(tmp_path / "run_state"))
    reporter_store = RunStore(state_path=str(tmp_path / "run_state"))

    waiter_store.register_confirm_wait("run-c", "tc-1", "confirm-token")
    outcomes: list[tuple[str, str | None] | None] = []

    def waiter() -> None:
        outcomes.append(
            waiter_store.wait_confirm("run-c", "confirm-token", timeout_seconds=3.0, poll_seconds=0.05)
        )

    thread = threading.Thread(target=waiter)
    thread.start()
    assert reporter_store.set_confirm_decision(
        "run-c",
        "confirm-token",
        decision="approve",
        approved_by="alice",
    )
    thread.join(timeout=2.0)
    assert outcomes == [("approve", "alice")]
