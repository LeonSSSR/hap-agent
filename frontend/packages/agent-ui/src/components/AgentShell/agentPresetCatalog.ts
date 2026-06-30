/**
 * 「预设与能力」面板文案与场景目录（用户可见内容，与 Agentic 能力对齐）。
 */

import type { AgentQuickPreset, HapPageContextLite } from './agentPresets';
import { buildPlaceholder } from './agentPresets';
import type { AgentCapabilitiesPayload, AgentHapOperation, AgentMcpTool } from './agentCapabilitiesView';
import { plainToolName } from './agentUserCopy';

export type PresetScenarioId = 'observe' | 'govern' | 'process' | 'develop' | 'deploy' | 'flows';

export type PresetScenario = {
  id: PresetScenarioId;
  title: string;
  description: string;
  presets: AgentQuickPreset[];
};

export const PRESET_PANEL_TAGLINE =
  '用一句话描述需求：助手会先说明思路，再查询信息或打开页面引导操作；写入类操作需您确认。';

export const FLOW_PRESET_COPY: Record<
  string,
  { title: string; description: string; stepsLabel: string }
> = {
  'builtin-data-train': {
    title: '数据准备到训练',
    description: '划分数据、提交训练并跟踪运行状态，适合从数据集开始建模。',
    stepsLabel: '3 步',
  },
  'builtin-train-deploy': {
    title: '训练到上线',
    description: '登记模型、完成评估与发布，并申请部署在线预测服务。',
    stepsLabel: '5 步',
  },
  'builtin-lifecycle-guide': {
    title: '全生命周期导览',
    description: '按治理→处理→开发→应用顺序列出页面与操作，先给计划再逐步引导。',
    stepsLabel: '9 步',
  },
};

/** 页面操作：用户可读摘要与填入指令 */
export const UI_ACTION_USER_COPY: Record<
  string,
  { summary: string; prompt: string }
> = {
  'dg.sources': {
    summary: '查看数据源列表与连接状态',
    prompt: '列出已接入的数据源及连接状态，标出异常项并给出处理建议。',
  },
  'dg.sources.create': {
    summary: '新建数据源连接',
    prompt: '引导我在数据源管理页新建一条数据源连接，并说明需要填写的关键参数。',
  },
  'dg.sync': {
    summary: '查看同步任务与最近执行',
    prompt: '查看数据同步任务列表与最近一次执行情况，说明失败原因（如有）。',
  },
  'ml.data.prepare': {
    summary: '管理数据集与版本',
    prompt: '列出可用于训练的数据集及版本，说明数据量与最近更新时间。',
  },
  'dg.schedule': {
    summary: '查看数据调度任务',
    prompt: '查看数据调度与定时任务列表，说明运行状态与下次执行时间。',
  },
  'dg.service': {
    summary: '数据服务发布与鉴权',
    prompt: '说明当前数据服务发布情况与鉴权配置，并引导我查看相关页面。',
  },
  'dp.labeling': {
    summary: '数据标注项目',
    prompt: '查看标注项目进度，或引导我创建新的标注任务。',
  },
  'dp.transform': {
    summary: '数据转换与清洗',
    prompt: '根据目标说明数据转换或清洗步骤，并引导打开对应处理页面。',
  },
  'dp.quality': {
    summary: '数据质量检查',
    prompt: '说明当前数据质量规则与检查结果，并给出改进建议。',
  },
  'ml.data.prepare.split': {
    summary: '划分训练/验证集',
    prompt: '帮我划分训练与验证数据集版本，说明参数选择与注意事项。',
  },
  'md.notebooks': {
    summary: 'Notebook 实验环境',
    prompt: '引导我打开 Notebook 工作区，说明如何开始一次实验。',
  },
  'ml.training.submit': {
    summary: '提交训练任务',
    prompt: '查看训练任务列表；如需新建，说明所需数据版本与训练配置。',
  },
  'md.pipelines.workspace': {
    summary: '流水线工作区',
    prompt: '打开流水线工作区，说明如何查看或编辑训练流水线。',
  },
  'ml.model.register': {
    summary: '登记模型版本',
    prompt: '将训练产物登记为可追踪的模型版本，说明需要确认的信息。',
  },
  'ml.evaluation': {
    summary: '模型评估',
    prompt: '查看模型评估结果，说明关键指标与是否达到发布标准。',
  },
  'ml.publish.confirm': {
    summary: '模型发布确认',
    prompt: '引导我完成模型发布前检查与确认流程，说明风险点。',
  },
  'ml.deploy': {
    summary: '部署在线预测服务',
    prompt: '为已发布模型申请部署在线预测服务，说明部署参数与健康检查方式。',
  },
  'ml.inference.test': {
    summary: '试跑在线预测',
    prompt: '对已部署服务发起一次试跑预测，并说明输入输出格式。',
  },
  'ma.service-monitor': {
    summary: '服务运行监控',
    prompt: '查看在线预测服务的运行指标与告警，说明是否需要处理。',
  },
  'lineage.unified': {
    summary: '统一血缘查询',
    prompt: '查询指定表或模型的血缘关系，分点说明上游来源与下游影响。',
  },
  'ops.health': {
    summary: '平台服务健康',
    prompt: '查询各平台服务运行状态与端口，用简洁列表说明。',
  },
};

