import platformCatalog from './platformOperationsCatalog.json';

export type MlStepCatalogItem = {
  node_id: string;
  label: string;
  risk_level: string;
  requires_confirmation: boolean;
  ui_action_id?: string;
};

export type StepPreset = {
  id: string;
  label: string;
  stepIds: string[];
  prompt: string;
};

const STORAGE_KEY = 'hap-agent-step-presets';

const ML_MODULE_PREFIXES = ['ml.', 'dg.', 'dp.', 'md.', 'ma.'];

export const ML_STEP_CATALOG: MlStepCatalogItem[] = (platformCatalog.operations || [])
  .filter((op) => ML_MODULE_PREFIXES.some((prefix) => String(op.ui_action_id || '').startsWith(prefix)))
  .map((op) => ({
    node_id: String(op.ui_action_id),
    label: String(op.label || op.ui_action_id),
    risk_level: 'low',
    requires_confirmation: false,
    ui_action_id: String(op.ui_action_id),
  }));

export const ML_STEP_CATALOG_BY_ID = new Map(ML_STEP_CATALOG.map((item) => [item.node_id, item]));

export const PRIMARY_ML_STEPS = ML_STEP_CATALOG;

export const BUILTIN_STEP_PRESETS: StepPreset[] = [
  {
    id: 'builtin-data-train',
    label: '数据→训练',
    stepIds: ['ml.data.prepare', 'ml.training.submit'],
    prompt: buildStepPresetPrompt(['ml.data.prepare', 'ml.training.submit']),
  },
  {
    id: 'builtin-train-deploy',
    label: '训练→部署',
    stepIds: ['ml.training.submit', 'ml.model.register', 'ml.evaluation', 'ml.deploy'],
    prompt: buildStepPresetPrompt(['ml.training.submit', 'ml.model.register', 'ml.evaluation', 'ml.deploy']),
  },
];

export function buildStepPresetPrompt(stepIds: string[]): string {
  const labels = stepIds
    .map((id) => ML_STEP_CATALOG_BY_ID.get(id)?.label || id)
    .filter(Boolean);
  if (labels.length === 0) {
    return '请帮我处理当前平台任务，按需跳转页面并调用工具。';
  }
  const chain = labels.join(' → ');
  return `请按顺序协助我完成以下平台操作：${chain}。需要时自动跳转对应页面并逐步执行。`;
}

export function buildStepPresetLabel(stepIds: string[]): string {
  const labels = stepIds
    .map((id) => ML_STEP_CATALOG_BY_ID.get(id)?.label || id)
    .filter(Boolean);
  if (labels.length === 0) return '自定义步骤';
  if (labels.length === 1) return labels[0];
  if (labels.length === 2) return `${labels[0]}→${labels[1]}`;
  return `${labels[0]}→…→${labels[labels.length - 1]}`;
}

export function loadStepPresetsFromStorage(): StepPreset[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveStepPresetsToStorage(presets: StepPreset[]): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(presets));
  } catch {
    /* ignore */
  }
}

export function isPanelOnlyStep(nodeId: string): boolean {
  return false;
}
