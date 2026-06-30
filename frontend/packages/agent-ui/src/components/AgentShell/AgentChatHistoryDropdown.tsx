import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Dropdown,
  Input,
  Popconfirm,
  Popover,
  Spin,
  Typography,
} from 'antd';
import {
  CheckCircleOutlined,
  DeleteOutlined,
  FormOutlined,
  MoreOutlined,
  PushpinFilled,
  PushpinOutlined,
} from '@ant-design/icons';
import type { AgentSessionListItem } from '@/services/agent';

const { Text } = Typography;

const PINNED_STORAGE_KEY = 'hap-agent-pinned-sessions';
const PANEL_WIDTH = 300;
const PANEL_MAX_HEIGHT = 420;

type AgentChatHistoryDropdownProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  loading: boolean;
  items: AgentSessionListItem[];
  activeSessionId: string | null;
  onSelect: (sessionId: string) => void | Promise<void>;
  onDelete: (sessionId: string) => void | Promise<void>;
  children: React.ReactNode;
};

type SessionGroupKey = 'today' | 'previous7Days' | 'older';

type SessionGroups = Record<SessionGroupKey, AgentSessionListItem[]>;

function readPinnedSessionIds(): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(PINNED_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((id) => typeof id === 'string') : [];
  } catch {
    return [];
  }
}

function writePinnedSessionIds(ids: string[]) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(PINNED_STORAGE_KEY, JSON.stringify(ids));
  } catch {
    /* ignore */
  }
}

function resolveSessionId(item: AgentSessionListItem): string {
  return String(item.sessionId || item.session_id || '');
}

function isDraftSession(item: AgentSessionListItem): boolean {
  const messageCount = item.messageCount ?? 0;
  return item.status !== 'saved' && messageCount > 0;
}

function getSessionTitle(item: AgentSessionListItem): string {
  const base = String(item.title || item.summary || '').trim();
  if (isDraftSession(item)) {
    const draftBody = base || 'Untitled';
    return draftBody.startsWith('Draft:') ? draftBody : `Draft: ${draftBody}`;
  }
  return base || 'New Agent';
}

function groupSessionsByTime(items: AgentSessionListItem[]): SessionGroups {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfPrevious7Days = new Date(startOfToday);
  startOfPrevious7Days.setDate(startOfPrevious7Days.getDate() - 7);

  const groups: SessionGroups = {
    today: [],
    previous7Days: [],
    older: [],
  };

  items.forEach((item) => {
    const updatedAt = item.updatedAt ? new Date(item.updatedAt) : null;
    if (!updatedAt || Number.isNaN(updatedAt.getTime()) || updatedAt >= startOfToday) {
      groups.today.push(item);
      return;
    }
    if (updatedAt >= startOfPrevious7Days) {
      groups.previous7Days.push(item);
      return;
    }
    groups.older.push(item);
  });

  return groups;
}

const GROUP_LABELS: Record<SessionGroupKey, string> = {
  today: 'Today',
  previous7Days: 'Previous 7 days',
  older: 'Older',
};

