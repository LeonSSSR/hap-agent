/** Agent 面板用户可见文案：通俗说法，避免 MCP / Workflow / Skill 等术语。 */

const REPLACEMENTS: Array<[RegExp, string]> = [
  [/append-only/giu, '只新增、不覆盖'],
  [/append_only/giu, '只新增、不覆盖'],
  [/controlled_mock/giu, '演示模式'],
  [/controlled_real/giu, '正式执行'],
  [/real_execution/giu, '正式执行'],
  [/write_gated/giu, '需批准后才写入'],
  [/plan_rejected/giu, '计划已拒绝'],
  [/MCP\s*工具/giu, '后台操作'],
  [/调用\s*MCP/giu, '后台执行'],
  [/\bMCP\b/giu, '后台'],
  [/\bWorkflow\b/giu, '执行流程'],
  [/\bworkflow\b/giu, '执行流程'],
  [/\bSkill\b/giu, '能力'],
  [/\bskill\b/giu, '能力'],
  [/\bHermes\b/giu, '智能规划'],
  [/\bSSE\b/giu, '实时进度'],
  [/\bExecutor\b/giu, '执行器'],
  [/\bAgent\b/giu, '助手'],
  [/沙箱执行/giu, '安全演示'],
  [/编排/giu, '安排'],
  [/审计留痕/giu, '操作记录'],
  [/漂移监控/giu, '数据变化提醒'],
  [/推理服务/giu, '在线预测服务'],
  [/ML\s*生命周期/giu, '模型全流程'],
  [/最小闭环/giu, '一条龙'],
  [/端到端/giu, '从头到尾'],
  [/P9\b/giu, ''],
  [/ui_action_id/giu, '页面定位'],
  [/page_button_ids/giu, '页面按钮'],
  [/Topic/giu, '主题'],
  [/Partition/giu, '分区'],
  [/Offset/giu, '位置'],
  [/Trace/giu, '追踪编号'],
  [/mock\b/giu, '演示'],
  [/\bmock\b/giu, '演示'],
];

export const ACCESS_LABEL_PLAIN: Record<string, string> = {
  只读: '仅查看',
  审计: '可查记录',
  需确认: '执行前要您确认',
  需审批: '需您同意',
  追加写: '会新增数据',
  全流程: '完整流程',
  页面联动: '会打开对应页面',
  MCP: '后台代为提交',
};

export const TOOL_NAME_PLAIN: Record<string, string> = {
  data_quality_rule_create: '新建质量规则',
  data_quality_check_run: '运行质量检查',
  drift_monitor_create: '新建变化提醒',
  dataset_version_create: '划分数据集版本',
  training_job_create: '创建训练任务',
  model_version_register: '登记模型版本',
  online_inference_invoke: '试跑在线预测',
  model_publish_request: '申请发布模型',
  inference_service_deploy: '申请部署服务',
};

export function plainAccessLabel(label: string): string {
  const trimmed = label.trim();
  return ACCESS_LABEL_PLAIN[trimmed] || trimmed;
}

export function plainToolName(toolName?: string | null): string {
  const key = String(toolName || '').trim();
  if (!key) return '未指定';
  return TOOL_NAME_PLAIN[key] || key.replace(/_/g, ' ');
}

export function simplifyAgentText(text: string): string {
  if (!text) return text;
  let result = text;
  for (const [pattern, replacement] of REPLACEMENTS) {
    result = result.replace(pattern, replacement);
  }
  return result.replace(/\s{2,}/g, ' ').trim();
}

/** @deprecated 使用 simplifyAgentText；保留别名供既有 import。 */
export const softenUserFacingText = simplifyAgentText;
