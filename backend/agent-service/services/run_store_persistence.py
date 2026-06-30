"""File-backed run handoff state for multi-instance agent-service deployments."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


class RunStatePersistence:
    """Minimal cross-process coordination via JSON files (no extra dependencies)."""

    def __init__(self, base_path: str | Path) -> None:
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return True

    def _run_dir(self, run_id: str) -> Path:
        return self._base_path / str(run_id or "").strip()

    def write_owner(self, run_id: str, owner: str) -> None:
        rid = str(run_id or "").strip()
        if not rid:
            return
        _atomic_write_json(
            self._run_dir(rid) / "owner.json",
            {"run_id": rid, "owner": str(owner or "").strip(), "updated_at": time.time()},
        )

    def read_owner(self, run_id: str) -> str | None:
        path = self._run_dir(run_id) / "owner.json"
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        owner = str(payload.get("owner") or "").strip()
        return owner or None

    def write_page_pending(self, run_id: str, tool_call_id: str, *, ui_action_id: str = "") -> None:
        self._write_wait(
            run_id,
            "page",
            tool_call_id,
            {"status": "pending", "ui_action_id": str(ui_action_id or "").strip()},
        )

    def write_page_result(self, run_id: str, tool_call_id: str, result: dict[str, Any]) -> None:
        self._write_wait(
            run_id,
            "page",
            tool_call_id,
            {"status": "done", "result": dict(result)},
        )

    def read_page_result(self, run_id: str, tool_call_id: str) -> dict[str, Any] | None:
        payload = self._read_wait(run_id, "page", tool_call_id)
        if not payload:
            return None
        if str(payload.get("status") or "") != "done":
            return None
        result = payload.get("result")
        return result if isinstance(result, dict) else None

    def write_confirm_pending(self, run_id: str, resume_token: str, *, tool_call_id: str = "") -> None:
        self._write_wait(
            run_id,
            "confirm",
            resume_token,
            {"status": "pending", "tool_call_id": str(tool_call_id or "").strip()},
        )

    def write_confirm_decision(
        self,
        run_id: str,
        resume_token: str,
        *,
        decision: str,
        approved_by: str | None,
    ) -> None:
        self._write_wait(
            run_id,
            "confirm",
            resume_token,
            {
                "status": "done",
                "decision": str(decision or "reject"),
                "approved_by": str(approved_by or "").strip() or None,
            },
        )

    def read_confirm_decision(self, run_id: str, resume_token: str) -> tuple[str, str | None] | None:
        payload = self._read_wait(run_id, "confirm", resume_token)
        if not payload or str(payload.get("status") or "") != "done":
            return None
        return (str(payload.get("decision") or "reject"), payload.get("approved_by"))

    def write_clarify_pending(self, run_id: str, resume_token: str, *, tool_call_id: str = "") -> None:
        self._write_wait(
            run_id,
            "clarify",
            resume_token,
            {"status": "pending", "tool_call_id": str(tool_call_id or "").strip()},
        )

    def write_clarify_answer(
        self,
        run_id: str,
        resume_token: str,
        *,
        answer: str,
        skipped: bool,
    ) -> None:
        self._write_wait(
            run_id,
            "clarify",
            resume_token,
            {"status": "done", "answer": str(answer or ""), "skipped": bool(skipped)},
        )

    def read_clarify_answer(self, run_id: str, resume_token: str) -> tuple[str, bool] | None:
        payload = self._read_wait(run_id, "clarify", resume_token)
        if not payload or str(payload.get("status") or "") != "done":
            return None
        return (str(payload.get("answer") or ""), bool(payload.get("skipped")))

    def clear_run(self, run_id: str) -> None:
        run_dir = self._run_dir(run_id)
        if not run_dir.exists():
            return
        for path in run_dir.glob("*.json"):
            try:
                path.unlink()
            except OSError:
                continue

    def _wait_path(self, run_id: str, wait_type: str, key: str) -> Path:
        safe_key = str(key or "").strip().replace("/", "_")
        return self._run_dir(run_id) / f"{wait_type}__{safe_key}.json"

    def _write_wait(self, run_id: str, wait_type: str, key: str, payload: dict[str, Any]) -> None:
        rid = str(run_id or "").strip()
        safe_key = str(key or "").strip()
        if not rid or not safe_key:
            return
        body = {
            "run_id": rid,
            "wait_type": wait_type,
            "key": safe_key,
            "updated_at": time.time(),
            **payload,
        }
        _atomic_write_json(self._wait_path(rid, wait_type, safe_key), body)

    def _read_wait(self, run_id: str, wait_type: str, key: str) -> dict[str, Any] | None:
        path = self._wait_path(run_id, wait_type, key)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return payload if isinstance(payload, dict) else None
