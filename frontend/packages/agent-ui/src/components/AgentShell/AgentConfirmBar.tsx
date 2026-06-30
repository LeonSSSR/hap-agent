import React, { memo } from 'react';
import { Alert, Button, Space } from 'antd';
import {
  agentConfirmDeniedHint,
  canConfirmAgenticTool,
} from './agentPermissions';
import { getOperationByUiActionId, isOperationTool } from './platformOperationsMap';
import type { AgentConfirmPending } from './agentConfirmTypes';

export type AgentConfirmBarProps = {
  pending: AgentConfirmPending | null;
  permissions?: string[];
  roles?: string[];
  onApprove: () => void;
  onReject: () => void;
  busy?: boolean;
};

function labelForPending(pending: AgentConfirmPending): string {
  if ((isOperationTool(pending.toolName) || pending.toolName === 'hap_ui_action') && pending.uiActionId) {
    return getOperationByUiActionId(pending.uiActionId)?.label || pending.uiActionId;
  }
  return pending.toolName;
}

export const AgentConfirmBar = memo(function AgentConfirmBar({
  pending,
  permissions = [],
  roles = [],
  onApprove,
  onReject,
  busy = false,
}: AgentConfirmBarProps) {
  if (!pending) return null;

  const allowed = canConfirmAgenticTool(pending.riskLevel, permissions, roles);
  const title = labelForPending(pending);
  const risk = pending.riskLevel === 'high' ? '高' : pending.riskLevel === 'medium' ? '中' : '低';

  return (
    <Alert
      showIcon
      type="warning"
      style={{ marginBottom: 12, borderRadius: 12 }}
      message={`待确认：${title}（${risk}风险）`}
      description={
        allowed
          ? 'Agent 请求执行上述操作。流式执行已暂停，请确认或拒绝后继续。'
          : agentConfirmDeniedHint(pending.riskLevel)
      }
      action={
        allowed ? (
          <Space direction="vertical" size={4}>
            <Button size="small" type="primary" loading={busy} onClick={onApprove}>
              确认继续
            </Button>
            <Button size="small" danger loading={busy} onClick={onReject}>
              拒绝
            </Button>
          </Space>
        ) : (
          <Button size="small" danger loading={busy} onClick={onReject}>
            拒绝
          </Button>
        )
      }
    />
  );
});
