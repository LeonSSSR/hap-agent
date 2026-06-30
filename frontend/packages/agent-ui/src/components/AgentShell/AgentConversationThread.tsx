import { DownOutlined, RightOutlined } from '@ant-design/icons';
import { Tooltip, Typography } from 'antd';
import React from 'react';
import { agentTurnBubbleStyle, HAP_AGENT_THEME } from './AgentPanelTheme';

const { Text, Paragraph } = Typography;

export type AgentConversationTurn = {
  id: string;
  userMessage: string;
  response: Record<string, unknown> | null;
  error: string;
  status: 'loading' | 'done' | 'error';
  collapsed: boolean;
};

export function createConversationTurnId(): string {
  return `turn-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function summarizeConversationTurn(
  turn: AgentConversationTurn,
  soften?: (text: string) => string,
): string {
  const user = (soften ? soften(turn.userMessage) : turn.userMessage).trim();
  return user || '未命名对话';
}

export function TurnMessageBubble({
  role,
  children,
}: {
  role: 'user' | 'assistant';
  children: React.ReactNode;
}) {
  return (
    <div className={`hap-agent-turn-bubble hap-agent-turn-bubble--${role}`} style={agentTurnBubbleStyle(role)}>
      {children}
    </div>
  );
}

const recallIcon = (
  <svg
    viewBox="0 0 24 24"
    width="15"
    height="15"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden
  >
    <path d="M9 14 4 9l5-5" />
    <path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11" />
  </svg>
);

export function ConversationTurnShell({
  turn,
  summary,
  children,
  onToggleCollapsed,
  onRecall,
  rootRef,
}: {
  turn: AgentConversationTurn;
  summary: string;
  children: React.ReactNode;
  onToggleCollapsed: () => void;
  onRecall?: () => void;
  rootRef?: (node: HTMLDivElement | null) => void;
}) {
  return (
    <div ref={rootRef} style={{ marginBottom: 16 }}>
      <TurnMessageBubble role="user">
        <div
          className="hap-agent-turn-user-row"
          style={{ display: 'flex', alignItems: 'flex-start', gap: 8, width: '100%' }}
        >
          <span
            role="button"
            tabIndex={0}
            aria-label={turn.collapsed ? '展开' : '收起'}
            className="hap-agent-turn-toggle"
            onClick={onToggleCollapsed}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                onToggleCollapsed();
              }
            }}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 22,
              height: 22,
              flexShrink: 0,
              color: HAP_AGENT_THEME.accent,
              cursor: 'pointer',
            }}
          >
            {turn.collapsed ? <RightOutlined /> : <DownOutlined />}
          </span>
          <Text
            className="hap-agent-turn-user-text"
            onClick={onToggleCollapsed}
            style={{
              flex: 1,
              minWidth: 0,
              color: HAP_AGENT_THEME.text,
              fontWeight: 600,
              fontSize: 14,
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              cursor: 'pointer',
            }}
          >
            {summary}
          </Text>
          {onRecall ? (
            <Tooltip title="撤回">
              <span
                role="button"
                tabIndex={0}
                aria-label="撤回"
                className="hap-agent-turn-recall"
                onClick={(event) => {
                  event.stopPropagation();
                  onRecall();
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    event.stopPropagation();
                    onRecall();
                  }
                }}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 24,
                  height: 24,
                  marginLeft: 'auto',
                  flexShrink: 0,
                  borderRadius: 6,
                  color: '#98999B',
                  cursor: 'pointer',
                }}
              >
                {recallIcon}
              </span>
            </Tooltip>
          ) : null}
        </div>
      </TurnMessageBubble>
      {!turn.collapsed ? <div style={{ marginTop: 2 }}>{children}</div> : null}
    </div>
  );
}

export function HistoricalTurnOutput({
  turn,
  softenText,
  formatResponse,
  pickSummary,
}: {
  turn: AgentConversationTurn;
  softenText: (text: string) => string;
  formatResponse: (value: unknown) => string;
  pickSummary: (response: Record<string, unknown> | null) => string;
}) {
  const summary = pickSummary(turn.response);
  const hasAnswer = Boolean(summary || turn.response || turn.error);

  if (!hasAnswer) return null;

  return (
    <TurnMessageBubble role="assistant">
      {summary ? (
        <Paragraph style={{ marginBottom: turn.response || turn.error ? 8 : 0, color: HAP_AGENT_THEME.textSecondary }}>
          {softenText(summary)}
        </Paragraph>
      ) : null}
      {turn.response ? (
        <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, margin: 0, color: HAP_AGENT_THEME.text, lineHeight: 1.65 }}>
          {formatResponse(turn.response)}
        </pre>
      ) : null}
      {turn.error ? <Text type="danger">{turn.error}</Text> : null}
    </TurnMessageBubble>
  );
}
