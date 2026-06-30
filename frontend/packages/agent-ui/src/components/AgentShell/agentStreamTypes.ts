export type AgentActivityStatus = 'running' | 'ok' | 'error' | 'blocked';

export type AgentActivity = {
  toolCallId: string;
  toolName: string;
  status: AgentActivityStatus;
  argumentsPreview?: Record<string, unknown>;
  resultPreview?: string;
  durationMs?: number;
  startedAt: number;
};

export type AgentRunStreamState = {
  runId: string | null;
  traceId: string | null;
  status: 'idle' | 'running' | 'done' | 'error' | 'stopped';
  assistantText: string;
  activities: AgentActivity[];
  error?: string;
};

export const initialAgentRunStreamState = (): AgentRunStreamState => ({
  runId: null,
  traceId: null,
  status: 'idle',
  assistantText: '',
  activities: [],
});
