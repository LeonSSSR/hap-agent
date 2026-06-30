import React from 'react';

/** ProTable search 区查询/重置按钮注入 data-agent-action-id */
export function agentSearchOptionRender(searchActionId: string, resetActionId: string) {
  return (_searchConfig: unknown, _formProps: unknown, dom: React.ReactNode[]) =>
    dom.map((node, index) => {
      if (!React.isValidElement(node)) return node;
      const id = index === 0 ? searchActionId : index === 1 ? resetActionId : undefined;
      return id
        ? React.cloneElement(node as React.ReactElement<Record<string, unknown>>, {
            'data-agent-action-id': id,
          })
        : node;
    });
}
