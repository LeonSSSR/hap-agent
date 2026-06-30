import React from 'react';
import { Spin, Typography } from 'antd';

type AgentOverlayProps = {
  visible: boolean;
  title: string;
  description?: string;
  queryContext?: Record<string, unknown>;
};

export function AgentOverlay({ visible, title, description }: AgentOverlayProps) {
  if (!visible) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10050,
        background: 'rgba(0,0,0,0.35)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          background: '#fff',
          padding: 24,
          borderRadius: 8,
          maxWidth: 420,
          textAlign: 'center',
          boxShadow: '0 12px 32px rgba(0,0,0,0.18)',
        }}
      >
        <Spin />
        <Typography.Title level={5} style={{ marginTop: 16, marginBottom: 8 }}>
          {title}
        </Typography.Title>
        {description ? <Typography.Text type="secondary">{description}</Typography.Text> : null}
      </div>
    </div>
  );
}
