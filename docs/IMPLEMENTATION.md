# HAP Agent 实现详解

本文按**请求链路**说明各模块如何实现，便于阅读源码或二次集成。

## 1. 后端实现

### 1.1 启动与配置

| 文件 | 职责 |
|------|------|
| `main.py` | FastAPI 应用、健康检查、`architecture: mcp_agentic` |
| `config.py` / `.env.example` | 模型、JWT、platform_api_mode、超时等 |
| `middleware/auth.py` | Bearer JWT → `AgentIdentity` |

生产启动校验：`AGENT_RUNTIME_ENV=production` 时禁止 dev bypass、空 JWT。

### 1.2 HTTP 路由（`routers/agent.py`）

| 路由 | 实现要点 |
|------|----------|
| `POST /run/stream` | 见 §1.3 |
| `POST /run/{run_id}/page-result` | `run_store.set_page_result` 唤醒 runner |
| `POST /run/{run_id}/confirm` | `run_store.resolve_confirm(resume_token, decision)` |
| `POST /run/{run_id}/clarify` | `run_store.resolve_clarify(resume_token, answer)` |
| `GET /capabilities` | 汇总 MCP 工具 + hap_operations（按 identity 过滤） |
| `GET/POST /sessions/*` | 会话 CRUD、`record_turn` 在 stream 结束时写入 |

### 1.3 SSE 流式实现（关键）

**问题背景**：早期用 `run_in_executor(None, queue.get)` 阻塞线程池，并发 run/stream 会耗尽默认 executor（32 线程），导致新连接 200 但无 `run_start`。

**当前实现**：

```python
# routers/agent.py — 简化示意
event_queue: asyncio.Queue = asyncio.Queue()

def producer():
    for event, data in runner.run_events(...):
        asyncio.run_coroutine_threadsafe(event_queue.put((event, data)), loop)
    asyncio.run_coroutine_threadsafe(event_queue.put(None), loop)

threading.Thread(target=producer, daemon=True).start()

while True:
    item = await asyncio.wait_for(event_queue.get(), timeout=0.25)
    yield f"event: {event}\ndata: {json.dumps(data)}\n\n"
```

- **Producer 线程**：同步迭代 `AgenticRunner.run_events`（含 LLM 阻塞调用）。
- **Async consumer**：`asyncio.Queue` 桥接，不占用默认线程池。
- **断开检测**：`http_request.is_disconnected()` → `cancel_check` → runner 发 `run_done stopped`。
- **会话落库**：`finally` 里 `session_store.record_turn`。

### 1.4 AgenticRunner（`services/agentic_runner.py`）

多轮循环伪代码：

```
run_start(run_id, trace_id)
for turn in 1..max_turns:
    tools = select_tools_for_llm() + build_hierarchical_ui_tool_ids()
    llm_out = AgenticLlmClient.chat(tools=tools, messages=...)
    stream assistant_delta / reasoning_delta

    for each tool_call in llm_out.tool_calls:
        if tool is hap_clarify:
            emit clarify_required → wait clarify → continue
        if tool needs confirm (medium/high risk):
            emit confirm_required → wait confirm → continue
        if tool is hap_op_* / hap_ui_action:
            validate permission + page state
            emit page_action → wait page-result (run_store)
            emit tool_result
        else:
            orchestrator.execute_tool (MCP)
            emit tool_start / tool_result

    if no more tool_calls: break

run_done(status, summary)
```

**LLM 层**（`agentic_llm.py`）：

- `mock`：规则/MockAgenticLlm，CI 无 key 可跑。
- `openai_compatible`：DeepSeek 等，支持 stream delta。
- `AGENT_MODEL_FALLBACK_TO_RULES`：失败回退 mock。

**工具 schema**（`agentic_tool_schema.py` + `operation_tools.py`）：

- MCP 工具来自 `tool_registry` / YAML。
- 每个 catalog 条目生成 `hap_op_{id}`，参数 schema 含 `id`（动态路由）等。

