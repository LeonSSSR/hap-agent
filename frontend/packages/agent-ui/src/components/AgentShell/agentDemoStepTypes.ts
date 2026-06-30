export type AgentMicroStepEvent = {
  phase: 'start' | 'complete';
  label: string;
  index: number;
  total: number;
};
