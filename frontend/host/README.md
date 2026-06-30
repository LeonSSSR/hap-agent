# Host 应用集成说明

`packages/agent-ui` 是从 HAP 平台抽出的 Agent 前端模块，需嵌入你的 React/Umi 宿主应用。

## 1. 拷贝模块

```bash
# 将 agent-ui 合并到宿主 frontend 工程
cp -r ../packages/agent-ui/src/components/AgentShell  src/components/
cp ../packages/agent-ui/src/services/agent.ts src/services/
```

## 2. 开发代理（Umi `.umirc.ts`）

```ts
proxy: {
  '/api/agent': {
    target: 'http://localhost:8010',
    changeOrigin: true,
    timeout: 600000,
    proxyTimeout: 600000,
  },
},
```

## 3. 全站挂载 Agent 面板

在 `app.tsx` 的 `childrenRender` 中包裹：

```tsx
import { AgentShellHost } from '@/components/AgentShell/AgentShellHost';

childrenRender: (children) => (
  <AgentShellHost>{children}</AgentShellHost>
),
```

## 4. 页面自动化锚点

业务页按钮需带 `data-agent-action-id`，与 `catalog/platform_operations_catalog.json` 及 `AgentActionRegistry.ts` 一致。

校验：

```bash
node ../../scripts/verify-agent-registry.mjs
node ../../scripts/verify-agent-page-anchors.mjs
```

## 5. 权限

确认栏读取宿主 `initialState.roles` / `permissions`（见 `agentPermissions.ts`）。
