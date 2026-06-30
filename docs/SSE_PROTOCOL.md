# SSE 事件协议

`POST /api/agent/run/stream` 返回 `Content-Type: text/event-stream`。

每条消息格式：

```
event: <event_name>
data: <json object>

```

`data` 均为 JSON 对象，`ensure_ascii=False`（中文不转义）。

## 1. 生命周期事件

| event | 典型字段 | 说明 |
|-------|----------|------|
| `run_start` | `run_id`, `trace_id`, `session_id` |  run 开始；前端保存 run_id 供 page-result/confirm/clarify |
| `run_done` | `status`, `summary?` | 结束；`status`: `completed` \| `stopped` \| `failed` |
| `error` | `message`, `code`, `turn?` | 致命或 LLM 错误 |

## 2. LLM 输出事件

| event | 字段 | 说明 |
|-------|------|------|
| `assistant_delta` | `delta`, `turn` | 助手文本流式片段 |
| `assistant_message` | `content`, `turn` | 助手完整一句（非流式或 turn 结束） |
| `reasoning_delta` | `delta`, `turn` | 推理链流式（模型支持 thinking 时） |
| `reasoning_message` | `content`, `turn` | 推理完整内容 |

前端合并 delta 展示在 `AgentAssistantText` / `AgentReasoningBlock`。

## 3. 工具执行事件

| event | 字段 | 说明 |
|-------|------|------|
| `tool_start` | `tool_call_id`, `tool_name`, `turn`, `index` | MCP 或 ui 工具开始 |
| `tool_result` | `tool_call_id`, `tool_name`, `preview`, `turn` | 工具成功；`preview` 给 UI 摘要 |
| `tool_blocked` | `tool_call_id`, `blocked_reason`, `blocked_label` | 拒绝/超时/用户拒绝确认 |

`blocked_reason` 示例：`approval_required`、`tool_confirm_pending`、`permission_denied`。

## 4. 页面操作事件

| event | 字段 | 说明 |
|-------|------|------|
| `page_action` | `tool_call_id`, `ui_action_id`, `action_type`, `route`, `navigate_route`, `params`, `title` | 请前端执行 DOM 操作 |

前端处理流程：

```
page_action
  → AgentPageController.executeUiAction(...)
  → POST /api/agent/run/{run_id}/page-result
      { tool_call_id, ui_action_id, success, message, detail }
```

后端 `run_store.wait_page_result` 超时则向 LLM 返回 error tool message。

## 5. 人机协同事件

### 5.1 确认（高风险）

| event | 字段 |
|-------|------|
| `confirm_required` | `run_id`, `tool_call_id`, `tool_name`, `ui_action_id?`, `risk_level`, `resume_token`, `turn` |

前端展示 `AgentConfirmBar`，用户批准后：

```
POST /api/agent/run/{run_id}/confirm
{ "resume_token": "...", "decision": "approve", "approved_by": "username" }
```

拒绝：`decision: "reject"` → runner 发 `tool_blocked`。

### 5.2 澄清（缺参）

| event | 字段 |
|-------|------|
| `clarify_required` | `run_id`, `tool_call_id`, `question`, `resume_token`, `fields?`, `choices?`, `placeholder?` |

前端展示 `AgentClarifyBar`（支持选项 chips 自动提交）：

```
POST /api/agent/run/{run_id}/clarify
{ "resume_token": "...", "answer": "...", "skipped": false }
```

## 6. 请求体

```json
{
  "message": "打开数据源页面并新建",
  "session_id": "可选，续聊",
  "options": {
    "max_turns": 20,
    "confirm_high_risk": true,
    "execution_mode": "controlled_mock"
  }
}
```

## 7. 客户端实现要点

1. **AbortSignal**：用户点停止 → abort fetch → 后端 disconnect → `run_done stopped`。
2. **并发**：同一 session 避免并行多个 stream（易占满后端资源）。
3. **重试 clarify/confirm POST**：网络失败时前端应提示并可重试（已实现 `onClarificationPostFailed`）。
4. **Nginx**：必须 `proxy_read_timeout` 足够长（建议 600s+），且 `proxy_buffering off`。

## 8. 示例片段

```
event: run_start
data: {"run_id":"run-abc","trace_id":"trace-xyz","session_id":"sess-1"}

event: assistant_delta
data: {"delta":"好的","turn":1}

event: page_action
data: {"tool_call_id":"call_1","ui_action_id":"dg.sources","action_type":"navigate","route":"/data-governance/sources","title":"数据源"}

event: tool_result
data: {"tool_call_id":"call_1","tool_name":"hap_op_dg_sources","preview":{"success":true},"turn":1}

event: run_done
data: {"status":"completed","summary":"已打开数据源页面。"}
```

完整字段以 `services/agentic_runner.py` 与各 `yield ("event", {...})` 为准。
