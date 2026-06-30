import React, { useMemo, useState } from 'react';
import { DownOutlined, RightOutlined } from '@ant-design/icons';
import type { AgentActivity } from './agentStreamTypes';

type AgentActivityBlockProps = {
  activities: AgentActivity[];
  assistantText?: string;
};

export function AgentActivityBlock({ activities, assistantText }: AgentActivityBlockProps) {
  const [open, setOpen] = useState(false);
  const summary = useMemo(() => {
    const tools = activities.length;
    const ok = activities.filter((a) => a.status === 'ok').length;
    if (!tools) return '无工具调用';
    return `已执行 ${tools} 个操作${ok ? `（${ok} 成功）` : ''}`;
  }, [activities]);

  if (!activities.length && !assistantText) return null;

  return (
    <div style={{ marginTop: 8, fontSize: 13 }}>
      {assistantText ? (
        <div style={{ marginBottom: 8, whiteSpace: 'pre-wrap', color: '#111827' }}>{assistantText}</div>
      ) : null}
      {activities.length > 0 ? (
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
          }}
        >
          {open ? <DownOutlined style={{ fontSize: 10 }} /> : <RightOutlined style={{ fontSize: 10 }} />}
          <span>{summary}</span>
        </div>
      ) : null}
      {open && activities.length > 0 ? (
        <ul style={{ margin: '8px 0 0', paddingLeft: 18, color: '#4b5563' }}>
          {activities.map((item) => (
            <li key={item.toolCallId} style={{ marginBottom: 4 }}>
              <code style={{ fontSize: 13 }}>{item.toolName}</code>
              {' — '}
              <span>{item.status}</span>
              {item.durationMs != null ? <span> · {item.durationMs}ms</span> : null}
              {item.resultPreview ? (
                <div style={{ fontSize: 13, color: '#9ca3af', marginTop: 2 }}>{item.resultPreview.slice(0, 160)}</div>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
