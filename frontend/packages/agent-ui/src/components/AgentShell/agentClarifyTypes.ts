export type AgentClarifyPending = {
  runId: string;
  toolCallId: string;
  question: string;
  resumeToken: string;
  fields?: string[];
  placeholder?: string;
  choices?: string[];
};

export type AgentClarifyResult = {
  answer: string;
  skipped: boolean;
};
