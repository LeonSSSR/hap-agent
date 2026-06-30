import React, { memo, useEffect, useRef } from 'react';
import { Alert } from 'antd';
import type { ExecutionStatus } from './agentExecutionTypes';

export type ExecutionLogPanelProps = {
  executionStatus: ExecutionStatus;
  executionError: string;
  executionLogs: string[];
};

export const ExecutionLogPanel = memo(function ExecutionLogPanel({
  executionStatus,
  executionError,
  executionLogs,
}: ExecutionLogPanelProps) {
  const logRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    const node = logRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [executionLogs.length, executionStatus]);

  return (
    <div style={{ padding: '8px 12px' }}>
      {executionStatus === 'running' ? (
        <Alert
          showIcon
          type="info"
          message="Agent 正在逐步执行（左侧页面可看到高亮操作）"
          style={{
            marginBottom: 8,
            background: 'rgba(220, 38, 38, 0.08)',
            border: '1px solid rgba(220, 38, 38, 0.22)',
          }}
        />
      ) : null}
      {executionError ? <Alert showIcon type="error" message={executionError} style={{ marginBottom: 8 }} /> : null}
      <pre
        ref={logRef}
        style={{
          margin: 0,
          minHeight: 96,
          maxHeight: 240,
          overflow: 'auto',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          color: '#166534',
          background: '#f9fafb',
          borderRadius: 8,
          padding: 10,
          border: '1px solid rgba(15,23,42,0.08)',
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
          fontSize: 11,
          lineHeight: 1.55,
        }}
      >
        {executionLogs.length > 0
          ? executionLogs.join('\n')
          : executionStatus === 'running'
            ? '等待执行流输出…'
            : '批准并开始执行后，SSE 日志将在此展示。'}
      </pre>
    </div>
  );
});
