import type { AgentRunStreamMessage } from '@/services/agent';

export const asRecord = (value: unknown): Record<string, unknown> | null => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
};

export const pickString = (...values: unknown[]): string => {
  for (const value of values) {
    if (value != null && value !== '') return String(value);
  }
  return '-';
};

export const pickNumber = (...values: unknown[]): number | undefined => {
  for (const value of values) {
    if (typeof value === 'number' && !Number.isNaN(value)) return value;
    if (typeof value === 'string' && value.trim() !== '' && !Number.isNaN(Number(value))) {
      return Number(value);
    }
  }
  return undefined;
};

export const hasText = (value: unknown) => {
  const text = String(value ?? '').trim();
  return text.length > 0 && text !== '-';
};

export const formatField = (value: unknown) => {
  if (value == null || value === '') return '-';
  return String(value);
};

export const formatResponse = (response: unknown) => {
  if (response == null) return '-';
  if (typeof response === 'string') return response;
  try {
    return JSON.stringify(response, null, 2);
  } catch {
    return String(response);
  }
};

export const formatSessionTime = (value?: string) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
};

export const executionModeLabel = (realExecution?: boolean) => {
  if (realExecution === false) return '只读';
  if (realExecution === true) return '真实执行';
  return '-';
};

export type AuditRecord = {
  audit_id?: string;
  action?: string;
  risk_level?: string | null;
  status?: string | null;
  summary?: string | null;
  skill_name?: string | null;
  trace_id?: string | null;
  timestamp?: string | null;
  real_execution?: boolean;
};

export const parseAuditItems = (res: unknown): AuditRecord[] => {
  const payload = res as { data?: { items?: unknown }; items?: unknown } | null;
  const items = payload?.data?.items ?? payload?.items;
  return Array.isArray(items) ? (items as AuditRecord[]) : [];
};

export const formatStreamLogLine = (msg: AgentRunStreamMessage) => {
  const parsed = msg.parsed as Record<string, unknown> | undefined;
  const detail =
    parsed?.message ||
    parsed?.status ||
    parsed?.tool_name ||
    (parsed?.run_id ? `run_id=${String(parsed.run_id)}` : '') ||
    msg.raw;
  const modeHint =
    parsed?.real_execution === true
      ? ' | 真实执行'
      : parsed?.real_execution === false && msg.event === 'tool_result'
        ? ' | 只读/模拟'
        : '';
  const time = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  return `[${time}] [${msg.event}] ${String(detail)}${modeHint}`;
};

export const softenUserFacingText = (text: string): string => {
  if (!text) return text;
  return text
    .replace(/mock\s*执行流/giu, '执行流')
    .replace(/\bmock\b/giu, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
};

export type AgentResponseMeta = {
  source?: string;
  realExecution?: boolean | null;
  providerPayload?: Record<string, unknown> | null;
};

export function resolveProviderPayload(response: unknown): Record<string, unknown> | null {
  const flat = asRecord(response);
  if (!flat) return null;
  return asRecord(flat.provider_payload) || asRecord(flat.result) || asRecord(flat.data) || null;
}

export function resolveAgentResponseMeta(response: unknown): AgentResponseMeta {
  const flat = asRecord(response);
  if (!flat) return {};
  const providerPayload = resolveProviderPayload(response);
  const source = pickString(flat.source, providerPayload?.source, '');
  return {
    source: source !== '-' ? source : undefined,
    realExecution: typeof flat.real_execution === 'boolean' ? flat.real_execution : undefined,
    providerPayload,
  };
}

export function normalizeProviderSource(source: unknown, realExecution?: boolean | null): string {
  if (realExecution === true) return 'real';
  if (realExecution === false) return 'mock';
  const normalized = String(source || '').trim().toLowerCase();
  return normalized || 'unknown';
}

export function providerSourceLabel(source: string): string {
  if (source === 'real') return '真实执行';
  if (source === 'mock') return '演示数据';
  return source || '未知来源';
}

export function providerSourceTagTone(source: string): 'success' | 'default' | 'warning' {
  if (source === 'real') return 'success';
  if (source === 'mock') return 'warning';
  return 'default';
}

export function shouldShowProviderSourceTag(_response: unknown, meta: AgentResponseMeta): boolean {
  return Boolean(meta.source || meta.realExecution != null);
}
