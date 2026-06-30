import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  getAuditTrace,
  getTraceByTraceId,
  listAudits,
  triggerTraceCompensation,
} from '@/services/agent';
import { parseAuditItems } from './agentUtils';
import type { AuditRecord } from './agentUtils';

export function useAgentTrace(currentTraceId: string | null) {
  const [auditRecords, setAuditRecords] = useState<AuditRecord[]>([]);
  const [auditError, setAuditError] = useState('');
  const [auditLoaded, setAuditLoaded] = useState(false);
  const [traceAuditRecords, setTraceAuditRecords] = useState<AuditRecord[]>([]);
  const [traceAuditError, setTraceAuditError] = useState('');
  const [traceAuditLoaded, setTraceAuditLoaded] = useState(false);
  const [traceAuditLoading, setTraceAuditLoading] = useState(false);
  const [traceView, setTraceView] = useState<any>(null);
  const [traceLoading, setTraceLoading] = useState(false);
  const [traceError, setTraceError] = useState('');
  const [selectedTraceIndex, setSelectedTraceIndex] = useState<number | null>(null);
  const [traceEventFilter, setTraceEventFilter] = useState<string>('all');
  const [traceStatusFilter, setTraceStatusFilter] = useState<string>('all');
  const [traceLinkedStepIndex, setTraceLinkedStepIndex] = useState<number | null>(null);
  const [collapsedTraceGroups, setCollapsedTraceGroups] = useState<Record<string, boolean>>({});
  const [compensationLoading, setCompensationLoading] = useState(false);
  const [compensationMessage, setCompensationMessage] = useState('');

  const fetchTraceAudits = useCallback(async (traceId: string) => {
    setTraceAuditLoading(true);
    setTraceAuditError('');
    try {
      const res = await getAuditTrace(traceId, 50);
      const items = (res as { items?: unknown[] })?.items ?? res;
      setTraceAuditRecords(parseAuditItems(items));
      setTraceAuditLoaded(true);
    } catch {
      setTraceAuditError('本次 Trace 审计加载失败。');
      setTraceAuditRecords([]);
      setTraceAuditLoaded(true);
    } finally {
      setTraceAuditLoading(false);
    }
  }, []);

  const fetchTraceView = useCallback(async (traceId: string) => {
    setTraceLoading(true);
    setTraceError('');
    setSelectedTraceIndex(null);
    try {
      const res = await getTraceByTraceId(traceId);
      setTraceView(res?.data ?? res);
    } catch {
      setTraceError('统一 trace 视图加载失败。');
      setTraceView(null);
    } finally {
      setTraceLoading(false);
    }
  }, []);

  const fetchGlobalAudits = useCallback(async () => {
    setAuditError('');
    try {
      const res = await listAudits({ limit: 20 });
      setAuditRecords(parseAuditItems(res));
      setAuditLoaded(true);
      return true;
    } catch (e: any) {
      const errMsg = e?.message || '审计记录加载失败';
      setAuditError(errMsg);
      setAuditRecords([]);
      setAuditLoaded(true);
      throw e;
    }
  }, []);

  const refreshTraceContext = useCallback(() => {
    if (!currentTraceId) return;
    void fetchTraceAudits(currentTraceId);
    void fetchTraceView(currentTraceId);
  }, [currentTraceId, fetchTraceAudits, fetchTraceView]);

  useEffect(() => {
    if (!currentTraceId) {
      setTraceAuditRecords([]);
      setTraceAuditError('');
      setTraceAuditLoaded(false);
      setTraceAuditLoading(false);
      setTraceView(null);
      setTraceError('');
      setTraceLoading(false);
      return;
    }
    refreshTraceContext();
  }, [currentTraceId, refreshTraceContext]);

  const traceItems = Array.isArray(traceView?.items) ? traceView.items : [];
  const traceItemsSorted = useMemo(
    () =>
      [...traceItems].sort((left, right) =>
        String(left.timestamp || '').localeCompare(String(right.timestamp || '')),
      ),
    [traceItems],
  );

  const traceGroups = useMemo(() => {
    const groups = new Map<string, { title: string; items: any[] }>();
    traceItemsSorted.forEach((item: any) => {
      const key = String(item?.event_type || item?.type || item?.action || 'event');
      const entry = groups.get(key) || { title: key, items: [] };
      entry.items.push(item);
      groups.set(key, entry);
    });
    return Array.from(groups.entries()).map(([key, value]) => ({ key, ...value }));
  }, [traceItemsSorted]);

  const filteredTraceGroups = useMemo(() => {
    const visibleTraceGroups = traceGroups.filter((group) => !collapsedTraceGroups[group.key]);
    return visibleTraceGroups
      .map((group) => ({
        ...group,
        items: group.items.filter((item: any) => {
          const eventType = String(item?.event_type || item?.type || item?.action || 'event');
          const status = String(item?.status || '');
          const eventOk = traceEventFilter === 'all' || eventType === traceEventFilter;
          const statusOk = traceStatusFilter === 'all' || status === traceStatusFilter;
          return eventOk && statusOk;
        }),
      }))
      .filter((group) => group.items.length > 0);
  }, [collapsedTraceGroups, traceEventFilter, traceGroups, traceStatusFilter]);

  const toggleTraceGroup = useCallback((key: string) => {
    setCollapsedTraceGroups((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const triggerCompensation = useCallback(async () => {
    const traceId = String(currentTraceId || traceView?.trace_id || '');
    if (!traceId) {
      setCompensationMessage('缺少 trace_id，无法触发补偿。');
      return;
    }
    const suggested = traceView?.observability?.compensation?.suggested_strategy;
    setCompensationLoading(true);
    setCompensationMessage('');
    try {
      await triggerTraceCompensation(traceId, {
        strategy: typeof suggested === 'string' ? suggested : undefined,
      });
      setCompensationMessage('已记录补救说明（只新增、不删除原记录）。');
      await fetchTraceView(traceId);
    } catch {
      setCompensationMessage('补偿触发失败，请检查权限与 trace 状态。');
    } finally {
      setCompensationLoading(false);
    }
  }, [currentTraceId, fetchTraceView, traceView]);

  return {
    auditRecords,
    auditError,
    auditLoaded,
    planAuditRecords: traceAuditRecords,
    planAuditError: traceAuditError,
    planAuditLoaded: traceAuditLoaded,
    planAuditLoading: traceAuditLoading,
    traceView,
    traceLoading,
    traceError,
    selectedTraceIndex,
    setSelectedTraceIndex,
    traceEventFilter,
    setTraceEventFilter,
    traceStatusFilter,
    setTraceStatusFilter,
    traceLinkedStepIndex,
    setTraceLinkedStepIndex,
    collapsedTraceGroups,
    toggleTraceGroup,
    traceItemsSorted,
    traceGroups,
    filteredTraceGroups,
    fetchTraceAudits,
    fetchTraceView,
    fetchGlobalAudits,
    refreshTraceContext,
    setAuditLoaded,
    compensationLoading,
    compensationMessage,
    triggerCompensation,
    hasTraceContext: Boolean(currentTraceId),
  };
}