### 1.5 AgentOrchestrator（`services/orchestrator.py`）

- `build_contextual_input`：拼接长期记忆 + 会话 summary。
- `bind_tool_executor`：闭包注入 `identity`、`allow_real_write`、`confirmed`。
- `execute_tool` → `MCPAdapter.call` → `RestrictedExecutor`（策略、审计、写保护）。

### 1.6 页面操作后端路径

| 步骤 | 代码 |
|------|------|
| 校验 ui_action_id | `valid_ui_action_ids()`、`identity_allows_ui_action` |
| 校验导航状态 | `validate_navigate_page` / `validate_page_action` |
| 发 SSE | `("page_action", { ui_action_id, route, action_type, ... })` |
| 等待前端 | `run_store.wait_page_result(run_id, tool_call_id, timeout)` |
| 更新层级状态 | `advance_state_after_ui_success(PageRunState)` |

工具名约定：

- `hap_op_{ui_action_id}`：catalog 派生的 OpenAI function（`.` → `_`）。
- `hap_ui_action`：通用兜底工具（参数里带 `ui_action_id`）。

### 1.7 确认与澄清

| 机制 | run_store | SSE 事件 |
|------|-----------|----------|
| 高风险 MCP/ui | `register_confirm_wait` / `wait_confirm` | `confirm_required` |
| 缺参 | `register_clarify_wait` / `wait_clarify` | `clarify_required` |

前端 POST confirm/clarify 后，阻塞在 `wait_*` 的 runner 线程被唤醒，继续 tool 执行或写入 tool 错误消息给 LLM。

### 1.8 Catalog 服务（`platform_operations_catalog.py`）

- 加载 JSON，提供 `get_operation`、`filter_ui_actions_for_identity`。
- `resolve_operations_from_text`：意图匹配候选 ui_action（供层级选择）。
- 路由回退：详情页无 `id` 时 `_ROUTE_LIST_FALLBACKS` 导向列表页。

### 1.9 测试策略

`backend/agent-service/tests/`（35 文件）覆盖：

- SSE cancel、confirm/clarify gate、权限、ui_action catalog 覆盖率
- MCP binding、session 契约、DeepSeek live（`-m live` 可选）

CI：`.github/workflows/agent-service-tests-smoke.yml` / `nightly.yml`。

---

## 2. 前端实现

### 2.1 模块结构

```
frontend/packages/agent-ui/src/
├── services/agent.ts              # HTTP + SSE 客户端
└── components/AgentShell/
    ├── AgentShellHost.tsx         # 全站 FAB + 侧栏布局（宿主挂载）
    ├── index.tsx                  # 主面板 UI、发送、会话、能力页
    ├── agenticStreamSession.ts    # SSE 事件状态机
    ├── AgentPageController.ts     # DOM 自动化 + 高亮
    ├── AgentActionRegistry.ts     # ui_action_id → selector/type
    ├── platformOperationsMap.ts   # catalog 查询辅助
    ├── AgentClarifyBar.tsx        # 澄清条
    ├── AgentConfirmBar.tsx        # 确认条
    ├── ExecutionLogPanel.tsx      # 执行日志（默认展开）
    ├── agentDemoTiming.ts         # 演示慢速间隔
    └── agentPermissions.ts        # super_admin / confirm 权限
```

### 2.2 API 客户端（`services/agent.ts`）

- `runAgentStream`：`fetch` + `ReadableStream` 解析 SSE（`event:` / `data:`）。
- `postAgentPageResult`、`postAgentRunConfirm`、`postAgentRunClarify`：回调端点。
- 依赖宿主 `@/utils/request`、`@/utils/auth`（JWT header）。

### 2.3 流式会话（`agenticStreamSession.ts`）

`runAgenticStreamSession` 是前端**核心状态机**：

