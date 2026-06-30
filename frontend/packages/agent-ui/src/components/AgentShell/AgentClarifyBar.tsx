import React, { memo, useEffect, useState } from 'react';
import { Alert, Button, Input, Space } from 'antd';
import type { AgentClarifyPending } from './agentClarifyTypes';

export type AgentClarifyBarProps = {
  pending: AgentClarifyPending | null;
  onSubmit: (answer: string) => void;
  onSkip: () => void;
  /** 父组件在提交完成/失败后递增，用于解除 loading */
  submitResetKey?: number;
  postError?: string;
};

export const AgentClarifyBar = memo(function AgentClarifyBar({
  pending,
  onSubmit,
  onSkip,
  submitResetKey = 0,
  postError,
}: AgentClarifyBarProps) {
  const [value, setValue] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setValue('');
    setSubmitting(false);
  }, [pending?.resumeToken, submitResetKey]);

  if (!pending) return null;

  const placeholder = pending.placeholder || '请输入补充信息';
  const choices = pending.choices?.filter(Boolean) ?? [];
  const submitAnswer = (answer: string) => {
    const trimmed = answer.trim();
    if (!trimmed || submitting) return;
    setSubmitting(true);
    onSubmit(trimmed);
  };

  const handleSkip = () => {
    if (submitting) return;
    setSubmitting(true);
    onSkip();
  };

  return (
    <Alert
      showIcon
      type="info"
      style={{ marginBottom: 12, borderRadius: 12, position: 'relative', zIndex: 20 }}
      message="需要您补充信息"
      description={
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <div>{pending.question}</div>
          {postError ? (
            <div style={{ color: '#cf1322', fontSize: 12 }}>{postError}</div>
          ) : null}
          {choices.length > 0 ? (
            <Space wrap>
              {choices.map((choice) => (
                <Button
                  key={choice}
                  size="small"
                  type={value === choice ? 'primary' : 'default'}
                  disabled={submitting}
                  onClick={() => {
                    setValue(choice);
                    submitAnswer(choice);
                  }}
                >
                  {choice}
                </Button>
              ))}
            </Space>
          ) : null}
          <Input
            value={value}
            placeholder={placeholder}
            onChange={(e) => setValue(e.target.value)}
            onPressEnter={() => submitAnswer(value)}
            disabled={submitting}
            autoFocus
          />
          <Space>
            <Button
              size="small"
              type="primary"
              loading={submitting}
              disabled={!value.trim() || submitting}
              onClick={() => submitAnswer(value)}
            >
              提交并继续
            </Button>
            <Button size="small" disabled={submitting} onClick={handleSkip}>
              跳过
            </Button>
          </Space>
        </Space>
      }
    />
  );
});
