import React, { useCallback, useEffect, useState } from 'react';
import { Button, Typography } from 'antd';
import { UndoOutlined } from '@ant-design/icons';
import type { AgentConversationTurn } from './AgentConversationThread';
import { HAP_AGENT_THEME } from './AgentPanelTheme';

const { Paragraph } = Typography;

type ConversationScrollPinHeaderProps = {
  turn: AgentConversationTurn;
  onJumpToTurn: () => void;
};

/** 滚动列表顶部粘性条：显示已滚出视口的最近一轮用户输入（Cursor 风格） */
export function ConversationScrollPinHeader({ turn, onJumpToTurn }: ConversationScrollPinHeaderProps) {
  return (
    <div
      className="hap-agent-scroll-pin"
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 12,
        marginBottom: 10,
        marginTop: -4,
        padding: '8px 10px',
        borderRadius: 10,
        background: HAP_AGENT_THEME.scrollPinBg,
        border: `1px solid ${HAP_AGENT_THEME.border}`,
        boxShadow: HAP_AGENT_THEME.shadow,
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 8,
      }}
    >
      <Paragraph
        style={{
          flex: 1,
          marginBottom: 0,
          color: HAP_AGENT_THEME.textSecondary,
          fontSize: 12,
          lineHeight: 1.5,
        }}
        ellipsis={{ rows: 2, expandable: false }}
      >
        {turn.userMessage}
      </Paragraph>
      <Button
        type="text"
        size="small"
        aria-label="回到该轮对话"
        icon={<UndoOutlined style={{ color: HAP_AGENT_THEME.textMuted, fontSize: 12 }} />}
        onClick={onJumpToTurn}
        style={{ flexShrink: 0, marginTop: 2, padding: '0 4px', height: 'auto' }}
      />
    </div>
  );
}

export function useConversationScrollPin(
  conversationTurns: AgentConversationTurn[],
  conversationScrollRef: React.RefObject<HTMLDivElement | null>,
  turnRefs: React.MutableRefObject<Map<string, HTMLDivElement>>,
) {
  const [pinnedTurnId, setPinnedTurnId] = useState<string | null>(null);
  const [scrollPinVisible, setScrollPinVisible] = useState(false);

  const updateScrollPin = useCallback(() => {
    const container = conversationScrollRef.current;
    if (!container || conversationTurns.length === 0) {
      setScrollPinVisible(false);
      setPinnedTurnId(null);
      return;
    }

    const { scrollTop } = container;
    if (scrollTop <= 4) {
      setScrollPinVisible(false);
      setPinnedTurnId(null);
      return;
    }

    const containerTop = container.getBoundingClientRect().top;
    let anchorTurnId: string | null = null;

    for (const turn of conversationTurns) {
      const el = turnRefs.current.get(turn.id);
      if (!el) continue;
      const rect = el.getBoundingClientRect();
      if (rect.top <= containerTop + 6) {
        anchorTurnId = turn.id;
      }
    }

    if (!anchorTurnId) {
      setScrollPinVisible(false);
      setPinnedTurnId(null);
      return;
    }

    const anchorEl = turnRefs.current.get(anchorTurnId);
    const userEl = anchorEl?.querySelector('[data-hap-turn-user]') as HTMLElement | null;
    const userScrolledAway = userEl ? userEl.getBoundingClientRect().bottom < containerTop + 2 : scrollTop > 24;

    if (userScrolledAway) {
      setScrollPinVisible(true);
      setPinnedTurnId(anchorTurnId);
    } else {
      setScrollPinVisible(false);
      setPinnedTurnId(null);
    }
  }, [conversationTurns, conversationScrollRef, turnRefs]);

  const scrollToTurn = useCallback(
    (turnId: string) => {
      const container = conversationScrollRef.current;
      const el = turnRefs.current.get(turnId);
      if (!container || !el) return;
      container.scrollTo({ top: Math.max(el.offsetTop - 8, 0), behavior: 'smooth' });
    },
    [conversationScrollRef, turnRefs],
  );

  useEffect(() => {
    updateScrollPin();
  }, [conversationTurns, updateScrollPin]);

  useEffect(() => {
    const container = conversationScrollRef.current;
    if (!container) return undefined;
    const ro = new ResizeObserver(() => updateScrollPin());
    ro.observe(container);
    return () => ro.disconnect();
  }, [conversationScrollRef, updateScrollPin, conversationTurns.length]);

  const pinnedTurn = conversationTurns.find((t) => t.id === pinnedTurnId) ?? null;

  return {
    pinnedTurn,
    scrollPinVisible,
    updateScrollPin,
    scrollToTurn,
  };
}