const QUERY_TOOL_COPY: Record<string, { label: string; summary: string; prompt: string }> = {
  platform_service_inventory: {
    label: '服务健康',
    summary: '各服务是否在线、端口是否可用',
    prompt: '查询平台各服务健康状态与端口，用列表说明是否正常。',
  },
  platform_task_status: {
    label: '任务汇总',
    summary: '训练、同步等任务成功/失败/运行中',
    prompt: '汇总后台任务运行状态，说明成功、失败与运行中数量。',
  },
  platform_lineage_query: {
    label: '血缘关系',
    summary: '表或模型的上下游链路',
    prompt: '查询 customer_orders 表的血缘，说明上游来源与下游影响。',
  },
  platform_audit_query: {
    label: '操作记录',
    summary: '助手近期执行与确认记录',
    prompt: '查询助手近期操作与确认记录，按时间简要列出。',
  },
  dataset_catalog_query: {
    label: '数据集目录',
    summary: '可用数据集与版本概览',
    prompt: '列出平台数据集目录及版本信息，说明可用于训练的数据。',
  },
  training_job_status: {
    label: '训练任务状态',
    summary: '训练任务状态与进度',
    prompt: '列出当前训练任务及运行状态，标出失败任务。',
  },
  model_versions_list: {
    label: '模型版本列表',
    summary: '已登记模型版本',
    prompt: '列出已登记模型版本及最近更新时间。',
  },
  inference_services_list: {
    label: '推理服务列表',
    summary: '在线预测服务部署状态',
    prompt: '列出已部署在线预测服务及健康状态。',
  },
  service_monitor_query: {
    label: '服务监控',
    summary: '推理服务运行指标',
    prompt: '查询在线预测服务监控指标，说明是否有异常。',
  },
};

