"""RunStore waits must be cancellable without freezing the server."""

from __future__ import annotations

import threading

from services.run_store import RunStore


def test_wait_clarify_cancel_check_unblocks() -> None:
    store = RunStore()
    cancelled = threading.Event()

    def cancel_check() -> bool:
        return cancelled.is_set()

    def waiter() -> None:
        result = store.wait_clarify("run-1", "clarify-abc", cancel_check=cancel_check)
        assert result is None

    thread = threading.Thread(target=waiter)
    store.register_clarify_wait("run-1", "tc-1", "clarify-abc")
    thread.start()
    cancelled.set()
    thread.join(timeout=2.0)
    assert not thread.is_alive()


def test_wait_page_result_cancel_returns_none() -> None:
    store = RunStore()
    cancelled = threading.Event()

    def waiter() -> None:
        result = store.wait_page_result(
            "run-2",
            "tc-page",
            timeout_seconds=5.0,
            cancel_check=cancelled.is_set,
        )
        assert result is None

    store.register_page_wait("run-2", "tc-page")
    thread = threading.Thread(target=waiter)
    thread.start()
    cancelled.set()
    thread.join(timeout=2.0)
    assert not thread.is_alive()


def test_clear_run_keeps_owner_for_grace_period() -> None:
    store = RunStore()
    store.register_run("run-4", "alice")
    store.clear_run("run-4")
    assert store.get_run_owner("run-4") == "alice"


def test_clear_run_page_wait_not_actionable_result() -> None:
    store = RunStore()
    store.register_page_wait("run-3", "tc-page")
    results: list[dict | None] = []

    def waiter() -> None:
        results.append(store.wait_page_result("run-3", "tc-page", timeout_seconds=2.0))

    thread = threading.Thread(target=waiter)
    thread.start()
    store.clear_run("run-3")
    thread.join(timeout=2.0)
    assert results == [None]
