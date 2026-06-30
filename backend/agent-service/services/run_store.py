"""Run session state for page-result / confirm / clarify handoff (memory + optional file sync)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from services.run_store_persistence import RunStatePersistence


@dataclass
class _PageWait:
    event: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] | None = None
    ui_action_id: str = ""


@dataclass
class _ConfirmWait:
    event: threading.Event = field(default_factory=threading.Event)
    tool_call_id: str = ""
    decision: str | None = None
    approved_by: str | None = None


@dataclass
class _ClarifyWait:
    event: threading.Event = field(default_factory=threading.Event)
    tool_call_id: str = ""
    answer: str | None = None
    skipped: bool = False


RUN_OWNER_GRACE_SECONDS = 120.0


class RunStore:
    def __init__(self, *, state_path: str | None = None) -> None:
        self._page_waits: dict[str, _PageWait] = {}
        self._confirm_waits: dict[str, _ConfirmWait] = {}
        self._clarify_waits: dict[str, _ClarifyWait] = {}
        self._run_owners: dict[str, str] = {}
        self._run_owner_cleared_at: dict[str, float] = {}
        self._lock = threading.Lock()
        self._persistence = RunStatePersistence(state_path) if state_path else None

    @property
    def persistence_enabled(self) -> bool:
        return self._persistence is not None

    def _key(self, run_id: str, tool_call_id: str) -> str:
        return f"{run_id}:{tool_call_id}"

    def _confirm_key(self, run_id: str, resume_token: str) -> str:
        return f"{run_id}:{resume_token}"

    def register_run(self, run_id: str, owner: str) -> None:
        with self._lock:
            rid = str(run_id or "").strip()
            owner_name = str(owner or "").strip()
            self._run_owners[rid] = owner_name
            self._run_owner_cleared_at.pop(rid, None)
        if self._persistence is not None:
            self._persistence.write_owner(rid, owner_name)

    def get_run_owner(self, run_id: str) -> str | None:
        with self._lock:
            rid = str(run_id or "").strip()
            owner = self._run_owners.get(rid)
            if not owner and self._persistence is not None:
                owner = self._persistence.read_owner(rid)
                if owner:
                    self._run_owners[rid] = owner
            if not owner:
                return None
            cleared_at = self._run_owner_cleared_at.get(rid)
            if cleared_at is not None and time.monotonic() - cleared_at > RUN_OWNER_GRACE_SECONDS:
                self._run_owners.pop(rid, None)
                self._run_owner_cleared_at.pop(rid, None)
                return None
            return owner

    def register_page_wait(self, run_id: str, tool_call_id: str, *, ui_action_id: str = "") -> None:
        with self._lock:
            self._page_waits[self._key(run_id, tool_call_id)] = _PageWait(
                ui_action_id=str(ui_action_id or "").strip(),
            )
        if self._persistence is not None:
            self._persistence.write_page_pending(run_id, tool_call_id, ui_action_id=ui_action_id)

    def set_page_result(self, run_id: str, tool_call_id: str, result: dict[str, Any]) -> bool:
        with self._lock:
            entry = self._page_waits.get(self._key(run_id, tool_call_id))
            reported_ui = str(result.get("ui_action_id") or "").strip()
            if entry is not None:
                if entry.ui_action_id and reported_ui and reported_ui != entry.ui_action_id:
                    return False
                entry.result = result
                entry.event.set()
            elif self._persistence is None:
                return False
        if self._persistence is not None:
            self._persistence.write_page_result(run_id, tool_call_id, result)
            return True
        return entry is not None

    def wait_page_result(
        self,
        run_id: str,
        tool_call_id: str,
        *,
        timeout_seconds: float,
        cancel_check: Callable[[], bool] | None = None,
        poll_seconds: float = 0.25,
    ) -> dict[str, Any] | None:
        with self._lock:
            entry = self._page_waits.get(self._key(run_id, tool_call_id))
        if entry is None and self._persistence is None:
            return None
        deadline = time.monotonic() + timeout_seconds if timeout_seconds > 0 else None
        while True:
            if entry is not None and entry.event.wait(timeout=poll_seconds):
                result = entry.result
                if isinstance(result, dict) and result.get("_cancelled"):
                    return None
                return result
            if entry is None:
                time.sleep(poll_seconds)
            if self._persistence is not None:
                persisted = self._persistence.read_page_result(run_id, tool_call_id)
                if persisted is not None:
                    if persisted.get("_cancelled"):
                        return None
                    if entry is not None:
                        with self._lock:
                            entry.result = persisted
                            entry.event.set()
                    return persisted
            if cancel_check and cancel_check():
                self.cancel_page_wait(run_id, tool_call_id)
                return None
            if deadline is not None and time.monotonic() >= deadline:
                return None

    def cancel_page_wait(self, run_id: str, tool_call_id: str) -> None:
        cancelled = {"_cancelled": True, "success": False, "message": "run cancelled"}
        with self._lock:
            entry = self._page_waits.get(self._key(run_id, tool_call_id))
            if entry is not None:
                entry.result = cancelled
                entry.event.set()
        if self._persistence is not None:
            self._persistence.write_page_result(run_id, tool_call_id, cancelled)

    def register_confirm_wait(self, run_id: str, tool_call_id: str, resume_token: str) -> None:
        with self._lock:
            self._confirm_waits[self._confirm_key(run_id, resume_token)] = _ConfirmWait(tool_call_id=tool_call_id)
        if self._persistence is not None:
            self._persistence.write_confirm_pending(run_id, resume_token, tool_call_id=tool_call_id)

    def set_confirm_decision(
        self,
        run_id: str,
        resume_token: str,
        *,
        decision: str,
        approved_by: str | None = None,
    ) -> bool:
        with self._lock:
            entry = self._confirm_waits.get(self._confirm_key(run_id, resume_token))
            if entry is not None:
                entry.decision = decision
                entry.approved_by = approved_by
                entry.event.set()
            elif self._persistence is None:
                return False
        if self._persistence is not None:
            self._persistence.write_confirm_decision(
                run_id,
                resume_token,
                decision=decision,
                approved_by=approved_by,
            )
            return True
        return entry is not None

    def wait_confirm(
        self,
        run_id: str,
        resume_token: str,
        *,
        timeout_seconds: float | None = None,
        cancel_check: Callable[[], bool] | None = None,
        poll_seconds: float = 0.25,
    ) -> tuple[str, str | None] | None:
        with self._lock:
            entry = self._confirm_waits.get(self._confirm_key(run_id, resume_token))
        if entry is None and self._persistence is None:
            return None
        deadline = time.monotonic() + timeout_seconds if timeout_seconds and timeout_seconds > 0 else None
        while True:
            if entry is not None and entry.event.wait(timeout=poll_seconds):
                return (str(entry.decision or "reject"), entry.approved_by)
            if entry is None:
                time.sleep(poll_seconds)
            if self._persistence is not None:
                persisted = self._persistence.read_confirm_decision(run_id, resume_token)
                if persisted is not None:
                    if entry is not None:
                        with self._lock:
                            entry.decision = persisted[0]
                            entry.approved_by = persisted[1]
                            entry.event.set()
                    return persisted
            if cancel_check and cancel_check():
                self.cancel_confirm_wait(run_id, resume_token)
                return None
            if deadline is not None and time.monotonic() >= deadline:
                return None

    def register_clarify_wait(self, run_id: str, tool_call_id: str, resume_token: str) -> None:
        with self._lock:
            self._clarify_waits[self._confirm_key(run_id, resume_token)] = _ClarifyWait(tool_call_id=tool_call_id)
        if self._persistence is not None:
            self._persistence.write_clarify_pending(run_id, resume_token, tool_call_id=tool_call_id)

    def set_clarify_answer(
        self,
        run_id: str,
        resume_token: str,
        *,
        answer: str,
        skipped: bool = False,
    ) -> bool:
        with self._lock:
            entry = self._clarify_waits.get(self._confirm_key(run_id, resume_token))
            if entry is not None:
                entry.answer = answer
                entry.skipped = skipped
                entry.event.set()
            elif self._persistence is None:
                return False
        if self._persistence is not None:
            self._persistence.write_clarify_answer(
                run_id,
                resume_token,
                answer=answer,
                skipped=skipped,
            )
            return True
        return entry is not None

    def wait_clarify(
        self,
        run_id: str,
        resume_token: str,
        *,
        timeout_seconds: float | None = None,
        cancel_check: Callable[[], bool] | None = None,
        poll_seconds: float = 0.25,
    ) -> tuple[str, bool] | None:
        with self._lock:
            entry = self._clarify_waits.get(self._confirm_key(run_id, resume_token))
        if entry is None and self._persistence is None:
            return None
        deadline = time.monotonic() + timeout_seconds if timeout_seconds and timeout_seconds > 0 else None
        while True:
            if entry is not None and entry.event.wait(timeout=poll_seconds):
                return (str(entry.answer or ""), bool(entry.skipped))
            if entry is None:
                time.sleep(poll_seconds)
            if self._persistence is not None:
                persisted = self._persistence.read_clarify_answer(run_id, resume_token)
                if persisted is not None:
                    if entry is not None:
                        with self._lock:
                            entry.answer = persisted[0]
                            entry.skipped = persisted[1]
                            entry.event.set()
                    return persisted
            if cancel_check and cancel_check():
                self.cancel_clarify_wait(run_id, resume_token)
                return None
            if deadline is not None and time.monotonic() >= deadline:
                return None

    def cancel_confirm_wait(self, run_id: str, resume_token: str) -> None:
        with self._lock:
            entry = self._confirm_waits.get(self._confirm_key(run_id, resume_token))
            if entry is not None:
                entry.decision = "reject"
                entry.event.set()
        if self._persistence is not None:
            self._persistence.write_confirm_decision(
                run_id,
                resume_token,
                decision="reject",
                approved_by=None,
            )

    def cancel_clarify_wait(self, run_id: str, resume_token: str) -> None:
        with self._lock:
            entry = self._clarify_waits.get(self._confirm_key(run_id, resume_token))
            if entry is not None:
                entry.skipped = True
                entry.answer = ""
                entry.event.set()
        if self._persistence is not None:
            self._persistence.write_clarify_answer(
                run_id,
                resume_token,
                answer="",
                skipped=True,
            )

    def clear_run(self, run_id: str) -> None:
        with self._lock:
            rid = str(run_id or "").strip()
            if rid and rid in self._run_owners:
                self._run_owner_cleared_at[rid] = time.monotonic()
            prefix = f"{run_id}:"
            for key, entry in list(self._confirm_waits.items()):
                if key.startswith(prefix):
                    entry.decision = "reject"
                    entry.event.set()
            for key, entry in list(self._clarify_waits.items()):
                if key.startswith(prefix):
                    entry.skipped = True
                    entry.answer = ""
                    entry.event.set()
            for key in list(self._page_waits.keys()):
                if key.startswith(prefix):
                    wait = self._page_waits[key]
                    wait.result = {"_cancelled": True, "success": False, "message": "run cancelled"}
                    wait.event.set()
            for key in list(self._page_waits.keys()):
                if key.startswith(prefix):
                    del self._page_waits[key]
            for key in list(self._confirm_waits.keys()):
                if key.startswith(prefix):
                    del self._confirm_waits[key]
            for key in list(self._clarify_waits.keys()):
                if key.startswith(prefix):
                    del self._clarify_waits[key]
        if self._persistence is not None:
            self._persistence.clear_run(run_id)


from config import settings

_run_store_path = settings.run_store_path.strip() if settings.run_store_path else None
run_store = RunStore(state_path=_run_store_path)
