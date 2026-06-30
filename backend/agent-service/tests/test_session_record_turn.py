from __future__ import annotations

from services.session_store import SessionStore


def test_record_turn_appends_exchange(tmp_path) -> None:
    store = SessionStore(base_path=str(tmp_path), context_window=8)
    session = store.create(title="测试会话", owner="test-user")
    session_id = str(session["session_id"])

    store.record_turn(
        session_id,
        user_message="第一条问题",
        assistant_message="第一条回答",
        run_id="run-abc",
        status="completed",
        chat_response={"reply": "第一条回答"},
    )
    store.record_turn(
        session_id,
        user_message="第二条问题",
        assistant_message="第二条回答",
        run_id="run-def",
        status="completed",
    )

    messages = store.list_messages(session_id)
    assert len(messages) == 4
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["metadata"]["chat_response"]["reply"] == "第一条回答"
    assert messages[2]["content"] == "第二条问题"

    context = store.build_context(session_id)
    assert context is not None
    assert "第一条问题" in str(context.get("summary") or "")
    assert "第二条回答" in str(context.get("summary") or "")


def test_build_llm_messages_includes_history(tmp_path) -> None:
    store = SessionStore(base_path=str(tmp_path), context_window=8)
    session = store.create(title="多轮会话", owner="test-user")
    session_id = str(session["session_id"])
    store.record_turn(
        session_id,
        user_message="我叫小明",
        assistant_message="你好小明",
        run_id="run-1",
        status="completed",
    )

    messages = store.build_llm_messages(
        session_id,
        system_prompt="你是助手",
        current_user_message="我刚才说我叫什么？",
    )
    roles = [m["role"] for m in messages]
    contents = [m["content"] for m in messages]
    assert roles == ["system", "user", "assistant", "user"]
    assert "我叫小明" in contents
    assert "你好小明" in contents
    assert contents[-1] == "我刚才说我叫什么？"


def test_record_turn_skips_duplicate_exchange(tmp_path) -> None:
    store = SessionStore(base_path=str(tmp_path))
    session = store.create(title="去重", owner="test-user")
    session_id = str(session["session_id"])
    store.record_turn(
        session_id,
        user_message="同一条",
        assistant_message="同一答",
        run_id="run-1",
        status="completed",
    )
    store.record_turn(
        session_id,
        user_message="同一条",
        assistant_message="同一答",
        run_id="run-1",
        status="completed",
    )
    assert len(store.list_messages(session_id)) == 2
