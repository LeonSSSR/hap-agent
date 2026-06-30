/**
 * Agentic 能力目录：对接 GET /api/agent/capabilities，供预设与「我能做什么」面板使用。
 */

import type { AgentQuickPreset } from './agentPresets';
import type { HapPageContextLite } from './agentPresets';

export type AgentHapOperation = {
  ui_action_id: string;
  label: string;
  module: string;
  route?: string;
  action_type?: string;
  risk_level?: string;
  keywords?: string[];
};

export type AgentMcpTool = {
  tool_name: string;
  title?: string;
  description?: string;
  risk_level?: string;
  permission_scope?: string[];
};

export type AgentCapabilitiesPayload = {
  mode?: string;
  architecture?: string;
  realExecution?: boolean;
  agent_model?: {
    enabled?: boolean;
    provider?: string;
    model?: string;
    configured?: boolean;
    stream?: boolean;
    thinking_enabled?: boolean;
  };
  hap_operations?: AgentHapOperation[];
  allowed_ui_action_ids?: string[];
  mcp_tools?: AgentMcpTool[];
  platformApiMode?: string;
  features?: string[];
};

export type CapabilityViewTab = 'pages' | 'queries' | 'flows';

export const MODULE_LABELS: Record<string, string> = {
  data_governance: '数据治理',
  data_processing: '数据处理',
  model_development: '模型开发',
  model_application: '模型应用',
  lineage: '统一血缘',
  platform: '平台',
};

export const DOMAIN_LABELS: Record<string, string> = {
  data_governance: '数据治理',
  data_processing: '数据处理',
  model_development: '模型开发',
  model_application: '模型应用',
  platform: '平台查询',
  shared: '通用',
};

const QUERY_TOOL_NAMES = new Set([
  'platform_service_inventory',
  'platform_task_status',
  'platform_lineage_query',
  'platform_audit_query',
  'platform_mock_catalog',
  'service_monitor_query',
  'dataset_catalog_query',
  'training_job_status',
  'model_versions_list',
  'inference_services_list',
  'model_monitor_query',
  'model_evaluation_query',
]);

const RISK_ORDER: Record<string, number> = { low: 0, medium: 1, high: 2 };

export function riskLevelLabel(level?: string): string {
  const v = String(level || 'low').toLowerCase();
  if (v === 'high') return '需您同意';
  if (v === 'medium') return '执行前确认';
  return '仅查看';
}

export function promptFromHapOperation(op: AgentHapOperation): string {
  const hints = (op.keywords || []).slice(0, 3).join('、');
  const actionHint =
    op.action_type === 'navigate'
      ? '先打开对应页面'
      : op.action_type === 'click'
        ? '在对应页面引导我完成点击操作'
        : '在对应页面引导我完成相关操作';
  return hints
    ? `请帮我在「${op.label}」${actionHint}（例如：${hints}）。`
    : `请帮我在「${op.label}」${actionHint}。`;
}

export function promptFromMcpTool(tool: AgentMcpTool): string {
  const title = tool.title || tool.tool_name;
  const desc = String(tool.description || '').trim();
  if (desc) return `请使用「${title}」查询：${desc.slice(0, 120)}`;
  return `请使用「${title}」帮我查询相关信息，并用简洁中文说明结果。`;
}

export function hapOperationToPreset(op: AgentHapOperation): AgentQuickPreset {
  return {
    id: `cap-page-${op.ui_action_id}`,
    label: op.label,
    prompt: promptFromHapOperation(op),
    group: 'context',
    hint: `${MODULE_LABELS[op.module] || op.module} · ${riskLevelLabel(op.risk_level)}`,
  };
}

export function mcpToolToPreset(tool: AgentMcpTool): AgentQuickPreset {
  const label = tool.title || tool.tool_name;
  return {
    id: `cap-query-${tool.tool_name}`,
    label,
    prompt: promptFromMcpTool(tool),
    group: 'global',
    hint: riskLevelLabel(tool.risk_level),
  };
}

export function matchOperationToContext(op: AgentHapOperation, ctx: HapPageContextLite): boolean {
  const route = String(op.route || '').split('?')[0];
  const pathname = ctx.pathname.split('?')[0];
  if (route && pathname && (pathname === route || pathname.startsWith(`${route}/`))) {
    return true;
  }
  const moduleMap: Record<string, string> = {
    lineage: 'lineage',
    data_governance: 'data_governance',
    data_processing: 'data_processing',
    model_development: 'model_development',
    model_application: 'model_application',
    workspace: 'platform',
    system_management: 'platform',
    environment_management: 'platform',
  };
  const targetModule = moduleMap[ctx.moduleKey];
  return Boolean(targetModule && op.module === targetModule);
}

