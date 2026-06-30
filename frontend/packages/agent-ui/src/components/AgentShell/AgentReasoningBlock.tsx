import React, { useState } from 'react';
import { DownOutlined, RightOutlined } from '@ant-design/icons';
import { AgentAssistantText } from './AgentAssistantText';
import { HAP_AGENT_THEME } from './AgentPanelTheme';

type AgentReasoningBlockProps = {
  text: string;
  softenText?: (value: string) => string;
  streaming?: boolean;
  defaultOpen?: boolean;
};

export function AgentReasoningBlock({
  text,
  softenText,
  streaming,
  defaultOpen = false,
}: AgentReasoningBlockProps) {
  const [open, setOpen] = useState(defaultOpen);
  const trimmed = text.trim();
  if (!trimmed) return null;

  return (
    <section aria-label="思考过程" style={{ marginBottom: 12 }}>
      <div
        role="button"
        tabIndex={0}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={(e) => e.key === 'Enter' && setOpen((v) => !v)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          color: '#6b7280',
          cursor: 'pointer',
          userSelect: 'none',
          fontSize: 12,
          marginBottom: open ? 8 : 0,
        }}
      >
        {open ? <DownOutlined style={{ fontSize: 10 }} /> : <RightOutlined style={{ fontSize: 10 }} />}
        <span>思考过程</span>
        {streaming ? <span style={{ color: '#9ca3af' }}>（生成中…）</span> : null}
      </div>
      {open ? (
        <div
          style={{
            background: HAP_AGENT_THEME.preBg,
            borderRadius: 12,
            padding: 12,
            border: `1px solid ${HAP_AGENT_THEME.preBorder}`,
            color: HAP_AGENT_THEME.textSecondary,
            fontSize: 13,
          }}
        >
          <AgentAssistantText text={trimmed} soften={softenText} streaming={streaming} />
        </div>
      ) : null}
    </section>
  );
}
