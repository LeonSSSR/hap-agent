import { useCallback, useEffect, useState } from 'react';
import { message } from 'antd';
import {
  createSession,
  deleteAgentSession,
  getSession,
  listSessions,
  saveAgentSession,
  type AgentSessionListItem,
} from '@/services/agent';
import type { AgentConversationTurn } from './AgentConversationThread';
import {
  AGENT_SESSION_STORAGE_KEY,
  applySessionToShell,
  buildSessionSavePayload,
} from './agentSession';

type UseAgentSessionOptions = {
  enabled: boolean;
  resetExecutionState: () => void;
  setError: React.Dispatch<React.SetStateAction<string>>;
};

export function useAgentSession({
  enabled,
  resetExecutionState,
  setError,
}: UseAgentSessionOptions) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionReady, setSessionReady] = useState(false);
  const [sessionListOpen, setSessionListOpen] = useState(false);
  const [sessionListItems, setSessionListItems] = useState<AgentSessionListItem[]>([]);
  const [sessionListLoading, setSessionListLoading] = useState(false);
  const [conversationTurns, setConversationTurns] = useState<AgentConversationTurn[]>([]);
  const [activeTurnId, setActiveTurnId] = useState<string | null>(null);
  const [response, setResponse] = useState<any>(null);

  const loadSessionList = useCallback(async () => {
    setSessionListLoading(true);
    try {
      const result = await listSessions(30, 0);
      setSessionListItems(result.items);
    } catch {
      setSessionListItems([]);
    } finally {
      setSessionListLoading(false);
    }
  }, []);

  const persistCurrentSession = useCallback(async (turns: AgentConversationTurn[], sid: string | null) => {
    if (!sid) return;
    const payload = buildSessionSavePayload(turns);
    if (!payload.length) return;
    await saveAgentSession(sid, {
      title: payload[0].userMessage.slice(0, 40),
      turns: payload,
    });
  }, []);

  const switchSession = useCallback(
    async (nextSessionId: string) => {
      if (!nextSessionId || nextSessionId === sessionId) {
        setSessionListOpen(false);
        return;
      }
      try {
        const session = await getSession(nextSessionId);
        if (!session?.sessionId) return;
        if (typeof window !== 'undefined') {
          window.localStorage.setItem(AGENT_SESSION_STORAGE_KEY, session.sessionId);
        }
        applySessionToShell(session, {
          setSessionId,
          setConversationTurns,
          setActiveTurnId,
          setResponse,
        });
        resetExecutionState();
        setError('');
        setSessionListOpen(false);
      } catch (e: any) {
        message.error(e?.message || '切换会话失败');
      }
    },
    [resetExecutionState, sessionId, setError],
  );

  const saveCurrentSessionAndNew = useCallback(async () => {
    if (sessionId) {
      await persistCurrentSession(conversationTurns, sessionId);
    }
    const session = await createSession();
    if (!session?.sessionId) {
      throw new Error('创建新会话失败');
    }
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(AGENT_SESSION_STORAGE_KEY, session.sessionId);
    }
    setSessionId(session.sessionId);
    setConversationTurns([]);
    setActiveTurnId(null);
    setResponse(null);
    resetExecutionState();
    setError('');
    await loadSessionList();
  }, [
    conversationTurns,
    loadSessionList,
    persistCurrentSession,
    resetExecutionState,
    sessionId,
    setError,
  ]);

  const removeSession = useCallback(
    async (targetSessionId: string) => {
      await deleteAgentSession(targetSessionId);
      await loadSessionList();
      if (targetSessionId !== sessionId) return;
      const session = await createSession();
      if (!session?.sessionId) {
        throw new Error('创建新会话失败');
      }
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(AGENT_SESSION_STORAGE_KEY, session.sessionId);
      }
      setSessionId(session.sessionId);
      setConversationTurns([]);
      setActiveTurnId(null);
      setResponse(null);
      resetExecutionState();
      setError('');
    },
    [loadSessionList, resetExecutionState, sessionId, setError],
  );

  useEffect(() => {
    if (!enabled) return undefined;

    let cancelled = false;

    const restoreSession = async () => {
      try {
        let storedSessionId: string | null = null;
        if (typeof window !== 'undefined') {
          storedSessionId = window.localStorage.getItem(AGENT_SESSION_STORAGE_KEY);
        }
        let session = storedSessionId ? await getSession(storedSessionId) : null;
        if (!session?.sessionId) {
          session = await createSession();
        }
        if (cancelled || !session?.sessionId) return;
        if (typeof window !== 'undefined') {
          window.localStorage.setItem(AGENT_SESSION_STORAGE_KEY, session.sessionId);
        }
        applySessionToShell(session, {
          setSessionId,
          setConversationTurns,
          setActiveTurnId,
          setResponse,
        });
      } catch {
        if (cancelled) return;
        try {
          const session = await createSession();
          if (!session?.sessionId) return;
          setSessionId(session.sessionId);
          if (typeof window !== 'undefined') {
            window.localStorage.setItem(AGENT_SESSION_STORAGE_KEY, session.sessionId);
          }
        } catch {
          // ignore session bootstrap errors
        }
      } finally {
        if (!cancelled) setSessionReady(true);
      }
    };

    void restoreSession();
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  useEffect(() => {
    if (!enabled || !sessionListOpen) return;
    void loadSessionList();
  }, [enabled, loadSessionList, sessionListOpen]);

  return {
    sessionId,
    sessionReady,
    sessionListOpen,
    setSessionListOpen,
    sessionListItems,
    sessionListLoading,
    conversationTurns,
    setConversationTurns,
    activeTurnId,
    setActiveTurnId,
    response,
    setResponse,
    switchSession,
    loadSessionList,
    persistCurrentSession,
    saveCurrentSessionAndNew,
    removeSession,
  };
}
