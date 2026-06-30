/**
 * Agentic 预设：类型、localStorage、审计指令常量。
 * 场景文案与推荐逻辑见 agentPresetCatalog.ts。
 */

export type PresetAction = 'fill' | 'audit';

export type AgentQuickPreset = {
  id: string;
  label: string;
  prompt: string;
  group?: 'context' | 'global' | 'custom' | 'recent';
  action?: PresetAction;
  hint?: string;
};

export type HapPageContextLite = {
  moduleKey: string;
  pageName: string;
  pathname: string;
};

const CUSTOM_STORAGE_KEY = 'hap-agent-custom-presets';
const RECENT_STORAGE_KEY = 'hap-agent-recent-presets';
const MAX_CUSTOM_PRESETS = 16;
const MAX_RECENT_PRESETS = 8;

export const AUDIT_QUICK_COMMAND = '查看助手操作记录';

const HIDDEN_PRESET_LABELS = new Set(['操作记录查询', '查看助手操作记录']);

export function isHiddenAgentPreset(item: { label?: string; prompt?: string }): boolean {
  const label = String(item.label || '').trim();
  const prompt = String(item.prompt || '').trim();
  if (HIDDEN_PRESET_LABELS.has(label)) return true;
  if (prompt === AUDIT_QUICK_COMMAND) return true;
  return false;
}

export function labelFromPrompt(prompt: string, maxLen = 16): string {
  const t = prompt.trim();
  if (!t) return '未命名';
  return t.length > maxLen ? `${t.slice(0, maxLen)}…` : t;
}

export function loadCustomPresets(): AgentQuickPreset[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(CUSTOM_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((p) => p && typeof p.prompt === 'string' && p.prompt.trim())
      .map((p) => ({
        id: String(p.id || `cp-${Date.now()}`),
        label: String(p.label || labelFromPrompt(p.prompt)),
        prompt: String(p.prompt).trim(),
        group: 'custom' as const,
      }))
      .slice(0, MAX_CUSTOM_PRESETS);
  } catch {
    return [];
  }
}

export function saveCustomPresets(presets: AgentQuickPreset[]): void {
  if (typeof window === 'undefined') return;
  try {
    const payload = presets.slice(0, MAX_CUSTOM_PRESETS).map((p) => ({
      id: p.id,
      label: p.label,
      prompt: p.prompt,
    }));
    window.localStorage.setItem(CUSTOM_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    /* ignore */
  }
}

export function loadRecentPresets(): AgentQuickPreset[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(RECENT_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((p) => p && typeof p.prompt === 'string' && p.prompt.trim())
      .map((p) => ({
        id: String(p.id || `recent-${Date.now()}`),
        label: String(p.label || labelFromPrompt(p.prompt)),
        prompt: String(p.prompt).trim(),
        group: 'recent' as const,
        hint: p.hint,
      }))
      .slice(0, MAX_RECENT_PRESETS);
  } catch {
    return [];
  }
}

export function saveRecentPresets(presets: AgentQuickPreset[]): void {
  if (typeof window === 'undefined') return;
  try {
    const payload = presets.slice(0, MAX_RECENT_PRESETS).map((p) => ({
      id: p.id,
      label: p.label,
      prompt: p.prompt,
      hint: p.hint,
    }));
    window.localStorage.setItem(RECENT_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    /* ignore */
  }
}

export function pushRecentPreset(presets: AgentQuickPreset[], next: AgentQuickPreset): AgentQuickPreset[] {
  const key = next.prompt.trim();
  if (!key) return presets;
  const filtered = presets.filter((p) => p.prompt.trim() !== key);
  return [{ ...next, group: 'recent' }, ...filtered].slice(0, MAX_RECENT_PRESETS);
}

export function buildPlaceholder(ctx: HapPageContextLite): string {
  const page = ctx.pageName?.trim();
  if (page && page !== '工作台') {
    return `描述您在「${page}」想完成的事，发送后助手将查询或引导操作`;
  }
  return '用一句话描述需求，发送后助手将查询信息或打开页面引导操作';
}
