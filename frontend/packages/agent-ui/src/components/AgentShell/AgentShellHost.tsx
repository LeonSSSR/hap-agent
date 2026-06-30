import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { getToken } from '@/utils/auth';
import { AgentPanelErrorBoundary } from './AgentPanelErrorBoundary';
import { PlatformAgentPageRoot } from './PlatformAgentPageRoot';
import AgentShell from './index';
import {
  HAP_AGENT_CLOSE_EVENT,
  HAP_AGENT_OPEN_EVENT,
  openHapAgentPanel,
  readHapAgentPanelExpanded,
} from './agentPanelControl';
import './agentPanel.less';

const PANEL_WIDTH_STORAGE_KEY = 'hap-agent-panel-width';
const FAB_POSITION_STORAGE_KEY = 'hap-agent-fab-position';
const DEFAULT_PANEL_WIDTH = 420;
const MIN_PANEL_WIDTH = 320;
const MAX_PANEL_WIDTH = 720;
const FAB_INSET = 24;
const FAB_DRAG_THRESHOLD = 5;
const HAP_LOGO = '/brand/HAP-V.svg';

/** 右下角 Agent 悬浮按钮尺寸 */
const FAB_ICON_SIZE = 28;
const FAB_FONT_SIZE = 15;
const FAB_PADDING = '12px 18px 12px 14px';
const FAB_GAP = 10;

type FabPosition = { x: number; y: number };

function readFabPosition(): FabPosition | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(FAB_POSITION_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { x?: number; y?: number };
    if (Number.isFinite(parsed.x) && Number.isFinite(parsed.y)) {
      return { x: parsed.x as number, y: parsed.y as number };
    }
  } catch {
    /* ignore */
  }
  return null;
}

function clampFabPosition(x: number, y: number, width: number, height: number): FabPosition {
  const maxX = Math.max(0, window.innerWidth - width);
  const maxY = Math.max(0, window.innerHeight - height);
  return {
    x: Math.min(maxX, Math.max(0, x)),
    y: Math.min(maxY, Math.max(0, y)),
  };
}

function readPanelWidth(): number {
  if (typeof window === 'undefined') return DEFAULT_PANEL_WIDTH;
  try {
    const raw = window.localStorage.getItem(PANEL_WIDTH_STORAGE_KEY);
    const parsed = raw ? Number.parseInt(raw, 10) : NaN;
    if (Number.isFinite(parsed) && parsed >= MIN_PANEL_WIDTH && parsed <= MAX_PANEL_WIDTH) {
      return parsed;
    }
  } catch {
    /* ignore */
  }
  return DEFAULT_PANEL_WIDTH;
}