/** 场景化快捷指令（面板「按场景」区） */
export const SCENARIO_CATALOG: PresetScenario[] = [
  {
    id: 'observe',
    title: '查状态',
    description: '只读查询，不修改平台数据',
    presets: [
      {
        id: 'sc-observe-health',
        label: '服务健康',
        group: 'global',
        hint: '只读',
        prompt: '查询各平台服务运行状态与端口，用简洁列表说明是否正常。',
      },
      {
        id: 'sc-observe-tasks',
        label: '任务汇总',
        group: 'global',
        hint: '只读',
        prompt: '汇总训练、同步等任务的成功、失败与运行中数量。',
      },
      {
        id: 'sc-observe-lineage',
        label: '血缘影响',
        group: 'global',
        hint: '只读',
        prompt: '分析 customer_orders 表的血缘与下游影响范围。',
      },
    ],
  },
  {
    id: 'govern',
    title: '数据治理',
    description: '数据源、同步、质量与数据集',
    presets: [
      {
        id: 'sc-govern-sources',
        label: '数据源',
        group: 'context',
        hint: '打开页面',
        prompt: '列出已接入数据源及连接状态，标出异常并给出建议。',
      },
      {
        id: 'sc-govern-sync',
        label: '同步任务',
        group: 'context',
        hint: '打开页面',
        prompt: '查看数据同步任务列表与最近执行情况。',
      },
      {
        id: 'sc-govern-quality',
        label: '质量规则',
        group: 'context',
        hint: '执行前确认',
        prompt: '为当前数据集说明质量规则与数据变化提醒的配置建议。',
      },
    ],
  },
  {
    id: 'process',
    title: '数据处理',
    description: '标注、转换、切分与特征',
    presets: [
      {
        id: 'sc-process-label',
        label: '数据标注',
        group: 'context',
        hint: '打开页面',
        prompt: '查看标注项目进度，或引导我创建标注任务。',
      },
      {
        id: 'sc-process-transform',
        label: '转换清洗',
        group: 'context',
        hint: '打开页面',
        prompt: '说明数据转换或清洗步骤，并引导打开对应页面。',
      },
      {
        id: 'sc-process-split',
        label: '划分数据集',
        group: 'context',
        hint: '执行前确认',
        prompt: '帮我划分训练/验证数据集版本，说明参数与风险。',
      },
    ],
  },
  {
    id: 'develop',
    title: '模型开发',
    description: '实验、训练与模型登记',
    presets: [
      {
        id: 'sc-develop-train',
        label: '训练任务',
        group: 'context',
        hint: '打开页面',
        prompt: '查看训练任务列表与运行状态，必要时说明如何发起新训练。',
      },
      {
        id: 'sc-develop-notebook',
        label: 'Notebook',
        group: 'context',
        hint: '打开页面',
        prompt: '引导我打开 Notebook 并开始一次实验。',
      },
      {
        id: 'sc-develop-register',
        label: '登记模型',
        group: 'context',
        hint: '执行前确认',
        prompt: '将训练产物登记为模型版本，说明需确认的信息。',
      },
    ],
  },
  {
    id: 'deploy',
    title: '发布上线',
    description: '评估、发布、部署与推理',
    presets: [
      {
        id: 'sc-deploy-eval',
        label: '模型评估',
        group: 'context',
        hint: '打开页面',
        prompt: '查看模型评估结果，说明是否达到发布标准。',
      },
      {
        id: 'sc-deploy-publish',
        label: '发布模型',
        group: 'context',
        hint: '需您同意',
        prompt: '引导我完成模型发布前检查与确认。',
      },
      {
        id: 'sc-deploy-service',
        label: '部署服务',
        group: 'context',
        hint: '需您同意',
        prompt: '为已发布模型部署在线预测服务，说明部署与健康检查方式。',
      },
    ],
  },
];

const MODULE_SCENARIO_IDS: Record<string, PresetScenarioId[]> = {
  workspace: ['observe', 'govern', 'develop', 'deploy'],
  lineage: ['observe', 'govern'],
  data_governance: ['govern', 'observe'],
  data_processing: ['process', 'develop'],
  model_development: ['develop', 'process'],
  model_application: ['deploy', 'develop'],
  system_management: ['observe'],
  environment_management: ['observe'],
  unknown: ['observe', 'govern'],
};

const PATHNAME_RECOMMENDED: Array<{ pattern: RegExp; presetIds: string[] }> = [
  {
    pattern: /^\/data-governance\/sources\b/i,
    presetIds: ['sc-govern-sources', 'cap-dg-sources-test'],
  },
  {
    pattern: /^\/data-governance\/sync\b/i,
    presetIds: ['sc-govern-sync'],
  },
  {
    pattern: /^\/data-governance\/datasets\b/i,
    presetIds: ['sc-govern-quality', 'ml.data.prepare'],
  },
  {
    pattern: /^\/model-dev\/training\b/i,
    presetIds: ['sc-develop-train'],
  },
  {
    pattern: /^\/model-app\/service-deploy\b/i,
    presetIds: ['sc-deploy-service'],
  },
  {
    pattern: /^\/lineage\b/i,
    presetIds: ['sc-observe-lineage', 'lineage.unified'],
  },
];

/** 路由专属补充（catalog 中无对应 id 的） */
const PATH_EXTRA_PRESETS: Record<string, AgentQuickPreset> = {
  'cap-dg-sources-test': {
    id: 'cap-dg-sources-test',
    label: '测试连接',
    group: 'context',
    hint: '当前页面',
    prompt: '检查当前数据源连接是否正常，并给出修复建议。',
  },
};

export function describeUiAction(op: AgentHapOperation): { summary: string; prompt: string; label: string } {
  const copy = UI_ACTION_USER_COPY[op.ui_action_id];
  if (copy) {
    return { label: op.label, summary: copy.summary, prompt: copy.prompt };
  }
  const hints = (op.keywords || []).slice(0, 2).join('、');
  const summary = hints ? `${op.label}（${hints}）` : op.label;
  const prompt = hints
    ? `请帮我在「${op.label}」完成相关操作，例如：${hints}。`
    : `请帮我在「${op.label}」完成相关操作，并引导打开对应页面。`;
  return { label: op.label, summary, prompt };
}

