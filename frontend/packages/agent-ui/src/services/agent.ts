import request from '@/utils/request';
import { getToken } from '@/utils/auth';

export type AgentSessionMessage = {
  messageId?: string;
  message_id?: string;
  role: string;
  content: string;
  metadata?: Record<string, unknown>;
};

export type AgentSession = {
  sessionId: string;
  session_id?: string;
  title?: string;
  summary?: string;
  messages?: AgentSessionMessage[];
  message_count?: number;
};

export type AgentSessionListItem = {
  sessionId: string;
  session_id?: string;
  title?: string;
  summary?: string;
  updated_at?: string;
  message_count?: number;
};

export type AgentRunStreamMessage = {
  event: string;
  raw: string;
  parsed: Record<string, unknown> | null;
};

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : null;

export const flattenAgentEnvelope = (response: unknown): Record<string, unknown> | null => {
  const record = asRecord(response);
  if (!record) return null;
  const nested = asRecord(record.data);
  if (nested && typeof record.code === 'number') {
    return { ...record, ...nested };
  }
  return record;
};

async function parseSseResponse(
  response: Response,
  onMessage: (message: AgentRunStreamMessage) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (!response.body) {
    throw new Error('SSE body missing');
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    if (signal?.aborted) return;
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() || '';
    for (const block of blocks) {
      const trimmed = block.trim();
      if (!trimmed) continue;
      let eventName = 'message';
      let dataLine = '';
      for (const line of trimmed.split('\n')) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim();
        if (line.startsWith('data:')) dataLine = line.slice(5).trim();
      }
      let parsed: Record<string, unknown> | null = null;
      if (dataLine) {
        try {
          parsed = JSON.parse(dataLine) as Record<string, unknown>;
        } catch {
          parsed = { raw: dataLine };
        }
      }
      onMessage({ event: eventName, raw: trimmed, parsed });
    }
  }
}

export async function runAgentStream(
  body: { message: string; session_id?: string | null; options?: Record<string, unknown> },
  onMessage: (message: AgentRunStreamMessage) => void,
  onDone: () => void,
  onError: (error: Error) => void,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const token = getToken();
    const response = await fetch('/api/agent/run/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      credentials: 'include',
      body: JSON.stringify(body),
      signal,
    });
    if (!response.ok) {
      throw new Error(`run/stream HTTP ${response.status}`);
    }
    await parseSseResponse(response, onMessage, signal);
    onDone();
  } catch (error) {
    if (
      (error instanceof DOMException && error.name === 'AbortError')
      || (error instanceof Error && error.name === 'AbortError')
      || signal?.aborted
    ) {
      onDone();
      return;
    }
    onError(error instanceof Error ? error : new Error(String(error)));
  }
}

function extractRequestErrorMessage(error: unknown, fallback: string): string {
  const err = error as {
    response?: { status?: number; data?: { detail?: unknown; message?: unknown } };
    message?: string;
  };
  const data = err?.response?.data;
  const detail = data?.detail ?? data?.message;
  if (typeof detail === 'string' && detail.trim()) return detail.trim();
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string } | string;
    if (typeof first === 'string' && first.trim()) return first.trim();
    if (typeof first === 'object' && first?.msg) return String(first.msg);
  }
  if (err?.response?.status === 404) return '会话已结束或已过期，页面操作结果未能回传';
  if (err?.response?.status === 403) return '无权回传页面操作结果（会话身份不一致）';
  return String(err?.message || fallback);
}

function extractClarifyErrorMessage(error: unknown, fallback: string): string {
  const msg = extractRequestErrorMessage(error, fallback);
  if (msg.includes('run access denied') || msg.includes('会话身份不一致')) {
    return '补充信息提交失败：当前登录身份与执行任务不一致，请刷新页面后重新发起对话';
  }
  if (msg.includes('not waiting') || msg.includes('已过期')) {
    return '补充信息提交失败：会话已结束或已过期，请重新发起对话';
  }
  return msg;
}

export async function postAgentPageResult(
  runId: string,
  body: {
    tool_call_id: string;
    ui_action_id: string;
    success?: boolean;
    message?: string;
    detail?: Record<string, unknown>;
  },
): Promise<void> {
  let res: unknown;
  try {
    res = await request<unknown>(`/api/agent/run/${runId}/page-result`, {
      method: 'POST',
      data: body,
      skipErrorHandler: true,
    });
  } catch (error: unknown) {
    throw new Error(extractRequestErrorMessage(error, '页面操作结果回传失败（会话可能已过期）'));
  }
  const flat = flattenAgentEnvelope(res);
  const code =
    typeof (res as { code?: number })?.code === 'number'
      ? (res as { code: number }).code
      : typeof flat?.code === 'number'
        ? (flat.code as number)
        : 0;
  if (code !== 0) {
    const msg = String(
      (res as { message?: string })?.message || flat?.message || '页面操作结果回传失败（会话可能已过期）',
    );
    throw new Error(msg);
  }
}

export async function postAgentRunConfirm(
  runId: string,
  body: { resume_token: string; decision: 'approve' | 'reject'; approved_by?: string },
): Promise<void> {
  await request(`/api/agent/run/${runId}/confirm`, { method: 'POST', data: body });
}

