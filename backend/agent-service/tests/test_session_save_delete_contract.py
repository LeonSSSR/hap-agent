from __future__ import annotations

from fastapi.testclient import TestClient

from main import app
from services.session_store import SessionStore


client = TestClient(app)


def test_save_session_persists_turns(tmp_path) -> None:
  store = SessionStore(base_path=str(tmp_path), context_window=8)
  session = store.create(title="新对话", owner="test-user")
  session_id = str(session["session_id"])

  saved = store.save_conversation(
    session_id,
    turns=[
      {
        "userMessage": "查看数据血缘",
        "assistantReply": "将查询血缘链路",
        "chatResponse": {"reply": "将查询血缘链路", "understanding": "血缘查询"},
      }
    ],
  )
  assert saved is not None
  assert saved["status"] == "saved"
  assert saved["title"] == "查看数据血缘"

  messages = store.list_messages(session_id)
  assert len(messages) == 2
  assert messages[0]["role"] == "user"
  assert messages[1]["role"] == "assistant"
  assert messages[1]["metadata"]["chat_response"]["understanding"] == "血缘查询"


def test_delete_session_api() -> None:
  created = client.post("/api/agent/sessions")
  assert created.status_code == 200
  session_id = created.json()["sessionId"]

  save_response = client.put(
    f"/api/agent/sessions/{session_id}",
    json={
      "turns": [
        {
          "userMessage": "查询任务状态",
          "assistantReply": "已返回任务状态",
        }
      ]
    },
  )
  assert save_response.status_code == 200
  assert save_response.json()["data"]["status"] == "saved"

  delete_response = client.delete(f"/api/agent/sessions/{session_id}")
  assert delete_response.status_code == 200
  assert delete_response.json()["data"]["deleted"] is True

  get_response = client.get(f"/api/agent/sessions/{session_id}")
  assert get_response.status_code == 404

  listed = client.get("/api/agent/sessions").json()["data"]["items"]
  assert all(item["sessionId"] != session_id for item in listed)


def test_save_session_and_new_via_api_flow() -> None:
  first = client.post("/api/agent/sessions")
  first_id = first.json()["sessionId"]
  client.put(
    f"/api/agent/sessions/{first_id}",
    json={"turns": [{"userMessage": "第一条", "assistantReply": "回复一"}]},
  )

  second = client.post("/api/agent/sessions")
  second_id = second.json()["sessionId"]
  assert second_id != first_id

  first_detail = client.get(f"/api/agent/sessions/{first_id}").json()["data"]
  assert first_detail["message_count"] == 2
  assert first_detail["status"] == "saved"
