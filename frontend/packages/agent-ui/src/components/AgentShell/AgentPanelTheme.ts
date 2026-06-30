import type { CardProps } from 'antd';
import type React from 'react';

/** HAP Agent 浅色主题令牌 */
export const HAP_AGENT_THEME = {
  bg: '#f5f5f7',
  bgElevated: '#ffffff',
  bgMuted: '#f3f4f6',
  bgComposer: '#F5F5F5',
  border: 'rgba(15, 23, 42, 0.1)',
  borderAccent: 'rgba(220, 38, 38, 0.22)',
  text: '#111827',
  textSecondary: '#4b5563',
  textMuted: '#9ca3af',
  textAccent: '#b91c1c',
  textLink: '#dc2626',
  accent: '#dc2626',
  accentDark: '#991b1b',
  accentSoft: 'rgba(220, 38, 38, 0.08)',
  accentSoftBorder: 'rgba(220, 38, 38, 0.18)',
  userBubbleBg: 'rgba(220, 38, 38, 0.06)',
  userBubbleBorder: 'rgba(220, 38, 38, 0.16)',
  shadow: '0 4px 16px rgba(15, 23, 42, 0.06)',
  shadowLg: '0 8px 24px rgba(15, 23, 42, 0.08)',
  scrollPinBg: 'rgba(255, 255, 255, 0.96)',
  inputBg: '#F5F5F5',
  inputBorder: 'rgba(15, 23, 42, 0.14)',
  preBg: '#f9fafb',
  preBorder: 'rgba(15, 23, 42, 0.08)',
  successBg: 'rgba(22, 163, 74, 0.1)',
  successBorder: 'rgba(22, 163, 74, 0.28)',
  successText: '#15803d',
  errorBg: 'rgba(220, 38, 38, 0.08)',
  errorBorder: 'rgba(220, 38, 38, 0.28)',
  errorText: '#b91c1c',
  warningBg: 'rgba(245, 158, 11, 0.1)',
  warningBorder: 'rgba(245, 158, 11, 0.28)',
  warningText: '#b45309',
  tagDefaultBg: 'rgba(15, 23, 42, 0.04)',
  tagDefaultBorder: 'rgba(15, 23, 42, 0.1)',
  tagDefaultText: '#4b5563',
} as const;

export const AGENT_CARD_HEADER_STYLE: React.CSSProperties = {
  background: HAP_AGENT_THEME.bgElevated,
  borderBottom: `1px solid ${HAP_AGENT_THEME.border}`,
  padding: '8px 12px',
  minHeight: 40,
};

export const agentCardStyles = (bodyPadding = 14): NonNullable<CardProps['styles']> => ({
  header: AGENT_CARD_HEADER_STYLE,
  body: { padding: bodyPadding },
});

export const AGENT_PANEL_ANT_THEME = {
  token: {
    colorBgContainer: HAP_AGENT_THEME.bgElevated,
    colorText: HAP_AGENT_THEME.text,
    colorTextSecondary: HAP_AGENT_THEME.textSecondary,
    colorBorder: HAP_AGENT_THEME.border,
    colorBorderSecondary: HAP_AGENT_THEME.border,
  },
  components: {
    Card: {
      headerBg: HAP_AGENT_THEME.bgElevated,
      colorTextHeading: HAP_AGENT_THEME.text,
      colorBorderSecondary: HAP_AGENT_THEME.border,
    },
    Input: {
      colorBgContainer: HAP_AGENT_THEME.inputBg,
      colorBorder: HAP_AGENT_THEME.inputBorder,
      colorText: HAP_AGENT_THEME.text,
    },
  },
} as const;

export const statusTagStyle = (tone: 'success' | 'error' | 'default') => {
  if (tone === 'success') {
    return {
      background: HAP_AGENT_THEME.successBg,
      borderColor: HAP_AGENT_THEME.successBorder,
      color: HAP_AGENT_THEME.successText,
    };
  }
  if (tone === 'error') {
    return {
      background: HAP_AGENT_THEME.errorBg,
      borderColor: HAP_AGENT_THEME.errorBorder,
      color: HAP_AGENT_THEME.errorText,
    };
  }
  return {
    background: HAP_AGENT_THEME.tagDefaultBg,
    borderColor: HAP_AGENT_THEME.tagDefaultBorder,
    color: HAP_AGENT_THEME.tagDefaultText,
  };
};

export const operationAccessTagStyle = {
  background: HAP_AGENT_THEME.tagDefaultBg,
  borderColor: HAP_AGENT_THEME.tagDefaultBorder,
  color: HAP_AGENT_THEME.textSecondary,
  fontSize: 11,
} as const;

export const operationRiskTagStyle = (riskLevel: 'low' | 'medium' | 'high') => {
  if (riskLevel === 'low') return statusTagStyle('success');
  if (riskLevel === 'medium') {
    return {
      background: HAP_AGENT_THEME.warningBg,
      borderColor: HAP_AGENT_THEME.warningBorder,
      color: HAP_AGENT_THEME.warningText,
    };
  }
  return statusTagStyle('error');
};

export const cardSurfaceStyle: React.CSSProperties = {
  background: HAP_AGENT_THEME.bgElevated,
  border: `1px solid ${HAP_AGENT_THEME.border}`,
  borderRadius: 12,
  padding: 12,
  marginBottom: 12,
};

export const planSummaryMutedStyle: React.CSSProperties = {
  background: HAP_AGENT_THEME.bgMuted,
  border: `1px solid ${HAP_AGENT_THEME.border}`,
  borderRadius: 12,
  padding: 12,
  marginBottom: 12,
};

/** 对话轮次：用户提问 / Agent 回答统一气泡框（白卡片 + 轻阴影，与平台内容区一致） */
export const agentTurnBubbleStyle = (_role: 'user' | 'assistant'): React.CSSProperties => ({
  border: `1px solid ${HAP_AGENT_THEME.border}`,
  borderRadius: 12,
  padding: '12px 14px',
  marginBottom: 10,
  background: HAP_AGENT_THEME.bgElevated,
  boxShadow: HAP_AGENT_THEME.shadow,
});

export const riskControlRulesCardStyle: React.CSSProperties = {
  marginTop: 10,
  padding: 12,
  borderRadius: 12,
  background: HAP_AGENT_THEME.bgMuted,
  border: `1px solid ${HAP_AGENT_THEME.borderAccent}`,
};
