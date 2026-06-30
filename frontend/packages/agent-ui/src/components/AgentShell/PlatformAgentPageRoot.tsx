import { useLocation } from '@umijs/max';
import React from 'react';
import { resolveOperationByPathname } from './platformOperationsMap';

/**
 * 按当前路由绑定页面级 Agent 锚点，使未单独打标的业务页也能被高亮/导航联动。
 */
export function PlatformAgentPageRoot({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const op = resolveOperationByPathname(pathname);
  const uiActionId = op?.ui_action_id;

  if (!uiActionId) {
    return <>{children}</>;
  }

  return (
    <div
      data-agent-page-root={uiActionId}
      data-agent-action-id={uiActionId}
      style={{ display: 'contents' }}
    >
      {children}
    </div>
  );
}
