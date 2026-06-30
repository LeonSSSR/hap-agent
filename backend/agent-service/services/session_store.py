"""Session and conversation memory with optional JSONL persistence."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from config import settings
from services.long_term_memory import long_term_memory


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionStore:
    def __init__(self, base_path: str | None = None, *, context_window: int = 12) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}
        self._messages: dict[str, list[dict[str, Any]]] = {}
        self._lock = Lock()
        self._context_window = max(1, int(context_window))
        self._base_path = Path(base_path) if base_path else None
        if self._base_path:
            self._base_path.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    @property
    def persistence_enabled(self) -> bool:
        return self._base_path is not None

    def _sessions_file(self) -> Path:
        assert self._base_path is not None
        return self._base_path / "sessions.jsonl"

    def _messages_file(self, session_id: str) -> Path:
        assert self._base_path is not None
        return self._base_path / f"{session_id}.messages.jsonl"

    def _append_jsonl(self, path: Path, record: dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        with self._lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def _load_from_disk(self) -> None:
        if not self._base_path:
            return
        sessions_file = self._sessions_file()
        if not sessions_file.exists():
            return
        with sessions_file.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                session_id = str(record.get("session_id") or record.get("sessionId") or "").strip()
                if not session_id:
                    continue
                self._sessions[session_id] = record
                msg_file = self._messages_file(session_id)
                if msg_file.exists():
                    messages: list[dict[str, Any]] = []
                    with msg_file.open(encoding="utf-8") as mf:
                        for mline in mf:
                            mline = mline.strip()
                            if not mline:
                                continue
                            try:
                                msg = json.loads(mline)
                            except json.JSONDecodeError:
                                continue
                            if isinstance(msg, dict):
                                messages.append(msg)
                    self._messages[session_id] = messages

    def create(self, *, title: str | None = None, owner: str) -> dict[str, Any]:
        owner_name = str(owner or "").strip()
        if not owner_name:
            raise ValueError("owner is required")
        session_id = f"session-{uuid4().hex[:12]}"
        timestamp = _utc_now()
        record = {
            "session_id": session_id,
            "sessionId": session_id,
            "owner": owner_name,
            "created_at": timestamp,
            "updated_at": timestamp,
            "status": "active",
            "mode": "mcp_agentic",
            "title": str(title or "新对话"),
            "summary": "",
            "last_run_id": None,
            "message_count": 0,
        }
        with self._lock:
            self._sessions[session_id] = record
            self._messages.setdefault(session_id, [])
        if self.persistence_enabled:
            self._append_jsonl(self._sessions_file(), record)
        return deepcopy(record)

    def get(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or self._is_deleted(session):
                return None
            return deepcopy(session)

    def _is_deleted(self, session: dict[str, Any]) -> bool:
        if not session:
            return True
        if str(session.get("status") or "").strip().lower() == "deleted":
            return True
        return bool(session.get("deleted_at"))

    def exists(self, session_id: str) -> bool:
        return self.get(session_id) is not None

    def _exchange_already_recorded(
        self,
        session_id: str,
        user_text: str,
        assistant_text: str,
    ) -> bool:
        with self._lock:
            msgs = list(self._messages.get(session_id, []))
        expected: list[tuple[str, str]] = []
        if user_text:
            expected.append(("user", user_text))
        if assistant_text:
            expected.append(("assistant", assistant_text))
        if not expected or len(msgs) < len(expected):
            return False
        tail = msgs[-len(expected) :]
        for (role, content), msg in zip(expected, tail, strict=True):
            if str(msg.get("role")) != role or str(msg.get("content") or "").strip() != content:
                return False
        return True

    def list_messages(self, session_id: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            messages = list(self._messages.get(session_id, []))
        if limit is not None and limit > 0:
            return deepcopy(messages[-limit:])
        return deepcopy(messages)

    def record_turn(
        self,
        session_id: str,
        *,
        user_message: str,
        assistant_message: str,
        run_id: str | None = None,
        status: str = "completed",
        chat_response: dict[str, Any] | None = None,
    ) -> None:
        """Append one user/assistant exchange for in-session memory and optional long-term indexing."""
        if not self.exists(session_id):
            return
        user_text = str(user_message or "").strip()
        assistant_text = str(assistant_message or "").strip()
        if self._exchange_already_recorded(session_id, user_text, assistant_text):
            return
        if user_text:
            self.append_message(session_id, role="user", content=user_text)
        if assistant_text:
            metadata: dict[str, Any] = {"status": status}
            if run_id:
                metadata["run_id"] = run_id
            if isinstance(chat_response, dict) and chat_response:
                metadata["chat_response"] = deepcopy(chat_response)
            self.append_message(session_id, role="assistant", content=assistant_text, metadata=metadata)
        if run_id:
            with self._lock:
                stored = self._sessions.get(session_id)
                if stored:
                    stored["last_run_id"] = run_id
                    stored["updated_at"] = _utc_now()
        if (
            settings.long_term_memory_enabled
            and long_term_memory.enabled
            and status == "completed"
            and user_text
            and assistant_text
        ):
            session = self.get(session_id) or {}
            long_term_memory.index_turn(
                session_id=session_id,
                user_input=user_text,
                assistant_reply=assistant_text,
                username=str(session.get("owner") or "").strip() or None,
            )

    def append_message(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        session = self.get(session_id)
        if session is None:
            return
        message = {
            "message_id": f"msg-{uuid4().hex[:12]}",
            "messageId": f"msg-{uuid4().hex[:12]}",
            "role": role,
            "content": content,
            "created_at": _utc_now(),
            "metadata": deepcopy(metadata or {}),
        }
        with self._lock:
            self._messages.setdefault(session_id, []).append(message)
            stored = self._sessions.get(session_id)
            if stored:
                stored["message_count"] = len(self._messages.get(session_id, []))
                stored["updated_at"] = _utc_now()
        if self.persistence_enabled:
            self._append_jsonl(self._messages_file(session_id), message)

    def build_context(self, session_id: str) -> dict[str, Any] | None:
        if not self.exists(session_id):
            return None
        messages = self.list_messages(session_id, limit=self._context_window)
        lines = [f"{m.get('role')}: {m.get('content')}" for m in messages if m.get("content")]
        session = self.get(session_id) or {}
        return {
            "session_id": session_id,
            "summary": "\n".join(lines)[-1200:],
            "message_count": session.get("message_count", len(messages)),
            "last_run_id": session.get("last_run_id"),
        }

    def build_llm_messages(
        self,
        session_id: str,
        *,
        system_prompt: str,
        current_user_message: str,
    ) -> list[dict[str, Any]]:
        """Build OpenAI-style messages with recent session history for multi-turn LLM context."""
        out: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        if not self.exists(session_id):
            current = str(current_user_message or "").strip()
            if current:
                out.append({"role": "user", "content": current})
            return out

        for msg in self.list_messages(session_id, limit=self._context_window):
            role = str(msg.get("role") or "")
            content = str(msg.get("content") or "").strip()
            if role not in {"user", "assistant"} or not content:
                continue
            out.append({"role": role, "content": content})

        current = str(current_user_message or "").strip()
        if current and not (
            out
            and out[-1].get("role") == "user"
            and str(out[-1].get("content") or "").strip() == current
        ):
            out.append({"role": "user", "content": current})
        return out

    def save_conversation(
        self,
        session_id: str,
        *,
        title: str | None = None,
        turns: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        if not self.exists(session_id):
            return None
        rebuilt: list[dict[str, Any]] = []
        first_user_title = ""
        for turn in turns or []:
            if not isinstance(turn, dict):
                continue
            user_msg = str(turn.get("userMessage") or turn.get("user_message") or "").strip()
            assistant = str(turn.get("assistantReply") or turn.get("assistant_reply") or "").strip()
            chat_response = turn.get("chatResponse") or turn.get("chat_response")
            if user_msg:
                if not first_user_title:
                    first_user_title = user_msg[:40]
                rebuilt.append({"role": "user", "content": user_msg, "metadata": {}})
            if assistant or chat_response:
                meta: dict[str, Any] = {}
                if isinstance(chat_response, dict):
                    meta["chat_response"] = chat_response
                rebuilt.append({"role": "assistant", "content": assistant, "metadata": meta})
        with self._lock:
            normalized: list[dict[str, Any]] = []
            for item in rebuilt:
                normalized.append(
                    {
                        "message_id": f"msg-{uuid4().hex[:12]}",
                        "messageId": f"msg-{uuid4().hex[:12]}",
                        "role": item["role"],
                        "content": item["content"],
                        "created_at": _utc_now(),
                        "metadata": item.get("metadata") or {},
                    }
                )
            self._messages[session_id] = normalized
            stored = self._sessions.get(session_id)
            if stored:
                stored["message_count"] = len(normalized)
                stored["updated_at"] = _utc_now()
                stored["title"] = str(title or first_user_title or stored.get("title") or "新对话")
                stored["status"] = "saved"
        if self.persistence_enabled:
            msg_file = self._messages_file(session_id)
            msg_file.write_text("", encoding="utf-8")
            for msg in self._messages.get(session_id, []):
                self._append_jsonl(msg_file, msg)
            if stored:
                self._append_jsonl(self._sessions_file(), stored)
        return {
            "sessionId": session_id,
            "status": "saved",
            "title": stored.get("title") if stored else title,
            "message_count": len(self._messages.get(session_id, [])),
        }

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            stored = self._sessions.get(session_id)
            if not stored:
                return False
            stored["status"] = "deleted"
            stored["deleted_at"] = _utc_now()
            self._messages.pop(session_id, None)
        return True

    def list_sessions(
        self,
        *,
        owner: str | None = None,
        include_all: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        with self._lock:
            items = [
                deepcopy(s)
                for s in self._sessions.values()
                if not self._is_deleted(s)
            ]
        if not include_all:
            owner_name = str(owner or "").strip()
            items = [s for s in items if str(s.get("owner") or "").strip() == owner_name]
        items.sort(key=lambda s: str(s.get("updated_at") or ""), reverse=True)
        return items[offset : offset + limit]

    def search_long_term_memory(
        self,
        query: str,
        *,
        session_id: str | None = None,
        owner: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        if not settings.long_term_memory_enabled or not long_term_memory.enabled:
            return []
        return long_term_memory.search(
            query,
            limit=limit,
            exclude_session_id=session_id,
            username=str(owner or "").strip() or None,
        )

    def to_api_session(self, session_id: str) -> dict[str, Any] | None:
        session = self.get(session_id)
        if session is None:
            return None
        messages = self.list_messages(session_id)
        return {
            "sessionId": session_id,
            "session_id": session_id,
            "title": session.get("title"),
            "summary": session.get("summary"),
            "status": session.get("status"),
            "created_at": session.get("created_at"),
            "updated_at": session.get("updated_at"),
            "message_count": session.get("message_count", len(messages)),
            "messages": messages,
        }


_base_path = settings.session_store_path.strip() if settings.session_store_path else None
session_store = SessionStore(base_path=_base_path, context_window=settings.session_context_window)
