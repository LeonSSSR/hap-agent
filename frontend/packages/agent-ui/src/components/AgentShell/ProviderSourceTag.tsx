import React from 'react';
import { Tag } from 'antd';
import {
  normalizeProviderSource,
  providerSourceLabel,
  providerSourceTagTone,
  shouldShowProviderSourceTag,
  resolveAgentResponseMeta,
  type AgentResponseMeta,
} from './agentUtils';
import { statusTagStyle } from './AgentPanelTheme';

export type ProviderSourceTagProps = {
  response?: unknown;
  source?: unknown;
  realExecution?: boolean | null;
  downgradedToMock?: boolean;
  compact?: boolean;
  meta?: AgentResponseMeta;
};

export const ProviderSourceTag: React.FC<ProviderSourceTagProps> = ({
  response,
  source,
  realExecution,
  downgradedToMock,
  compact,
  meta,
}) => {
  const resolvedMeta = meta ?? (response != null ? resolveAgentResponseMeta(response) : null);
  if (!resolvedMeta || !shouldShowProviderSourceTag(response, resolvedMeta)) {
    return null;
  }

  const normalized = normalizeProviderSource(source ?? resolvedMeta.source, realExecution ?? resolvedMeta.realExecution);
  if (normalized !== 'real' || downgradedToMock || resolvedMeta.downgradedToMock) {
    return null;
  }

  const label = providerSourceLabel(source ?? resolvedMeta.source, realExecution ?? resolvedMeta.realExecution);
  if (!label) return null;

  const tone = providerSourceTagTone(source ?? resolvedMeta.source, realExecution ?? resolvedMeta.realExecution);

  return (
    <Tag color={tone} style={{ margin: 0, ...(compact ? {} : statusTagStyle(tone)) }}>
      {compact ? label : `数据来源：${label}`}
    </Tag>
  );
};