function SessionRow({
  item,
  active,
  pinned,
  onSelect,
  onDelete,
  onTogglePin,
}: {
  item: AgentSessionListItem;
  active: boolean;
  pinned: boolean;
  onSelect: (sessionId: string) => void;
  onDelete: (sessionId: string) => void;
  onTogglePin: (sessionId: string) => void;
}) {
  const sessionId = resolveSessionId(item);
  const draft = isDraftSession(item);
  const title = getSessionTitle(item);
  const [hovered, setHovered] = useState(false);

  const rowMenuItems = [
    {
      key: 'pin',
      label: pinned ? 'Unpin' : 'Pin',
      icon: pinned ? <PushpinFilled /> : <PushpinOutlined />,
      onClick: () => onTogglePin(sessionId),
    },
  ];

  return (
    <div
      role="button"
      tabIndex={0}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => onSelect(sessionId)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect(sessionId);
        }
      }}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '7px 10px',
        borderRadius: 8,
        cursor: 'pointer',
        background: active ? '#2563eb' : hovered ? 'rgba(15, 23, 42, 0.05)' : 'transparent',
        color: active ? '#ffffff' : '#111827',
        transition: 'background 0.15s ease',
      }}
    >
      <span style={{ flexShrink: 0, fontSize: 14, lineHeight: 1, opacity: active ? 1 : 0.72 }}>
        {draft ? <FormOutlined /> : <CheckCircleOutlined />}
      </span>
      <Text
        ellipsis
        style={{
          flex: 1,
          minWidth: 0,
          margin: 0,
          fontSize: 13,
          color: 'inherit',
          fontWeight: active ? 500 : 400,
        }}
      >
        {title}
      </Text>
      {(hovered || active || pinned) ? (
        <span
          style={{ display: 'inline-flex', alignItems: 'center', gap: 2, flexShrink: 0 }}
          onClick={(event) => event.stopPropagation()}
        >
          <Dropdown menu={{ items: rowMenuItems }} trigger={['click']} placement="bottomRight">
            <Button
              type="text"
              size="small"
              icon={<MoreOutlined />}
              aria-label="More actions"
              style={{
                width: 22,
                height: 22,
                minWidth: 22,
                padding: 0,
                color: active ? '#ffffff' : 'rgba(17,24,39,0.55)',
              }}
              onClick={(event) => event.stopPropagation()}
            />
          </Dropdown>
          <Popconfirm
            title="Delete this agent?"
            description="This conversation cannot be restored."
            okText="Delete"
            cancelText="Cancel"
            okButtonProps={{ danger: true }}
            onConfirm={() => onDelete(sessionId)}
          >
            <Button
              type="text"
              size="small"
              icon={<DeleteOutlined />}
              aria-label="Delete agent"
              style={{
                width: 22,
                height: 22,
                minWidth: 22,
                padding: 0,
                color: active ? '#ffffff' : 'rgba(17,24,39,0.55)',
              }}
              onClick={(event) => event.stopPropagation()}
            />
          </Popconfirm>
        </span>
      ) : null}
      {pinned ? (
        <span style={{ flexShrink: 0, fontSize: 12, opacity: active ? 0.95 : 0.55 }}>
          <PushpinFilled />
        </span>
      ) : null}
    </div>
  );
}

function SessionSection({
  label,
  items,
  activeSessionId,
  pinnedIds,
  onSelect,
  onDelete,
  onTogglePin,
}: {
  label: string;
  items: AgentSessionListItem[];
  activeSessionId: string | null;
  pinnedIds: Set<string>;
  onSelect: (sessionId: string) => void;
  onDelete: (sessionId: string) => void;
  onTogglePin: (sessionId: string) => void;
}) {
  if (items.length === 0) return null;
  return (
    <div style={{ marginTop: 10 }}>
      <Text
        style={{
          display: 'block',
          padding: '0 10px 4px',
          fontSize: 11,
          fontWeight: 500,
          color: 'rgba(17,24,39,0.42)',
          letterSpacing: '0.01em',
        }}
      >
        {label}
      </Text>
      {items.map((item) => {
        const sessionId = resolveSessionId(item);
        return (
          <SessionRow
            key={sessionId}
            item={item}
            active={sessionId === activeSessionId}
            pinned={pinnedIds.has(sessionId)}
            onSelect={onSelect}
            onDelete={onDelete}
            onTogglePin={onTogglePin}
          />
        );
      })}
    </div>
  );
}

