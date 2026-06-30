import type { AgentActionDefinition } from './AgentActionRegistry';
import catalog from './platformOperationsCatalog.json';

export type PlatformModuleKey =
  | 'data_governance'
  | 'data_processing'
  | 'model_development'
  | 'model_application'
  | 'lineage'
  | 'platform'
  | 'project_operations'
  | 'project_development';

export type PlatformOperation = {
  ui_action_id: string;
  module: PlatformModuleKey | string;
  label: string;
  route: string;
  keywords: string[];
  parent_ui_action_id?: string;
  action_type?: string;
  agent_description?: string;
};

function isPageRootOperation(op: PlatformOperation): boolean {
  return !String(op.parent_ui_action_id || '').trim();
}

export const PLATFORM_OPERATIONS: PlatformOperation[] = (catalog.operations || []) as PlatformOperation[];

const byUiActionId = new Map(PLATFORM_OPERATIONS.map((op) => [op.ui_action_id, op]));

const byRoutePath = new Map<string, PlatformOperation>();
for (const op of PLATFORM_OPERATIONS) {
  if (!isPageRootOperation(op)) continue;
  const path = op.route.split('?')[0];
  if (!byRoutePath.has(path)) {
    byRoutePath.set(path, op);
  }
}

/** ML 生命周期已有路由（与 catalog 合并，catalog 优先补全） */
const ML_LIFECYCLE_ROUTE_FALLBACK: Record<string, string> = {
  'ml.training.monitor': '/model-dev/training',
};

export function buildPlatformUiActionRoutes(): Record<string, string> {
  const routes: Record<string, string> = { ...ML_LIFECYCLE_ROUTE_FALLBACK };
  for (const op of PLATFORM_OPERATIONS) {
    if (op.route) routes[op.ui_action_id] = op.route;
  }
  return routes;
}

export const PLATFORM_UI_ACTION_ROUTES = buildPlatformUiActionRoutes();

export function getOperationByUiActionId(uiActionId?: string | null): PlatformOperation | undefined {
  if (!uiActionId) return undefined;
  return byUiActionId.get(uiActionId);
}

export function operationToolName(uiActionId: string): string {
  return `hap_op_${uiActionId.replace(/\./g, '_').replace(/-/g, '_')}`;
}

const byOperationToolName = new Map(
  PLATFORM_OPERATIONS.map((op) => [operationToolName(op.ui_action_id), op.ui_action_id]),
);

export function uiActionIdFromOperationTool(toolName?: string | null): string | undefined {
  if (!toolName) return undefined;
  return byOperationToolName.get(toolName);
}

export function isOperationTool(toolName?: string | null): boolean {
  return Boolean(toolName && toolName.startsWith('hap_op_'));
}

function scoreRouteMatch(pathname: string, route: string): number {
  const normalized = pathname.split('?')[0];
  const base = route.split('?')[0];
  if (normalized === base) return base.length;
  if (!base.includes(':') && normalized.startsWith(`${base}/`)) return base.length;
  const pathParts = normalized.split('/').filter(Boolean);
  const routeParts = base.split('/').filter(Boolean);
  if (pathParts.length !== routeParts.length) return 0;
  for (let i = 0; i < routeParts.length; i++) {
    const segment = routeParts[i];
    if (segment.startsWith(':')) continue;
    if (segment !== pathParts[i]) return 0;
  }
  return base.length;
}

export function resolveOperationByPathname(pathname: string): PlatformOperation | undefined {
  const normalized = pathname.split('?')[0];
  const exact = byRoutePath.get(normalized);
  if (exact) return exact;
  let best: PlatformOperation | undefined;
  let bestLen = 0;
  for (const op of PLATFORM_OPERATIONS) {
    if (!isPageRootOperation(op)) continue;
    const score = scoreRouteMatch(normalized, op.route);
    if (score > bestLen) {
      best = op;
      bestLen = score;
    }
  }
  return best;
}

export function getOperationsForModule(module: PlatformModuleKey | string): PlatformOperation[] {
  return PLATFORM_OPERATIONS.filter((op) => op.module === module);
}

export function resolveOperationFromUserText(
  text: string,
  moduleHint?: PlatformModuleKey | string,
): PlatformOperation | undefined {
  const haystack = text.toLowerCase();
  let best: PlatformOperation | undefined;
  let bestScore = 0;
  for (const op of PLATFORM_OPERATIONS) {
    if (moduleHint && op.module !== moduleHint) continue;
    for (const kw of op.keywords) {
      const k = kw.toLowerCase();
      if (!k || !haystack.includes(k)) continue;
      const score = k.length + (op.label.length > 2 && haystack.includes(op.label.toLowerCase()) ? 20 : 0);
      if (score > bestScore) {
        bestScore = score;
        best = op;
      }
    }
    if (haystack.includes(op.label.toLowerCase()) && (op.label.length + 10) > bestScore) {
      bestScore = op.label.length + 10;
      best = op;
    }
  }
  if (best) return best;
  if (!moduleHint) return undefined;
  return PLATFORM_OPERATIONS.find((op) => op.module === moduleHint);
}

export function buildPlatformAgentActions(): Record<string, AgentActionDefinition> {
  const actions: Record<string, AgentActionDefinition> = {};
  for (const op of PLATFORM_OPERATIONS) {
    const selector = `[data-agent-action-id="${op.ui_action_id}"], [data-agent-page-root="${op.ui_action_id}"]`;
    actions[op.ui_action_id] = {
      uiActionId: op.ui_action_id,
      type: 'highlight',
      selector,
      route: op.route,
      label: op.label,
      description: `在「${op.label}」页面高亮主操作区；写入类操作由 MCP 执行，页面仅引导不自动提交。`,
    };
    actions[`${op.ui_action_id}.open`] = {
      uiActionId: `${op.ui_action_id}.open`,
      type: 'navigate',
      route: op.route,
      label: `打开${op.label}`,
      description: `跳转到 ${op.route}`,
    };
  }
  return actions;
}

export const ROUTE_PAGE_LABELS: Record<string, string> = Object.fromEntries(
  PLATFORM_OPERATIONS.map((op) => {
    const path = op.route.split('?')[0];
    const moduleLabel =
      op.module === 'data_governance'
        ? '数据治理'
        : op.module === 'data_processing'
          ? '数据处理'
          : op.module === 'model_development'
            ? '模型开发'
            : op.module === 'model_application'
              ? '模型应用'
              : op.module === 'lineage'
                ? '统一血缘'
                : op.module === 'platform'
                  ? '平台'
                  : op.module === 'project_operations'
                    ? '项目运维'
                    : op.module === 'project_development'
                      ? '项目开发'
                      : '平台';
    return [path, `${moduleLabel} · ${op.label}`];
  }),
);
