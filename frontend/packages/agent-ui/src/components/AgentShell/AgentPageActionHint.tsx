import React from 'react';
import { createPortal } from 'react-dom';
import {
  AimOutlined,
  FormOutlined,
  LoadingOutlined,
  RocketOutlined,
} from '@ant-design/icons';
import { HAP_AGENT_THEME } from './AgentPanelTheme';

export type PageActionHintKind = 'navigate' | 'highlight' | 'open_panel' | 'page_action';

export type PageActionHintState = {
  kind: PageActionHintKind;
  stepTitle: string;
  route?: string;
  uiActionId?: string;
  /** 打开面板时的按钮文案 */
  panelLabel?: string;
};

const ROUTE_LABELS: Record<string, string> = {
  '/data-governance/datasets': '数据治理 · 数据集',
  '/model-dev/training': '模型开发 · 训练',
  '/model-app/model-versions': '模型应用 · 模型版本',
  '/model-app/evaluation': '模型应用 · 评估',
  '/model-app/service-publish': '模型应用 · 发布',
  '/model-app/service-deploy': '模型应用 · 部署',
  '/model-app/service-invoke': '模型应用 · 推理',
  '/model-app/feature-drift': '模型应用 · 漂移治理',
};

const OPEN_PANEL_LABELS: Record<string, string> = {
  'ml.training.submit': '创建训练任务',
  'ml.model.register': '注册模型版本',
  'ml.deploy': '部署推理服务',
};

function routeLabel(route?: string): string | undefined {
  if (!route) return undefined;
  return ROUTE_LABELS[route.split('?')[0]] || route.split('?')[0];
}

export function buildPageActionHint(state: PageActionHintState): { title: string; description: string } {
  const step = state.stepTitle || '当前步骤';
  switch (state.kind) {
    case 'navigate': {
      const dest = routeLabel(state.route);
      return {
        title: dest ? `正在打开 ${dest}` : '正在跳转业务页面',
        description: `接下来将高亮「${step}」相关区域`,
      };
    }
    case 'highlight':
      return {
        title: `正在定位：${step}`,
        description: '请在左侧页面查看高亮控件',
      };
    case 'open_panel': {
      const panel =
        state.panelLabel
        || (state.uiActionId ? OPEN_PANEL_LABELS[state.uiActionId] : undefined)
        || step;
      return {
        title: `正在展开「${panel}」`,
        description: '仅打开表单/抽屉供查看，不会自动提交或保存',
      };
    }
    case 'page_action':
    default:
      return {
        title: `正在操作：${step}`,
        description: state.uiActionId ? `页面动作 ${state.uiActionId}` : '请在左侧页面查看 Agent 操作',
      };
  }
}

function kindIcon(kind: PageActionHintKind) {
  switch (kind) {
    case 'navigate':
      return <RocketOutlined />;
    case 'open_panel':
      return <FormOutlined />;
    case 'highlight':
      return <AimOutlined />;
    default:
      return <LoadingOutlined spin />;
  }
}

export type AgentPageActionHintProps = {
  hint: PageActionHintState | null;
};

/** 左侧业务区角标提示：轻量、不挡 Agent 面板、不展示调试信息 */
export const AgentPageActionHint: React.FC<AgentPageActionHintProps> = ({ hint }) => {
  if (!hint || typeof document === 'undefined') return null;

  const { title, description } = buildPageActionHint(hint);

  return createPortal(
    <div
      className="hap-agent-page-action-hint"
      role="status"
      aria-live="polite"
      style={{
        position: 'fixed',
        left: 16,
        top: 72,
        zIndex: 10030,
        maxWidth: 'min(360px, calc(100vw - 480px))',
        pointerEvents: 'none',
        animation: 'hap-agent-hint-in 0.22s ease-out',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 10,
          padding: '10px 14px',
          background: 'rgba(255, 255, 255, 0.96)',
          border: `1px solid ${HAP_AGENT_THEME.borderAccent}`,
          borderRadius: 12,
          boxShadow: HAP_AGENT_THEME.shadowLg,
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 10,
            flexShrink: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: HAP_AGENT_THEME.accentSoft,
            color: HAP_AGENT_THEME.accent,
            fontSize: 16,
          }}
        >
          {kindIcon(hint.kind)}
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: HAP_AGENT_THEME.text, lineHeight: 1.35 }}>
            {title}
          </div>
          <div style={{ fontSize: 12, color: HAP_AGENT_THEME.textSecondary, marginTop: 4, lineHeight: 1.45 }}>
            {description}
          </div>
          {hint.kind === 'open_panel' ? (
            <div
              style={{
                marginTop: 6,
                fontSize: 11,
                color: HAP_AGENT_THEME.successText,
                background: HAP_AGENT_THEME.successBg,
                border: `1px solid ${HAP_AGENT_THEME.successBorder}`,
                borderRadius: 6,
                padding: '2px 8px',
                display: 'inline-block',
              }}
            >
              安全模式 · 不自动提交
            </div>
          ) : null}
        </div>
      </div>
      <style>{`
        @keyframes hap-agent-hint-in {
          from { opacity: 0; transform: translateY(-6px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>,
    document.body,
  );
};
