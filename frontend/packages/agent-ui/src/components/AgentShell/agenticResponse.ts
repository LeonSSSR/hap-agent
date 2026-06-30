import { pickAgentUnderstandingCopy } from '@/services/agent';
import { asRecord } from './agentUtils';

export function pickAgenticUnderstanding(response: unknown): string | null {
  const flat = asRecord(response);
  if (!flat) return null;
  const agentRun = flat.agentRun as { assistantText?: string } | undefined;
  const fromRun = String(agentRun?.assistantText || '').trim();
  if (fromRun) return fromRun;
  const copy = pickAgentUnderstandingCopy(flat);
  return copy || null;
}

export function pickAgenticReasoning(response: unknown): string | null {
  const flat = asRecord(response);
  if (!flat) return null;
  const agentRun = flat.agentRun as { reasoningText?: string } | undefined;
  const reasoning = String(agentRun?.reasoningText || flat.reasoning_text || '').trim();
  return reasoning || null;
}

export function pickAgenticTraceId(response: unknown): string | null {
  const flat = asRecord(response);
  if (!flat) return null;
  const agentRun = flat.agentRun as { traceId?: string } | undefined;
  const traceId = String(agentRun?.traceId || '').trim();
  return traceId || null;
}

export function pickAgenticRunId(response: unknown): string | null {
  const flat = asRecord(response);
  if (!flat) return null;
  const agentRun = flat.agentRun as { runId?: string } | undefined;
  const runId = String(agentRun?.runId || '').trim();
  return runId || null;
}