1. 确保 `sessionId`（localStorage）。
2. 调用 `runAgentStream`，逐条 dispatch SSE。
3. **`page_action`** → `AgentPageController.executeUiAction` → `postAgentPageResult`。
4. **`confirm_required`** → `onConfirmRequired`（UI Promise）→ `postAgentRunConfirm`。
5. **`clarify_required`** → `onClarificationRequired` → `postAgentRunClarify`（支持选项自动提交、403 重试）。
6. 维护 `activities[]`（tool_start/result/blocked）供 UI 展示。
7. 结束态：`completed` | `stopped` | `failed` | `aborted`。

### 2.4 页面控制器（`AgentPageController.ts`）

执行顺序（带演示慢速 `AGENT_DEMO_TIMING`）：

1. **`navigate`**：`history.push` + `waitForRouteSettled`。
2. **`highlight`**：红色 outline 或四角标（大容器用角标避免遮罩整表）。
3. **`click` / `fill`**：`pickHighlightTarget` 收窄到内部按钮 → 点击/填值。
4. **`scrollIntoView`**：滚动可见。
5. 微步骤回调 `onMicroStep` → 执行日志（无虚拟光标，仅高亮框）。

DOM 定位：

```typescript
// 默认：data-agent-action-id 属性
document.querySelector(`[data-agent-action-id="${uiActionId}"]`)
// Registry 可 override selector、route、type
getAgentActionDefinition(uiActionId)
```

### 2.5 主面板（`index.tsx`）

- 输入框发送 → `runAgenticStreamSession`。
- `AgentConfirmBar` / `AgentClarifyBar` 与 pending 状态联动。
- 能力 Tab：按模块分组展示 MCP + hap_operations。
- 演示慢速 Switch、执行日志、`AgentActivityBlock` 推理/工具块。

### 2.6 宿主集成（不在本仓库，但必须）

见 [frontend/host/README.md](../frontend/host/README.md)：

1. 拷贝 AgentShell + agent.ts。
2. `app.tsx`：`childrenRender` 包 `AgentShellHost`。
3. `.umirc.ts`：`/api/agent` → `8010`。
4. 业务页加 `data-agent-action-id`，与 catalog 一致。

---

## 3. Catalog 工作流

```bash
# 1. 编辑权威源
vim catalog/platform_operations_catalog.json

# 2. 同步到前后端
bash scripts/sync-catalog.sh

# 3. 宿主 frontend 根目录校验
node scripts/verify-agent-registry.mjs
node scripts/verify-agent-page-anchors.mjs
```

`AgentActionRegistry.ts` 中 `BUTTON_ACTION_OVERRIDES` 用于 selector 复杂、一个 ui_action 多 DOM 等特殊情况；大部分条目由 `buildPlatformAgentActions(catalog)` 自动生成。

---

## 4. 关键环境变量

| 变量 | 实现影响 |
|------|----------|
| `AGENT_MODEL_*` | LLM 提供商与模型 |
| `AGENT_JWT_SECRET` | 与 core-service 一致才能解析用户 |
| `AGENT_PLATFORM_API_MODE` | mock / live / hybrid |
| `AGENT_AUTH_REQUIRED` | 是否强制 Bearer |
| `AGENTIC_CONFIRM_*_SECONDS` | confirm 超时 |
| `AGENT_MODEL_THINKING_ENABLED` | 推理链 delta 事件 |

完整列表见 `backend/agent-service/.env.example`。

---

## 5. 从主平台同步更新

主仓 `ai-platform` 演进后，在 monorepo 根目录：

```bash
rsync -a --exclude venv --exclude data/sessions --exclude data/run_state \
  /path/to/ai-platform/backend/agent-service/ backend/agent-service/

rsync -a /path/to/ai-platform/frontend/src/components/AgentShell/ \
  frontend/packages/agent-ui/src/components/AgentShell/

cp /path/to/ai-platform/frontend/src/services/agent.ts \
  frontend/packages/agent-ui/src/services/agent.ts

bash scripts/sync-catalog.sh
```

然后 `pytest` + verify 脚本 + 提交。
