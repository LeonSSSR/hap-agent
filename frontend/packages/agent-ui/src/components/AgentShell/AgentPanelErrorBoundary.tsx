import React from 'react';
import { Alert, Button } from 'antd';

type State = { error: Error | null };

/** 仅包裹右侧 Agent 分栏，避免 Agent 异常拖垮整页布局。 */
export class AgentPanelErrorBoundary extends React.Component<
  { children: React.ReactNode },
  State
> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[AgentPanelErrorBoundary]', error, info.componentStack);
  }

  handleRetry = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 12, height: '100%', overflow: 'auto' }}>
          <Alert
            showIcon
            type="error"
            message="Agent 面板渲染失败"
            description={this.state.error.message}
            style={{ marginBottom: 12 }}
          />
          <Button type="primary" size="small" onClick={this.handleRetry}>
            重试加载 Agent
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
