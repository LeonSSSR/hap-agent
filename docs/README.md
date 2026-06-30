# HAP Agent 文档

本目录描述当前 HAP Agent 的**架构设计**与**具体实现思路**，与仓库代码一一对应。

| 文档 | 内容 |
|------|------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 总体架构、设计原则、模块边界、部署拓扑 |
| [IMPLEMENTATION.md](./IMPLEMENTATION.md) | 后端/前端实现细节、关键类与调用链 |
| [SSE_PROTOCOL.md](./SSE_PROTOCOL.md) | `run/stream` 事件协议与交互回调 |
| [PAGE_AUTOMATION.md](./PAGE_AUTOMATION.md) | 页面自动化：catalog、registry、锚点、层级选页 |

## 快速理解

```
用户输入
  → POST /api/agent/run/stream (SSE)
  → AgenticRunner（多轮 LLM + 工具选择）
  → MCP 工具（查数据/调 API） 或 hap_op_* / hap_ui_action（页面操作）
  → 前端 AgentPageController 执行 DOM 操作
  → POST /api/agent/run/{run_id}/page-result 回灌
  → LLM 继续下一轮 → run_done
```

架构代号：**`mcp_agentic`**（多轮 Agent + MCP + HAP 页面操作）。

## 与代码的对应关系

| 层级 | 仓库路径 |
|------|----------|
| 后端入口 | `backend/agent-service/main.py` |
| HTTP / SSE | `backend/agent-service/routers/agent.py` |
| 执行循环 | `backend/agent-service/services/agentic_runner.py` |
| 工具编排 | `backend/agent-service/services/orchestrator.py` |
| 页面目录 | `catalog/platform_operations_catalog.json` |
| 前端 Shell | `frontend/packages/agent-ui/src/components/AgentShell/` |
| 宿主集成 | `frontend/host/README.md` |