function AgentSplitLayout({ children }: { children: React.ReactNode }) {
  const [panelWidth, setPanelWidth] = useState(readPanelWidth);
  const [expanded, setExpanded] = useState(readHapAgentPanelExpanded);
  const [resizing, setResizing] = useState(false);
  const [fabPosition, setFabPosition] = useState<FabPosition | null>(null);
  const [draggingFab, setDraggingFab] = useState(false);
  const resizeRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const fabRef = useRef<HTMLButtonElement | null>(null);
  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    originX: number;
    originY: number;
    moved: boolean;
  } | null>(null);
  const authed = typeof window !== 'undefined' && !!getToken();

  const persistPanelWidth = useCallback((width: number) => {
    try {
      window.localStorage.setItem(PANEL_WIDTH_STORAGE_KEY, String(width));
    } catch {
      /* ignore */
    }
  }, []);

  const persistFabPosition = useCallback((pos: FabPosition) => {
    try {
      window.localStorage.setItem(FAB_POSITION_STORAGE_KEY, JSON.stringify(pos));
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    const onOpen = () => setExpanded(true);
    const onClose = () => setExpanded(false);
    window.addEventListener(HAP_AGENT_OPEN_EVENT, onOpen);
    window.addEventListener(HAP_AGENT_CLOSE_EVENT, onClose);
    return () => {
      window.removeEventListener(HAP_AGENT_OPEN_EVENT, onOpen);
      window.removeEventListener(HAP_AGENT_CLOSE_EVENT, onClose);
    };
  }, []);

  useEffect(() => {
    if (!resizing) return;
    const onMouseMove = (event: MouseEvent) => {
      if (!resizeRef.current) return;
      const delta = resizeRef.current.startX - event.clientX;
      const next = Math.min(MAX_PANEL_WIDTH, Math.max(MIN_PANEL_WIDTH, resizeRef.current.startWidth + delta));
      setPanelWidth(next);
    };
    const onMouseUp = () => {
      setResizing(false);
      if (resizeRef.current) persistPanelWidth(panelWidth);
      resizeRef.current = null;
    };
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, [panelWidth, persistPanelWidth, resizing]);

  useLayoutEffect(() => {
    if (expanded) return;
    const el = fabRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const saved = readFabPosition();
    if (saved) {
      setFabPosition(clampFabPosition(saved.x, saved.y, rect.width, rect.height));
      return;
    }
    setFabPosition((prev) => (prev != null ? prev : { x: rect.left, y: rect.top }));
  }, [expanded]);

  useEffect(() => {
    if (!fabPosition || expanded) return;
    const onResize = () => {
      const el = fabRef.current;
      if (!el) return;
      setFabPosition((prev) => (prev ? clampFabPosition(prev.x, prev.y, el.offsetWidth, el.offsetHeight) : prev));
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [expanded, fabPosition]);

  const handleResizeStart = (event: React.MouseEvent) => {
    event.preventDefault();
    resizeRef.current = { startX: event.clientX, startWidth: panelWidth };
    setResizing(true);
  };

  const handleFabPointerDown = (event: React.PointerEvent<HTMLButtonElement>) => {
    if (!fabPosition) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: fabPosition.x,
      originY: fabPosition.y,
      moved: false,
    };
  };

  const handleFabPointerMove = (event: React.PointerEvent<HTMLButtonElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (!drag.moved && Math.hypot(dx, dy) < FAB_DRAG_THRESHOLD) return;
    drag.moved = true;
    setDraggingFab(true);
    const el = fabRef.current;
    const width = el?.offsetWidth ?? 0;
    const height = el?.offsetHeight ?? 0;
    setFabPosition(clampFabPosition(drag.originX + dx, drag.originY + dy, width, height));
  };

  const handleFabPointerUp = (event: React.PointerEvent<HTMLButtonElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (drag.moved && fabPosition) {
      persistFabPosition(fabPosition);
    } else if (!drag.moved) {
      openHapAgentPanel();
    }
    dragRef.current = null;
    setDraggingFab(false);
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      /* ignore */
    }
  };

  if (!authed) {
    return <>{children}</>;
  }

  return (
    <div
      className="hap-agent-split-root"
      style={{
        display: 'flex',
        width: '100%',
        height: 'calc(100vh - 56px)',
        position: 'relative',
        userSelect: resizing ? 'none' : undefined,
      }}
    >
      <main style={{ flex: 1, minWidth: 0, overflow: 'auto' }}>
        <PlatformAgentPageRoot>{children}</PlatformAgentPageRoot>
      </main>

      {expanded ? (
        <>
          <div
            role="separator"
            aria-orientation="vertical"
            onMouseDown={handleResizeStart}
            style={{
              width: 6,
              cursor: 'col-resize',
              flexShrink: 0,
              background: resizing
                ? 'linear-gradient(90deg, transparent, rgba(220,38,38,0.45), transparent)'
                : 'linear-gradient(90deg, transparent, rgba(15,23,42,0.08), transparent)',
            }}
          />
          <aside
            className="hap-agent-panel-expanded"
            style={{
              width: panelWidth,
              flexShrink: 0,
              display: 'flex',
              flexDirection: 'column',
              height: '100%',
              borderLeft: '1px solid rgba(220, 38, 38, 0.14)',
              background: 'rgba(255, 255, 255, 0.68)',
              backdropFilter: 'blur(18px) saturate(135%)',
              WebkitBackdropFilter: 'blur(18px) saturate(135%)',
              boxShadow: '-4px 0 24px rgba(15, 23, 42, 0.06)',
              overflow: 'hidden',
            }}
          >
            <div
              className="hap-agent-panel-body"
              style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
            >
              <AgentPanelErrorBoundary>
                <AgentShell variant="split" />
              </AgentPanelErrorBoundary>
            </div>
          </aside>
        </>
      ) : null}

      {!expanded ? (
        <button
          ref={fabRef}
          type="button"
          className="hap-agent-fab"
          aria-label="打开 Agent"
          onPointerDown={handleFabPointerDown}
          onPointerMove={handleFabPointerMove}
          onPointerUp={handleFabPointerUp}
          onPointerCancel={handleFabPointerUp}
          style={{
            position: 'fixed',
            ...(fabPosition
              ? { left: fabPosition.x, top: fabPosition.y, right: 'auto', bottom: 'auto' }
              : { right: FAB_INSET, bottom: FAB_INSET }),
            zIndex: 1100,
            display: 'flex',
            alignItems: 'center',
            gap: FAB_GAP,
            padding: FAB_PADDING,
            border: '1px solid rgba(220, 38, 38, 0.35)',
            borderRadius: 999,
            background: 'rgba(255, 255, 255, 0.96)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            boxShadow: draggingFab
              ? '0 12px 32px rgba(15, 23, 42, 0.24)'
              : '0 8px 28px rgba(15, 23, 42, 0.18)',
            cursor: draggingFab ? 'grabbing' : 'grab',
            touchAction: 'none',
            userSelect: 'none',
            color: '#000000',
            fontWeight: 600,
            fontSize: FAB_FONT_SIZE,
            lineHeight: 1.2,
          }}
        >
          <img
            src={HAP_LOGO}
            alt=""
            aria-hidden
            style={{ width: FAB_ICON_SIZE, height: FAB_ICON_SIZE, display: 'block', flexShrink: 0 }}
          />
          <span>Agent</span>
        </button>
      ) : null}
    </div>
  );
}

export function AgentShellHost({ children }: { children: React.ReactNode }) {
  return <AgentSplitLayout>{children}</AgentSplitLayout>;
}