export function AgentChatHistoryDropdown({
  open,
  onOpenChange,
  loading,
  items,
  activeSessionId,
  onSelect,
  onDelete,
  children,
}: AgentChatHistoryDropdownProps) {
  const [query, setQuery] = useState('');
  const [pinnedIds, setPinnedIds] = useState<string[]>(() => readPinnedSessionIds());

  useEffect(() => {
    if (!open) {
      setQuery('');
    }
  }, [open]);

  const pinnedIdSet = useMemo(() => new Set(pinnedIds), [pinnedIds]);

  const filteredItems = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) return items;
    return items.filter((item) => {
      const title = getSessionTitle(item).toLowerCase();
      const summary = String(item.summary || '').toLowerCase();
      return title.includes(keyword) || summary.includes(keyword);
    });
  }, [items, query]);

  const pinnedItems = useMemo(
    () =>
      pinnedIds
        .map((id) => filteredItems.find((item) => resolveSessionId(item) === id))
        .filter((item): item is AgentSessionListItem => Boolean(item)),
    [filteredItems, pinnedIds],
  );

  const unpinnedItems = useMemo(
    () => filteredItems.filter((item) => !pinnedIdSet.has(resolveSessionId(item))),
    [filteredItems, pinnedIdSet],
  );

  const groupedItems = useMemo(() => groupSessionsByTime(unpinnedItems), [unpinnedItems]);

  const handleTogglePin = useCallback((sessionId: string) => {
    setPinnedIds((prev) => {
      const next = prev.includes(sessionId) ? prev.filter((id) => id !== sessionId) : [sessionId, ...prev];
      writePinnedSessionIds(next);
      return next;
    });
  }, []);

  const handleSelect = useCallback(
    (sessionId: string) => {
      void onSelect(sessionId);
    },
    [onSelect],
  );

  const handleDelete = useCallback(
    (sessionId: string) => {
      setPinnedIds((prev) => {
        if (!prev.includes(sessionId)) return prev;
        const next = prev.filter((id) => id !== sessionId);
        writePinnedSessionIds(next);
        return next;
      });
      void onDelete(sessionId);
    },
    [onDelete],
  );

  const panel = (
    <div
      className="hap-agent-chat-history-panel"
      style={{
        width: PANEL_WIDTH,
        maxHeight: PANEL_MAX_HEIGHT,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      <div style={{ padding: '10px 10px 8px' }}>
        <Input
          allowClear
          placeholder="Search Agents..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          variant="borderless"
          style={{
            padding: '4px 8px',
            background: 'rgba(15, 23, 42, 0.04)',
            borderRadius: 8,
            fontSize: 13,
          }}
        />
      </div>

      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '0 4px 8px' }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '24px 0' }}>
            <Spin size="small" />
          </div>
        ) : filteredItems.length === 0 ? (
          <Text style={{ display: 'block', padding: '12px 10px', fontSize: 12, color: 'rgba(17,24,39,0.45)' }}>
            {query.trim() ? 'No agents found' : 'No chat history yet'}
          </Text>
        ) : (
          <>
            {pinnedItems.length > 0 ? (
              <SessionSection
                label="Pinned"
                items={pinnedItems}
                activeSessionId={activeSessionId}
                pinnedIds={pinnedIdSet}
                onSelect={handleSelect}
                onDelete={handleDelete}
                onTogglePin={handleTogglePin}
              />
            ) : null}
            {(Object.keys(GROUP_LABELS) as SessionGroupKey[]).map((key) => (
              <SessionSection
                key={key}
                label={GROUP_LABELS[key]}
                items={groupedItems[key]}
                activeSessionId={activeSessionId}
                pinnedIds={pinnedIdSet}
                onSelect={handleSelect}
                onDelete={handleDelete}
                onTogglePin={handleTogglePin}
              />
            ))}
          </>
        )}
      </div>
    </div>
  );

  return (
    <Popover
      open={open}
      onOpenChange={onOpenChange}
      trigger="click"
      placement="bottomRight"
      arrow={false}
      destroyTooltipOnHide
      overlayClassName="hap-agent-chat-history-popover"
      overlayInnerStyle={{
        padding: 0,
        borderRadius: 12,
        boxShadow: '0 12px 40px rgba(15, 23, 42, 0.14)',
        border: '1px solid rgba(15, 23, 42, 0.08)',
      }}
      content={panel}
    >
      {children}
    </Popover>
  );
}