export function describeQueryTool(tool: AgentMcpTool): { label: string; summary: string; prompt: string } {
  const copy = QUERY_TOOL_COPY[tool.tool_name];
  if (copy) return copy;
  const label = plainToolName(tool.tool_name);
  const desc = String(tool.description || '').trim();
  return {
    label,
    summary: desc.slice(0, 48) || '平台数据查询',
    prompt: desc
      ? `请查询：${desc.slice(0, 100)}，并用简洁中文说明结果。`
      : `请使用「${label}」查询相关信息，并用简洁中文说明结果。`,
  };
}

export function scenariosForModule(moduleKey: string): PresetScenario[] {
  const ids = MODULE_SCENARIO_IDS[moduleKey] || MODULE_SCENARIO_IDS.unknown;
  const flows: PresetScenario = {
    id: 'flows',
    title: '组合流程',
    description: '跨多个页面的连续任务，会先给计划再逐步引导',
    presets: [],
  };
  const picked = ids
    .map((id) => SCENARIO_CATALOG.find((s) => s.id === id))
    .filter((s): s is PresetScenario => Boolean(s));
  return [...picked, flows];
}

function findPresetById(id: string, operations: AgentHapOperation[]): AgentQuickPreset | null {
  const extra = PATH_EXTRA_PRESETS[id];
  if (extra) return extra;

  for (const scenario of SCENARIO_CATALOG) {
    const hit = scenario.presets.find((p) => p.id === id);
    if (hit) return hit;
  }

  const op = operations.find((o) => o.ui_action_id === id);
  if (op) {
    const d = describeUiAction(op);
    return {
      id: `cap-page-${op.ui_action_id}`,
      label: d.label,
      prompt: d.prompt,
      group: 'context',
      hint: d.summary,
    };
  }
  return null;
}

/** 顶部「推荐」：路由优先 + 当前模块场景，最多 4 条 */
export function buildRecommendedPresets(
  ctx: HapPageContextLite,
  operations: AgentHapOperation[],
): AgentQuickPreset[] {
  const pathname = ctx.pathname.split('?')[0];
  const result: AgentQuickPreset[] = [];
  const seen = new Set<string>();

  for (const rule of PATHNAME_RECOMMENDED) {
    if (!rule.pattern.test(pathname)) continue;
    for (const id of rule.presetIds) {
      const preset = findPresetById(id, operations);
      if (!preset || seen.has(preset.prompt)) continue;
      seen.add(preset.prompt);
      result.push(preset);
    }
  }

  const routeOps = operations.filter((op) => {
    const route = String(op.route || '').split('?')[0];
    return route && (pathname === route || pathname.startsWith(`${route}/`));
  });
  for (const op of routeOps.slice(0, 2)) {
    const d = describeUiAction(op);
    const preset: AgentQuickPreset = {
      id: `rec-${op.ui_action_id}`,
      label: d.label,
      prompt: d.prompt,
      group: 'context',
      hint: d.summary,
    };
    if (!seen.has(preset.prompt)) {
      seen.add(preset.prompt);
      result.push(preset);
    }
  }

  const scenarios = scenariosForModule(ctx.moduleKey);
  for (const scenario of scenarios) {
    if (scenario.id === 'flows') continue;
    for (const preset of scenario.presets) {
      if (result.length >= 4) return result;
      if (seen.has(preset.prompt)) continue;
      seen.add(preset.prompt);
      result.push(preset);
    }
  }

  if (result.length < 4) {
    const observe = SCENARIO_CATALOG.find((s) => s.id === 'observe');
    for (const preset of observe?.presets || []) {
      if (result.length >= 4) break;
      if (seen.has(preset.prompt)) continue;
      seen.add(preset.prompt);
      result.push(preset);
    }
  }

  return result.slice(0, 4);
}

export function buildInputPlaceholder(
  ctx: HapPageContextLite,
  _capabilities: AgentCapabilitiesPayload | null,
): string {
  return buildPlaceholder(ctx);
}

export function buildModeSummary(
  capabilities: {
    realExecution?: boolean;
    agent_model?: { model?: string; thinking_enabled?: boolean };
  } | null,
): string | null {
  if (!capabilities) return null;
  const parts: string[] = [];
  const model = capabilities.agent_model?.model;
  if (model) parts.push(String(model));
  if (capabilities.agent_model?.thinking_enabled) parts.push('思考模式');
  parts.push(capabilities.realExecution ? '正式执行' : '预览模式');
  return parts.join(' · ');
}