export function buildContextPresetsFromCapabilities(
  operations: AgentHapOperation[],
  ctx: HapPageContextLite,
  limit = 6,
): AgentQuickPreset[] {
  const matched = operations.filter((op) => matchOperationToContext(op, ctx));
  const sorted = [...matched].sort((a, b) => {
    const routeA = a.route && ctx.pathname.startsWith(a.route) ? 0 : 1;
    const routeB = b.route && ctx.pathname.startsWith(b.route) ? 0 : 1;
    if (routeA !== routeB) return routeA - routeB;
    return (RISK_ORDER[a.risk_level || 'low'] ?? 9) - (RISK_ORDER[b.risk_level || 'low'] ?? 9);
  });
  return sorted.slice(0, limit).map(hapOperationToPreset);
}

export function groupOperationsByModuleAndPage(
  operations: AgentHapOperation[],
  query: string,
): Array<{ module: string; label: string; items: AgentHapOperation[] }> {
  const q = query.trim().toLowerCase();
  const filtered = q
    ? operations.filter((op) => {
        const haystack = [
          op.label,
          op.ui_action_id,
          op.route,
          ...(op.keywords || []),
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        return haystack.includes(q);
      })
    : operations;
  return groupOperationsByModule(filtered);
}

export function groupOperationsByModule(
  operations: AgentHapOperation[],
): Array<{ module: string; label: string; items: AgentHapOperation[] }> {
  const groups = new Map<string, AgentHapOperation[]>();
  for (const op of operations) {
    const key = op.module || 'platform';
    const list = groups.get(key) || [];
    list.push(op);
    groups.set(key, list);
  }
  const order = ['lineage', 'data_governance', 'data_processing', 'model_development', 'model_application', 'platform'];
  return order
    .filter((key) => groups.has(key))
    .map((key) => ({
      module: key,
      label: MODULE_LABELS[key] || key,
      items: (groups.get(key) || []).sort((a, b) => a.label.localeCompare(b.label, 'zh-CN')),
    }));
}

export function filterQueryTools(tools: AgentMcpTool[]): AgentMcpTool[] {
  return tools.filter((tool) => {
    const risk = String(tool.risk_level || 'low').toLowerCase();
    if (risk !== 'low') return false;
    const name = tool.tool_name;
    if (QUERY_TOOL_NAMES.has(name)) return true;
    return /query|list|status|inventory|catalog|monitor/i.test(name);
  });
}

export function groupQueryToolsByDomain(
  tools: AgentMcpTool[],
): Array<{ domain: string; label: string; items: AgentMcpTool[] }> {
  const groups = new Map<string, AgentMcpTool[]>();
  for (const tool of tools) {
    const domain = inferToolDomain(tool.tool_name);
    const list = groups.get(domain) || [];
    list.push(tool);
    groups.set(domain, list);
  }
  const order = ['platform', 'data_governance', 'data_processing', 'model_development', 'model_application', 'shared'];
  return order
    .filter((key) => groups.has(key))
    .map((key) => ({
      domain: key,
      label: DOMAIN_LABELS[key] || key,
      items: (groups.get(key) || []).sort((a, b) =>
        String(a.title || a.tool_name).localeCompare(String(b.title || b.tool_name), 'zh-CN'),
      ),
    }));
}

function inferToolDomain(toolName: string): string {
  if (toolName.startsWith('platform_') || toolName === 'service_monitor_query') return 'platform';
  if (/datasource|dataset|drift|quality|sync|governance|lineage/i.test(toolName)) return 'data_governance';
  if (/label|transform|split|augment|feature|clean/i.test(toolName)) return 'data_processing';
  if (/training|notebook|pipeline|katib|algorithm/i.test(toolName)) return 'model_development';
  if (/model|inference|deploy|publish/i.test(toolName)) return 'model_application';
  return 'shared';
}

export function filterCapabilityItems<T extends { label?: string; prompt?: string }>(
  items: T[],
  query: string,
): T[] {
  const q = query.trim().toLowerCase();
  if (!q) return items;
  return items.filter((item) => {
    const label = String((item as { label?: string }).label || '').toLowerCase();
    const prompt = String(item.prompt || '').toLowerCase();
    return label.includes(q) || prompt.includes(q);
  });
}
