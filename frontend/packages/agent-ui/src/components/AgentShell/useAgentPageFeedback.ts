import { useCallback, useState } from 'react';
import type { PageActionHintState } from './AgentPageActionHint';

export function useAgentPageFeedback() {
  const [pageActionHint, setPageActionHint] = useState<PageActionHintState | null>(null);
  const [pageActionErrors, setPageActionErrors] = useState<string[]>([]);

  const resetPageFeedback = useCallback(() => {
    setPageActionHint(null);
    setPageActionErrors([]);
  }, []);

  return {
    pageActionHint,
    setPageActionHint,
    pageActionErrors,
    setPageActionErrors,
    resetPageFeedback,
  };
}
