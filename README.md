# HAP Agent Monorepo

HAP 平台 Agent 模块：**多轮 LLM + MCP 工具 + 页面 ui_action 自动化**。

**仓库**：[github.com/LeonSSSR/hap-agent](https://github.com/LeonSSSR/hap-agent)

## 设计与实现文档

| 文档 | 说明 |
|------|------|
| [docs/README.md](docs/README.md) | 文档索引 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构设计、模块边界、部署拓扑 |
| [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) | 后端/前端实现细节与调用链 |
| [docs/SSE_PROTOCOL.md](docs/SSE_PROTOCOL.md) | `run/stream` SSE 事件协议 |
| [docs/PAGE_AUTOMATION.md](docs/PAGE_AUTOMATION.md) | Catalog、Registry、DOM 锚点 |

## 目录结构

```
hap-agent/
├── backend/agent-service/          # FastAPI，端口 8010，SSE /api/agent/run/stream
├── frontend/
│   ├── packages/agent-ui/          # AgentShell + agent.ts API 客户端
│   └── host/                       # 宿主应用集成说明
├── catalog/
│   └── platform_operations_catalog.json   # ui_action 权威目录（单一源）
├── scripts/
│   ├── sync-catalog.sh             # 同步 catalog → 前后端
│   └── verify-agent-*.mjs          # 锚点/registry 校验（在宿主 frontend 下运行）
├── deploy/
│   ├── docker-compose.agent.yml
│   └── nginx-agent-snippet.conf
└── .github/workflows/              # agent-service CI
```

## 快速启动（后端）

```bash
cd backend/agent-service
cp .env.example .env
# 填写 AGENT_MODEL_API_KEY、AGENT_JWT_SECRET（与平台 core-service 一致）
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8010
curl -s http://127.0.0.1:8010/health | jq .
```

## Catalog 同步

修改 `catalog/platform_operations_catalog.json` 后：

```bash
bash scripts/sync-catalog.sh
```

## 测试

```bash
cd backend/agent-service && pytest tests/ -q
```

## 新平台部署清单

| 项 | 说明 |
|----|------|
| agent-service | 8010，环境变量见 `backend/agent-service/.env.example` |
| Nginx | `location ^~ /api/agent/` → `http://127.0.0.1:8010` |
| 前端 | 集成 `agent-ui` + JWT + 页面 `data-agent-action-id` |
| core-service | MCP live 模式需 `:8085` 可访问 |

## 前端集成

见 [frontend/host/README.md](frontend/host/README.md)。

## 从 HAP 主仓同步更新

在本 monorepo 目录外的主平台仓库中更新 Agent 后，可重新 rsync：

```bash
rsync -a --exclude venv --exclude data/sessions --exclude data/run_state \
  /path/to/ai-platform/backend/agent-service/ backend/agent-service/
rsync -a /path/to/ai-platform/frontend/src/components/AgentShell/ \
  frontend/packages/agent-ui/src/components/AgentShell/
bash scripts/sync-catalog.sh
```

## License

与 HAP 主平台保持一致（请按你的组织策略填写）。
