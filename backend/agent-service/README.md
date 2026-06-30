# agent-service

HAP 平台 **Agentic** 服务：多轮大模型 + MCP 工具 + HAP 页面操作。唯一对话执行入口为 SSE 流式 `POST /api/agent/run/stream`。

## 架构

```
用户输入 → POST /api/agent/run/stream (SSE)
         → AgenticRunner（AGENT_MODEL_* 多轮 + 工具）
         → MCP 工具 / hap_op_* 页面操作工具（按层级动态暴露）
         → 前端 page-result 回灌（页面操作）
```

## 快速启动

```bash
cd backend/agent-service
cp .env.example .env   # 按需填写 AGENT_MODEL_API_KEY
uvicorn main:app --host 0.0.0.0 --port 8010 --reload
curl -s http://127.0.0.1:8010/health | jq .
```

## 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `AGENT_MODEL_PROVIDER` | `mock` \| `openai_compatible` | `mock` |
| `AGENT_MODEL_API_KEY` | API Key | 空 → Mock |
| `AGENT_MODEL_BASE_URL` | 兼容 API 根路径 | `https://api.deepseek.com` |
| `AGENT_MODEL_NAME` | 模型名 | `deepseek-v4-pro` |
| `AGENT_MODEL_FALLBACK_TO_RULES` | LLM 失败时回退 Mock | `true` |
| `AGENT_PLATFORM_API_MODE` | `mock` \| `live` \| `hybrid` | `hybrid` |

DeepSeek 示例：

```bash
export AGENT_MODEL_PROVIDER=openai_compatible
export AGENT_MODEL_API_KEY=sk-...
export AGENT_MODEL_BASE_URL=https://api.deepseek.com
export AGENT_MODEL_NAME=deepseek-v4-pro
```

## 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查，`architecture: mcp_agentic` |
| POST | `/api/agent/run/stream` | **主路径**：Agentic SSE |
| POST | `/api/agent/run/{run_id}/page-result` | 前端上报 `hap_ui_action` 结果 |
| POST | `/api/agent/run/{run_id}/confirm` | 高风险操作确认 |
| POST | `/api/agent/run/{run_id}/clarify` | 参数澄清 |
| GET | `/api/agent/capabilities` | 能力清单 |
| GET/POST/PUT/DELETE | `/api/agent/sessions/*` | 会话与历史 |
| GET | `/api/agent/audits`, `/traces/*` | 追踪与审计 |

## 测试

```bash
cd backend/agent-service
pip install -r requirements.txt pytest httpx
pytest tests/ -q

# 可选：DeepSeek 真 LLM（需 API Key）
AGENT_MODEL_API_KEY=sk-... pytest tests/test_agent_model_deepseek.py -m live -v
```

## 目录说明

| 路径 | 作用 |
|------|------|
| `routers/agent.py` | Agent API |
| `services/agentic_runner.py` | 多轮执行循环 |
| `services/agentic_llm*.py` | Mock / OpenAI 兼容 LLM |
| `services/orchestrator.py` | MCP 工具执行边界 |
| `services/platform_operations_catalog.py` | HAP `ui_action_id` 目录 |
| `data/platform_operations_catalog.json` | 页面操作权威目录 |
| `mcp/tools/*.yaml` | MCP 工具定义 |
| `tests/` | Agentic 契约测试 |
