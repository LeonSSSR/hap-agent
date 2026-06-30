import type { AgentSession, AgentSessionMessage } from '@/services/agent';
import { createConversationTurnId, type AgentConversationTurn } from './AgentConversationThread';

export const AGENT_SESSION_STORAGE_KEY = 'hap-agent-session-id';

export const buildTurnsFromSessionMessages = (messages: AgentSessionMessage[]): AgentConversationTurn[] => {
  const turns: AgentConversationTurn[] = [];
  let pending: AgentConversationTurn | null = null;

  messages.forEach((item) => {
    const role = String(item.role || '');
    const content = String(item.content || '').trim();
    const messageId = String(item.messageId || item.message_id || createConversationTurnId());

    if (role === 'user') {
      if (pending) {
        turns.push({ ...pending, collapsed: true });
      }
      pending = {
        id: messageId,
        userMessage: content,
        response: null,
        error: '',
        status: 'done',
        collapsed: false,
      };
      return;
    }

    if (role === 'assistant' && pending) {
      const snapshot = item.metadata?.chat_response;
      pending.response =
        snapshot && typeof snapshot === 'object' && !Array.isArray(snapshot)
          ? snapshot
          : { reply: content };
      pending.status = 'done';
    }
  });

  if (pending) {
    turns.push(pending);
  }

  return turns.map((turn, index) => ({
    ...turn,
    collapsed: index < turns.length - 1,
  }));
};

export const extractAssistantReply = (response: Record<string, unknown> | null): string => {
  if (!response || typeof response !== 'object') return '';
  return String(
    response.summary
      || response.understanding
      || (response.agentRun as Record<string, unknown> | undefined)?.assistantText
      || response.reply
      || '',
  ).trim();
};

export const buildSessionSavePayload = (turns: AgentConversationTurn[]) =>
  turns
    .filter((turn) => turn.userMessage.trim())
    .map((turn) => ({
      userMessage: turn.userMessage.trim(),
      assistantReply: extractAssistantReply(turn.response),
      chatResponse: turn.response && turn.status === 'done' ? turn.response : undefined,
    }));

export const applySessionToShell = (
  session: AgentSession,
  setters: {
    setSessionId: (value: string) => void;
    setConversationTurns: React.Dispatch<React.SetStateAction<AgentConversationTurn[]>>;
    setActiveTurnId: React.Dispatch<React.SetStateAction<string | null>>;
    setResponse: React.Dispatch<React.SetStateAction<any>>;
  },
) => {
  if (!session?.sessionId) return;
  setters.setSessionId(session.sessionId);
  const historyMessages = Array.isArray(session.messages) ? session.messages : [];
  if (historyMessages.length) {
    const restoredTurns = buildTurnsFromSessionMessages(historyMessages);
    setters.setConversationTurns(restoredTurns);
    const lastTurn = restoredTurns[restoredTurns.length - 1];
    if (lastTurn) {
      setters.setActiveTurnId(lastTurn.id);
      if (lastTurn.response) {
        setters.setResponse(lastTurn.response);
      }
    }
  } else {
    setters.setConversationTurns([]);
    setters.setActiveTurnId(null);
    setters.setResponse(null);
  }
};
