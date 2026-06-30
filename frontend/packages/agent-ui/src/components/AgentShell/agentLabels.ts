export const riskLevelLabel = (riskLevel?: string | null) => {
  if (!riskLevel) {
    return { text: '未标记', color: 'default' as const };
  }
  const normalized = riskLevel.toLowerCase();
  if (normalized === 'low') return { text: '低风险', color: 'success' as const };
  if (normalized === 'medium') return { text: '中风险', color: 'warning' as const };
  if (normalized === 'high') return { text: '高风险', color: 'error' as const };
  return { text: riskLevel, color: 'default' as const };
};

export const riskApprovalHint = (riskLevel?: string | null) => {
  const normalized = riskLevel?.toLowerCase();
  if (normalized === 'medium') {
    return {
      text: '中风险，需要执行前确认',
      alertType: 'warning' as const,
      border: '1px solid rgba(245, 158, 11, 0.45)',
      background: 'rgba(120, 53, 15, 0.35)',
      color: '#fcd34d',
    };
  }
  if (normalized === 'high') {
    return {
      text: '高风险，需要人工确认与权限校验',
      alertType: 'error' as const,
      border: '1px solid rgba(239, 68, 68, 0.55)',
      background: 'rgba(127, 29, 29, 0.4)',
      color: '#991b1b',
    };
  }
  return {
    text: '低风险',
    alertType: 'success' as const,
    border: '1px solid rgba(34, 197, 94, 0.35)',
    background: 'rgba(20, 83, 45, 0.25)',
    color: '#bbf7d0',
  };
};

export const traceTypeTone = (eventType?: string | null): 'success' | 'error' | 'default' => {
  const normalized = String(eventType || '').toLowerCase();
  if (['tool_execution', 'workflow_state', 'workflow_runtime'].includes(normalized)) return 'success';
  if (['plan_rejected', 'error', 'failed'].includes(normalized)) return 'error';
  return 'default';
};
