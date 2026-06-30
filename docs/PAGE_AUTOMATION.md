# 页面自动化实现

HAP Agent 的「能点击平台按钮」能力由 **Catalog + Registry + DOM 锚点** 三层协作实现。

## 1. 三层模型

```
platform_operations_catalog.json     ← 权威：能做什么、路由、风险、权限
           │
           ├─► 后端 operation_tools.py   → hap_op_* LLM 工具
           │
           └─► 前端 platformOperationsMap + AgentActionRegistry
                        │
                        ▼
              业务页 data-agent-action-id   ← 真实 DOM 锚点
```

| 层 | 位置 | 职责 |
|----|------|------|
| Catalog | `catalog/platform_operations_catalog.json` | 平台级操作目录，单一源 |
| Registry | `AgentActionRegistry.ts` | ui_action_id → selector、action type、route |
| 锚点 | 宿主 `src/pages/**/*.tsx` | HTML 上的 `data-agent-action-id` 属性 |

**本仓库含 Catalog + Registry**；**锚点在 HAP 主平台 104+ 页面**，集成时需自行维护或从主仓同步。

## 2. Catalog 条目结构

典型字段（简化）：

```json
{
  "ui_action_id": "dg.sources.create",
  "label": "新建数据源",
  "module": "data_governance",
  "parent_ui_action_id": "dg.sources",
  "action_type": "click",
  "route": "/data-governance/sources",
  "risk_level": "medium",
  "permission_scopes": ["workflow.write"],
  "agent_description": "在数据源列表页点击新建入口"
}
```

### action_type 语义

| 值 | 后端/前端行为 |
|----|----------------|
| `navigate` | 路由跳转（L0 页面根） |
| `click` | 点击按钮/链接 |
| `fill` | 向 input/textarea 填值 |
| `highlight` | 仅高亮，不点击 |
| `open_panel` | 打开抽屉/Modal（常作 L2） |
| `page_action` | 复合页内步骤 |

### 层级关系

- 无 `parent_ui_action_id` → **页面根**（L0）。
- 有 parent → **页内或面板内操作**（L1/L2）。
- `hierarchical_page_selection.py` 按当前是否已 `navigate_ok` 决定暴露 navigate 还是 action 工具。

## 3. 后端：从 Catalog 到 LLM 工具

`operation_tools.py`：

```python
OPERATION_TOOL_PREFIX = "hap_op_"

def operation_tool_name(ui_action_id: str) -> str:
    safe = ui_action_id.replace(".", "_").replace("-", "_")
    return f"{OPERATION_TOOL_PREFIX}{safe}"
# dg.sources.create → hap_op_dg_sources_create
```

每轮 LLM 可见工具 = **MCP 子集** + **hap_op 层级子集**（非全量 1302）。

权限：`identity_allows_ui_action(identity, ui_action_id)` 过滤。

## 4. 前端：AgentActionRegistry

1. `import catalog from './platformOperationsCatalog.json'`
2. `buildPlatformAgentActions(catalog)` 生成默认 `AgentActionDefinition`
3. `BUTTON_ACTION_OVERRIDES` 覆盖复杂 selector（多候选、嵌套 input）

```typescript
export type AgentActionDefinition = {
  uiActionId: string;
  type: 'navigate' | 'highlight' | 'click' | 'fill' | 'scrollIntoView' | 'clearHighlight';
  selector?: string;  // 默认 [data-agent-action-id="..."]
  route?: string;
  label?: string;
  value?: string;     // fill 默认值
};
```

`AgentPageController.executeUiAction` 根据 definition 执行，并 emit 微步骤日志。

## 5. DOM 锚点规范

### 5.1 基本规则

```tsx
<Button data-agent-action-id="dg.sources.create">新建数据源</Button>
```

- `ui_action_id` 与 catalog **完全一致**。
- 一 id 多元素时，Registry 可写逗号 selector；Controller 会 `pickHighlightTarget` 收窄到可点击子节点。

### 5.2 输入框

```tsx
<Input data-agent-action-id="lineage.tableInput" />
// 或 Registry 指向内部 input：
// '[data-agent-action-id="lineage.tableInput"] input'
```

### 5.3 路由与动态 id

Catalog 中 `route: "/foo/:id"` 需要 params.id 时，LLM 工具参数或 clarify 收集 id；无 id 时 catalog 的 `_ROUTE_LIST_FALLBACKS` 回退列表页。

## 6. 演示与可观测

| 功能 | 实现 |
|------|------|
| 按钮高亮框 | `AgentPageController` outline / 四角标 |
| 演示慢速 | `agentDemoTiming.ts` 各阶段 pause |
| 执行日志 | `ExecutionLogPanel`，默认展开 |
| 微步骤 | `onMicroStep` → `[页面]` / `[高亮]` 等行 |

**刻意不做**虚拟光标；仅高亮目标控件。

## 7. 校验脚本

在**宿主 frontend 根目录**（含 `src/pages`）运行：

| 脚本 | 检查 |
|------|------|
| `verify-agent-registry.mjs` | Registry 与 catalog id 对齐 |
| `verify-agent-page-anchors.mjs` | 页面 DOM 锚点覆盖 registry |
| `verify-agent-executable.mjs` | 可执行性约束 |
| `audit-agent-page-coverage.mjs` | 模块覆盖率审计 |

Monorepo 内路径：`scripts/*.mjs`（从宿主 `frontend/` 调用 `node ../../scripts/...` 或复制到宿主 `scripts/`）。

## 8. 新增一个 ui_action 的检查清单

1. [ ] 在 `catalog/platform_operations_catalog.json` 增加条目（含 parent、route、risk、scopes）
2. [ ] `bash scripts/sync-catalog.sh`
3. [ ] 业务页添加 `data-agent-action-id`
4. [ ] 若 selector 特殊，在 `AgentActionRegistry.ts` 增加 override
5. [ ] 跑 verify 脚本
6. [ ] `pytest tests/test_ui_action_*.py`（后端权限/描述契约）

## 9. 与主平台的差距说明

| 已在 hap-agent | 仅在 HAP 主平台 |
|----------------|-----------------|
| 1302 条 catalog 定义 | 104 个页面 tsx 锚点 |
| Registry 832+ 映射 | QuickStartGuide 等 7 个共享组件锚点 |
| 后端层级选页逻辑 | `app.tsx` / `.umirc.ts` 集成 |

因此：**Agent 模块上传是完整的**；**整站 UI 自动化**需宿主页面配合，见 [ARCHITECTURE.md](./ARCHITECTURE.md) §4。