export async function postAgentRunClarify(
  runId: string,
  body: { resume_token: string; answer?: string; skipped?: boolean },
): Promise<void> {
  let res: unknown;
  try {
    res = await request<unknown>(`/api/agent/run/${runId}/clarify`, {
      method: 'POST',
      data: body,
      skipErrorHandler: true,
    });
  } catch (error: unknown) {
    throw new Error(extractClarifyErrorMessage(error, '补充信息提交失败（会话可能已过期）'));
  }
  const flat = flattenAgentEnvelope(res);
  const code =
    typeof (res as { code?: number })?.code === 'number'
      ? (res as { code: number }).code
      : typeof flat?.code === 'number'
        ? (flat.code as number)
        : 0;
  if (code !== 0) {
    const msg = String(
      (res as { message?: string })?.message || flat?.message || '补充信息提交失败（会话可能已过期）',
    );
    throw new Error(extractClarifyErrorMessage(new Error(msg), msg));
  }
}

export async function createSession(): Promise<AgentSession> {
  const res = await request<unknown>('/api/agent/sessions', {
    method: 'POST',
    skipErrorHandler: true,
  });
  const flat = flattenAgentEnvelope(res);
  const sessionId = String(flat?.sessionId || flat?.session_id || '');
  return { sessionId, ...(flat || {}) } as AgentSession;
}

export async function getSession(sessionId: string): Promise<AgentSession | null> {
  const res = await request<unknown>(`/api/agent/sessions/${sessionId}`, {
    skipErrorHandler: true,
  });
  const flat = flattenAgentEnvelope(res);
  if (!flat) return null;
  return {
    sessionId: String(flat.sessionId || flat.session_id || sessionId),
    ...flat,
  } as AgentSession;
}

export type AgentSessionTurnPayload = {
  userMessage: string;
  assistantReply?: string;
  chatResponse?: Record<string, unknown>;
};

export async function saveAgentSession(
  sessionId: string,
  body: { title?: string; turns: AgentSessionTurnPayload[] },
): Promise<void> {
  const res = await request<unknown>(`/api/agent/sessions/${sessionId}`, {
    method: 'PUT',
    data: body,
    skipErrorHandler: true,
  });
  const flat = flattenAgentEnvelope(res);
  const code =
    typeof (res as { code?: number })?.code === 'number'
      ? (res as { code: number }).code
      : typeof flat?.code === 'number'
        ? (flat.code as number)
        : 0;
  if (code !== 0) {
    throw new Error(String((res as { message?: string })?.message || flat?.message || '保存会话失败'));
  }
}

export async function deleteAgentSession(sessionId: string): Promise<void> {
  const res = await request<unknown>(`/api/agent/sessions/${sessionId}`, {
    method: 'DELETE',
    skipErrorHandler: true,
  });
  const flat = flattenAgentEnvelope(res);
  const code =
    typeof (res as { code?: number })?.code === 'number'
      ? (res as { code: number }).code
      : typeof flat?.code === 'number'
        ? (flat.code as number)
        : 0;
  if (code !== 0) {
    throw new Error(String((res as { message?: string })?.message || flat?.message || '删除会话失败'));
  }
}

export async function listSessions(limit = 20, offset = 0): Promise<{ items: AgentSessionListItem[] }> {
  const res = await request<unknown>('/api/agent/sessions', {
    method: 'GET',
    params: { limit, offset },
    skipErrorHandler: true,
  });
  const flat = flattenAgentEnvelope(res);
  const items = Array.isArray(flat?.items) ? (flat.items as AgentSessionListItem[]) : [];
  return { items };
}

export async function getCapabilities(): Promise<Record<string, unknown>> {
  const res = await request<unknown>('/api/agent/capabilities', { skipErrorHandler: true });
  return flattenAgentEnvelope(res) || {};
}

export function isRequestTimeoutError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error || '');
  return /timeout|timed out|ETIMEDOUT/i.test(message);
}

export function formatAgentRequestError(error: unknown): string {
  if (isRequestTimeoutError(error)) {
    return '请求超时，大模型响应较慢，请稍后重试或简化指令。';
  }
  if (error instanceof Error && error.message) return error.message;
  return '请求失败，请稍后重试。';
}

export function pickAgentUnderstandingCopy(payload: Record<string, unknown> | null): string {
  if (!payload) return '';
  return String(
    payload.understanding
      || payload.summary
      || payload.reply
      || (payload.agentRun as Record<string, unknown> | undefined)?.assistantText
      || '',
  ).trim();
}

export async function listAudits(limit = 20): Promise<unknown> {
  const res = await request<unknown>('/api/agent/audits', { params: { limit } });
  return flattenAgentEnvelope(res);
}

export async function getAuditTrace(traceId: string, limit = 50): Promise<unknown> {
  const res = await request<unknown>(`/api/agent/audits/trace/${traceId}`, { params: { limit } });
  return flattenAgentEnvelope(res);
}

export async function getTraceByTraceId(traceId: string, limit = 50): Promise<unknown> {
  const res = await request<unknown>(`/api/agent/traces/${traceId}`, { params: { limit } });
  return flattenAgentEnvelope(res);
}

export async function triggerTraceCompensation(traceId: string, body?: Record<string, unknown>): Promise<unknown> {
  const res = await request<unknown>(`/api/agent/traces/${traceId}/compensate`, { method: 'POST', data: body || {} });
  return flattenAgentEnvelope(res);
}

