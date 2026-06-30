export type AgentConfirmDecision = 'approve' | 'reject';

export type AgentConfirmPending = {
  runId: string;
  toolCallId: string;
  toolName: string;
  riskLevel: string;
  resumeToken: string;
  uiActionId?: string;
};
