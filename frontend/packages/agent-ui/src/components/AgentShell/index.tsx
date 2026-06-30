import { history, useModel } from '@umijs/max';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  ConfigProvider,
  Empty,
  Input,
  Space,
  Spin,
  Switch,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import { ClockCircleOutlined, CloseOutlined, PlusOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { closeHapAgentPanel } from './agentPanelControl';
import { AgentChatHistoryDropdown } from './AgentChatHistoryDropdown';
import { AgentPanelBottomChrome, type BottomPanelKey } from './AgentPanelBottomChrome';
import { AgentTraceAuditSection } from './AgentTraceAuditSection';
import { ExecutionLogPanel } from './ExecutionLogPanel';
import type { ExecutionStatus } from './agentExecutionTypes';
import { useAgentPageFeedback } from './useAgentPageFeedback';
import { runAgenticStreamSession } from './agenticStreamSession';
import { AgentClarifyBar } from './AgentClarifyBar';
import { AgentConfirmBar } from './AgentConfirmBar';
import type { AgentClarifyPending, AgentClarifyResult } from './agentClarifyTypes';
import type { AgentConfirmDecision, AgentConfirmPending } from './agentConfirmTypes';
import { AgentAssistantText } from './AgentAssistantText';
import { pickAgenticReasoning, pickAgenticTraceId, pickAgenticUnderstanding } from './agenticResponse';
import { AgentActivityBlock } from './AgentActivityBlock';
import { AgentReasoningBlock } from './AgentReasoningBlock';
import type { AgentActivity } from './agentStreamTypes';
import { useAgentSession } from './useAgentSession';
import { useAgentTrace } from './useAgentTrace';
import {
  asRecord,
  formatField,
  formatResponse,
  hasText,
  pickString,
  pickNumber,
  softenUserFacingText,
  resolveProviderPayload,
  resolveAgentResponseMeta,
} from './agentUtils';
import { riskLevelLabel, traceTypeTone } from './agentLabels';
import { renderAuditRecordList } from './agentAuditUi';

import {
  AgentConversationTurn,
  ConversationTurnShell,
  createConversationTurnId,
  HistoricalTurnOutput,
  summarizeConversationTurn,
  TurnMessageBubble,
} from './AgentConversationThread';
import {
  ConversationScrollPinHeader,
  useConversationScrollPin,
} from './AgentConversationScrollPin';
import {
  formatAgentRequestError,
  getCapabilities,
  isRequestTimeoutError,
  pickAgentUnderstandingCopy,
} from '@/services/agent';
import { AgentPageActionHint } from './AgentPageActionHint';
import {
  AUDIT_QUICK_COMMAND,
  type AgentQuickPreset,
  labelFromPrompt,
  loadCustomPresets,
  loadRecentPresets,
  pushRecentPreset,
  saveCustomPresets,
  saveRecentPresets,
} from './agentPresets';
import {
  type AgentCapabilitiesPayload,
  type CapabilityViewTab,
  filterQueryTools,
  groupOperationsByModuleAndPage,
  groupQueryToolsByDomain,
} from './agentCapabilitiesView';
import { buildInputPlaceholder } from './agentPresetCatalog';
import { buildPresetPanelModel } from './agentPresetPanel';
import { ProviderSourceTag } from './ProviderSourceTag';
import { AgentPageController } from './AgentPageController';
import {
  AGENT_PANEL_ANT_THEME,
  agentCardStyles,
  HAP_AGENT_THEME,
  planSummaryMutedStyle,
  statusTagStyle,
} from './AgentPanelTheme';
import {
  buildStepPresetLabel,
  buildStepPresetPrompt,
  loadStepPresetsFromStorage,
  saveStepPresetsToStorage,
  type StepPreset,
} from './stepPresets';
const { TextArea } = Input;
const { Paragraph, Text } = Typography;

function AgentPanelThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <ConfigProvider theme={AGENT_PANEL_ANT_THEME}>
      <div
        className="hap-agent-panel-inner"
        style={{
          flex: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          background: 'rgba(255,255,255,0.58)',
          color: HAP_AGENT_THEME.text,
        }}
      >
        {children}
      </div>
    </ConfigProvider>
  );
}

type ModuleKey =
  | 'workspace'
  | 'lineage'
  | 'data_governance'
  | 'data_processing'
  | 'model_development'
  | 'model_application'
  | 'system_management'
  | 'environment_management'
  | 'unknown';

type HapPageContext = {
  pageName: string;
  moduleKey: ModuleKey;
  description: string;
  pathname: string;
  title: string;
};

const MODULE_PAGE_NAMES: Record<ModuleKey, string> = {
  workspace: '工作台',
  lineage: '统一血缘',
  data_governance: '数据治理',
  data_processing: '数据处理',
  model_development: '模型开发',
  model_application: '模型应用',
  system_management: '系统管理',
  environment_management: '环境管理',
  unknown: '工作台',
};

const MODULE_DESCRIPTIONS: Record<ModuleKey, string> = {
  workspace: '查看平台运行情况、任务进度和操作记录。',
  lineage: '查看数据从哪里来、会影响到哪里。',
  data_governance: '管理数据质量、规则与变化提醒。',
  data_processing: '处理、清洗、标注和切分数据，执行前会请您确认。',
  model_development: '创建训练任务、查看训练进度和模型版本。',
  model_application: '发布模型、部署在线服务并查看运行状态。',
  system_management: '查看系统设置、服务健康与安全提示。',
  environment_management: '查看环境资源、服务健康与安全提示。',
  unknown: '根据您当前打开的页面提供常用操作。',
};

const MODULE_DETECT_RULES: Array<{ keywords: string[]; moduleKey: ModuleKey }> = [
  { keywords: ['统一血缘', 'lineage'], moduleKey: 'lineage' },
  { keywords: ['数据治理'], moduleKey: 'data_governance' },
  { keywords: ['数据处理'], moduleKey: 'data_processing' },
  { keywords: ['模型开发'], moduleKey: 'model_development' },
  { keywords: ['模型应用'], moduleKey: 'model_application' },
  { keywords: ['环境管理', '资源监控'], moduleKey: 'environment_management' },
  { keywords: ['系统管理', '超级管理'], moduleKey: 'system_management' },
  { keywords: ['总览', '工作台', '首页', 'dashboard', 'workbench'], moduleKey: 'workspace' },
];

/** 路由优先于侧边栏全文扫描，避免误匹配到其他菜单项文字。 */
const PATHNAME_PAGE_RULES: Array<{ pattern: RegExp; moduleKey: ModuleKey; pageName: string }> = [
  { pattern: /^\/env\/monitor\b/i, moduleKey: 'environment_management', pageName: '资源监控' },
  { pattern: /^\/env\//i, moduleKey: 'environment_management', pageName: '环境管理' },
  { pattern: /^\/lineage\b/i, moduleKey: 'lineage', pageName: '统一血缘' },
  { pattern: /^\/data-governance\b/i, moduleKey: 'data_governance', pageName: '数据治理' },
  { pattern: /^\/data-manage\b/i, moduleKey: 'data_governance', pageName: '数据治理' },
  { pattern: /^\/data-processing\b/i, moduleKey: 'data_processing', pageName: '数据处理' },
  { pattern: /^\/model-dev\b/i, moduleKey: 'model_development', pageName: '模型开发' },
  { pattern: /^\/model-app\b/i, moduleKey: 'model_application', pageName: '模型应用' },
  { pattern: /^\/system\b/i, moduleKey: 'system_management', pageName: '系统管理' },
  { pattern: /^\/super-admin\b/i, moduleKey: 'system_management', pageName: '超级管理' },
  { pattern: /^\/(home|dashboard|workbench)\/?$/i, moduleKey: 'workspace', pageName: '工作台' },
  { pattern: /^\/\/?$/i, moduleKey: 'workspace', pageName: '工作台' },
];

const detectPageFromPathname = (
  pathname: string,
): { moduleKey: ModuleKey; pageName: string } | null => {
  for (const rule of PATHNAME_PAGE_RULES) {
    if (rule.pattern.test(pathname)) {
      return { moduleKey: rule.moduleKey, pageName: rule.pageName };
    }
  }
  return null;
};

const readActiveMenuTextFromDom = (): string => {
  if (typeof document === 'undefined') return '';
  const selected: string[] = [];
  document.querySelectorAll('.ant-menu-item-selected').forEach((element) => {
    const text = (element.textContent || '').replace(/\s+/g, ' ').trim();
    if (text) selected.push(text);
  });
  if (selected.length > 0) return selected.join(' ');

  const openSubmenu = document.querySelector(
    '.ant-menu-submenu-selected > .ant-menu-submenu-title, .ant-menu-submenu-open > .ant-menu-submenu-title',
  );
  if (openSubmenu) {
    return (openSubmenu.textContent || '').replace(/\s+/g, ' ').trim();
  }
  return '';
};

const readBreadcrumbPageName = (): string => {
  if (typeof document === 'undefined') return '';
  const items = Array.from(document.querySelectorAll('.ant-breadcrumb li, .ant-breadcrumb-link'))
    .map((el) => (el.textContent || '').replace(/\s+/g, ' ').trim())
    .filter(Boolean);
  return items.length > 0 ? items[items.length - 1] : '';
};

const detectModuleKey = (pathname: string, title: string, menuText: string): ModuleKey => {
  const haystack = `${title} ${pathname} ${menuText}`.toLowerCase();
  for (const rule of MODULE_DETECT_RULES) {
    if (rule.keywords.some((keyword) => haystack.includes(keyword.toLowerCase()))) {
      return rule.moduleKey;
    }
  }
  if (pathname === '/' || /\/(home|workbench|dashboard)(\/|$)/iu.test(pathname)) {
    return 'workspace';
  }
  return 'unknown';
};

const readHapPageContext = (): HapPageContext => {
  if (typeof window === 'undefined') {
    return {
      pageName: '工作台',
      moduleKey: 'workspace',
      description: MODULE_DESCRIPTIONS.workspace,
      pathname: '',
      title: '',
    };
  }
  const pathname = window.location.pathname || '';
  const title = document.title || '';
  const menuText = readActiveMenuTextFromDom();
  const breadcrumbPageName = readBreadcrumbPageName();
  const pathMatch = detectPageFromPathname(pathname);
  const moduleKey = pathMatch?.moduleKey ?? detectModuleKey(pathname, title, menuText);
  const pageName = breadcrumbPageName || pathMatch?.pageName || menuText || MODULE_PAGE_NAMES[moduleKey];
  return {
    pageName,
    moduleKey,
    description: MODULE_DESCRIPTIONS[moduleKey],
    pathname,
    title,
  };
};

type LoadingMode = 'chat' | 'audit' | null;
type ExecutionStatus = 'idle' | 'running' | 'done' | 'error';
type CapabilitiesStatus = 'idle' | 'loading' | 'connected' | 'failed';


export type { AgentShellProps } from './agentShellTypes';
import type { AgentShellProps } from './agentShellTypes';

function AgentPanelFrame({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="hap-agent-split-panel"
      style={{
        flex: 1,
        minHeight: 0,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        background: 'transparent',
      }}
    >
      <AgentPanelThemeProvider>{children}</AgentPanelThemeProvider>
    </div>
  );
}

const AgentShell: React.FC<AgentShellProps> = ({ variant = 'split' }) => {
  const isSplitPanel = variant === 'split';
  const { initialState } = useModel('@@initialState');
  const agentPermissions = initialState?.permissions ?? [];
  const agentRoles = initialState?.roles ?? [];
  const approvedBy =
    initialState?.currentUser?.username || initialState?.currentUser?.name || undefined;
  const [pendingConfirm, setPendingConfirm] = useState<AgentConfirmPending | null>(null);
  const [pendingClarify, setPendingClarify] = useState<AgentClarifyPending | null>(null);
  const [confirmSubmitting, setConfirmSubmitting] = useState(false);
  const [clarifySubmitResetKey, setClarifySubmitResetKey] = useState(0);
  const [clarifyPostError, setClarifyPostError] = useState('');
  const [auditPanelLoading, setAuditPanelLoading] = useState(false);
  const confirmResolverRef = useRef<((decision: AgentConfirmDecision) => void) | null>(null);
  const clarifyResolverRef = useRef<((result: AgentClarifyResult) => void) | null>(null);
  const cancelPendingInteractions = useCallback(() => {
    if (clarifyResolverRef.current) {
      clarifyResolverRef.current({ answer: '', skipped: true });
      clarifyResolverRef.current = null;
    }
    if (confirmResolverRef.current) {
      confirmResolverRef.current('reject');
      confirmResolverRef.current = null;
    }
    setPendingClarify(null);
    setPendingConfirm(null);
    setConfirmSubmitting(false);
    setClarifySubmitResetKey((key) => key + 1);
    setClarifyPostError('');
  }, []);
  const resolveAgentConfirm = useCallback((pending: AgentConfirmPending) => {
    setBottomPanel('executionLog');
    return new Promise<AgentConfirmDecision>((resolve) => {
      setPendingConfirm(pending);
      confirmResolverRef.current = resolve;
    });
  }, []);
  const resolveAgentClarify = useCallback((pending: AgentClarifyPending) => {
    setBottomPanel('executionLog');
    setClarifyPostError('');
    return new Promise<AgentClarifyResult>((resolve) => {
      setPendingClarify(pending);
      clarifyResolverRef.current = resolve;
    });
  }, []);
  const handleAgentConfirmDecision = useCallback((decision: AgentConfirmDecision) => {
    setConfirmSubmitting(true);
    confirmResolverRef.current?.(decision);
    confirmResolverRef.current = null;
  }, []);
  const handleAgentClarifySubmit = useCallback((answer: string) => {
    clarifyResolverRef.current?.({ answer, skipped: false });
    clarifyResolverRef.current = null;
  }, []);
  const handleAgentClarifySkip = useCallback(() => {
    clarifyResolverRef.current?.({ answer: '', skipped: true });
    clarifyResolverRef.current = null;
  }, []);
  const handleAgentClarifyComplete = useCallback(() => {
    setPendingClarify(null);
    setClarifyPostError('');
    setClarifySubmitResetKey((key) => key + 1);
  }, []);
  const handleAgentClarifyPostFailed = useCallback((message: string) => {
    setClarifyPostError(message || '补充信息提交失败，请重试');
    setClarifySubmitResetKey((key) => key + 1);
  }, []);
  const handleAgentConfirmComplete = useCallback(() => {
    setPendingConfirm(null);
    setConfirmSubmitting(false);
  }, []);
  const handleAgentConfirmPostFailed = useCallback(() => {
    setConfirmSubmitting(false);
  }, []);
  const [open] = useState(true);
  const [messageText, setMessageText] = useState('');
  /** 已选预设/技能：仅发送时使用，不写入输入框 */
  const [composerQueue, setComposerQueue] = useState<AgentQuickPreset | null>(null);
  const [recentPresets, setRecentPresets] = useState<AgentQuickPreset[]>(() => loadRecentPresets());
  const [loadingMode, setLoadingMode] = useState<LoadingMode>(null);
  const [error, setError] = useState('');
  const resetExecutionRef = useRef<() => void>(() => {});
  const [capabilitiesStatus, setCapabilitiesStatus] = useState<CapabilitiesStatus>('idle');
  const [capabilitiesData, setCapabilitiesData] = useState<AgentCapabilitiesPayload | null>(null);
  const [capabilityTab, setCapabilityTab] = useState<CapabilityViewTab>(() => {
    if (typeof window === 'undefined') return 'pages';
    try {
      const saved = window.localStorage.getItem('hap-agent-capability-tab') as CapabilityViewTab | null;
      return saved === 'queries' ? 'queries' : 'pages';
    } catch {
      return 'pages';
    }
  });
  const [lastUserMessage, setLastUserMessage] = useState('');
  const {
    sessionId,
    setSessionId,
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
  } = useAgentSession({
    enabled: open,
    resetExecutionState: () => resetExecutionRef.current(),
    setError,
  });

  const activeTurn = useMemo(() => {
    if (!conversationTurns.length) return null;
    if (activeTurnId) {
      return (
        conversationTurns.find((turn) => turn.id === activeTurnId)
        ?? conversationTurns[conversationTurns.length - 1]
      );
    }
    return conversationTurns[conversationTurns.length - 1];
  }, [conversationTurns, activeTurnId]);

  const understanding = useMemo(
    () => pickAgenticUnderstanding(activeTurn?.response ?? response),
    [activeTurn?.response, response],
  );
  const reasoning = useMemo(
    () => pickAgenticReasoning(activeTurn?.response ?? response),
    [activeTurn?.response, response],
  );
  const activeActivities = useMemo(() => {
    const flat = asRecord(activeTurn?.response ?? response);
    const agentRun = flat?.agentRun as { activities?: AgentActivity[] } | undefined;
    return Array.isArray(agentRun?.activities) ? agentRun.activities : [];
  }, [activeTurn?.response, response]);
  const currentTraceId = useMemo(
    () => pickAgenticTraceId(activeTurn?.response) || pickAgenticTraceId(response),
    [activeTurn?.response, response],
  );
  const {
    auditRecords,
    auditError,
    auditLoaded,
    planAuditRecords,
    planAuditError,
    planAuditLoaded,
    planAuditLoading,
    traceView,
    traceLoading,
    traceError,
    selectedTraceIndex,
    setSelectedTraceIndex,
    traceEventFilter,
    setTraceEventFilter,
    traceStatusFilter,
    setTraceStatusFilter,
    collapsedTraceGroups,
    toggleTraceGroup,
    traceItemsSorted,
    traceGroups,
    filteredTraceGroups,
    fetchTraceView,
    fetchGlobalAudits,
    compensationLoading,
    compensationMessage,
    triggerCompensation,
    hasTraceContext,
    refreshTraceContext,
  } = useAgentTrace(currentTraceId);
  const conversationEndRef = useRef<HTMLDivElement | null>(null);
  const conversationScrollRef = useRef<HTMLDivElement | null>(null);
  const turnRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const [customPresets, setCustomPresets] = useState<AgentQuickPreset[]>(() => loadCustomPresets());
  const persistCustomPresets = useCallback((next: AgentQuickPreset[]) => {
    setCustomPresets(next);
    saveCustomPresets(next);
  }, []);
  const handleSaveCurrentPreset = useCallback(() => {
    const prompt = (messageText || '').trim() || composerQueue?.prompt?.trim() || '';
    if (!prompt) {
      message.warning('请先输入内容，或点选一个预设/技能后再保存');
      return;
    }
    const id = `cp-${Date.now().toString(36)}`;
    const entry: AgentQuickPreset = {
      id,
      label: labelFromPrompt(prompt),
      prompt,
      group: 'custom',
    };
    const next = [entry, ...customPresets.filter((p) => p.prompt !== prompt)];
    persistCustomPresets(next);
    message.success('已保存为自定义预设');
  }, [messageText, composerQueue, customPresets, persistCustomPresets]);
  const handleRemoveCustomPreset = useCallback(
    (id: string) => {
      persistCustomPresets(customPresets.filter((p) => p.id !== id));
    },
    [customPresets, persistCustomPresets],
  );
  const [userStepPresets, setUserStepPresets] = useState<StepPreset[]>(() => loadStepPresetsFromStorage());
  const persistUserStepPresets = useCallback((next: StepPreset[]) => {
    setUserStepPresets(next);
    saveStepPresetsToStorage(next);
  }, []);
  const handleSaveStepPreset = useCallback(
    (stepIds: string[]) => {
      if (stepIds.length === 0) {
        message.warning('请至少选择一个步骤');
        return;
      }
      const prompt = buildStepPresetPrompt(stepIds);
      const label = buildStepPresetLabel(stepIds);
      const id = `sp-${Date.now().toString(36)}`;
      const signature = stepIds.join('|');
      const next = [
        { id, label, stepIds, prompt },
        ...userStepPresets.filter((p) => p.stepIds.join('|') !== signature),
      ].slice(0, 10);
      persistUserStepPresets(next);
      message.success(`已保存步骤预设「${label}」`);
    },
    [userStepPresets, persistUserStepPresets],
  );
  const handleRemoveStepPreset = useCallback(
    (id: string) => {
      persistUserStepPresets(userStepPresets.filter((p) => p.id !== id));
    },
    [userStepPresets, persistUserStepPresets],
  );
  const [hapPageContext, setHapPageContext] = useState<HapPageContext>(() => readHapPageContext());
  const [bottomPanel, setBottomPanel] = useState<BottomPanelKey | null>(null);
  const rememberRecentPreset = useCallback((preset: AgentQuickPreset) => {
    setRecentPresets((prev) => pushRecentPreset(prev, preset));
  }, []);
  const applyComposerPrompt = useCallback((preset: AgentQuickPreset) => {
    setComposerQueue(preset);
    setMessageText(preset.prompt);
    setBottomPanel(null);
    rememberRecentPreset(preset);
  }, [rememberRecentPreset]);

  const handleApplyStepPreset = useCallback(
    (preset: StepPreset) => {
      applyComposerPrompt({
        id: preset.id,
        label: preset.label,
        prompt: preset.prompt,
        group: 'context',
      });
    },
    [applyComposerPrompt],
  );
  const [capabilityQuery, setCapabilityQuery] = useState('');

  useEffect(() => {
    if (typeof window === 'undefined') return;
    saveRecentPresets(recentPresets);
  }, [recentPresets]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
    } catch {
      /* 不再持久化技能指令到输入框 */
    }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem('hap-agent-capability-tab', capabilityTab);
    } catch {
      // ignore persistence errors
    }
  }, [capabilityTab]);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const refreshPageContext = () => {
      window.requestAnimationFrame(() => {
        setHapPageContext(readHapPageContext());
      });
    };
    refreshPageContext();
    return history.listen(refreshPageContext);
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    setHapPageContext(readHapPageContext());

    let cancelled = false;

    const loadCapabilities = async () => {
      setCapabilitiesStatus('loading');
      try {
        const res = await getCapabilities();
        if (cancelled) return;
        const data = (res?.data ?? res) as AgentCapabilitiesPayload;
        setCapabilitiesData(data);
        setCapabilitiesStatus('connected');
      } catch {
        if (cancelled) return;
        setCapabilitiesData(null);
        setCapabilitiesStatus('failed');
      }
    };

    loadCapabilities();

    return () => {
      cancelled = true;
    };
  }, [open]);

  const loading = loadingMode === 'chat';
  const loadingMessage = 'Agent 正在处理您的请求...';

  const traceItems = traceItemsSorted;

  const syncActiveTurnResponse = useCallback(
    (updater: any) => {
      setResponse(updater);
      setConversationTurns((prev) =>
        prev.map((turn) => {
          if (turn.id !== activeTurnId) return turn;
          const nextResponse = typeof updater === 'function' ? updater(turn.response) : updater;
          return { ...turn, response: nextResponse, status: 'done', error: '' };
        }),
      );
    },
    [activeTurnId, setConversationTurns, setResponse],
  );

  const agentStreamAbortRef = useRef<AbortController | null>(null);
  const [executionLogs, setExecutionLogs] = useState<string[]>([]);
  const [executionError, setExecutionError] = useState('');
  const [executionStatus, setExecutionStatus] = useState<ExecutionStatus>('idle');
  const {
    pageActionHint,
    setPageActionHint,
    pageActionErrors,
    setPageActionErrors,
    resetPageFeedback,
  } = useAgentPageFeedback();

  const resetExecutionState = useCallback(() => {
    agentStreamAbortRef.current?.abort();
    agentStreamAbortRef.current = null;
    cancelPendingInteractions();
    setExecutionError('');
    setExecutionLogs([]);
    setExecutionStatus('idle');
    resetPageFeedback();
    AgentPageController.clearHighlight();
  }, [cancelPendingInteractions, resetPageFeedback]);

  useEffect(() => {
    resetExecutionRef.current = resetExecutionState;
  }, [resetExecutionState]);

  const handleStopExecution = useCallback(() => {
    agentStreamAbortRef.current?.abort();
    agentStreamAbortRef.current = null;
    cancelPendingInteractions();
    setExecutionStatus('idle');
    setExecutionLogs((prev) => [...prev, '⏹ 已手动停止']);
    setLoadingMode((prev) => (prev === 'chat' ? null : prev));
    setConversationTurns((prev) =>
      prev.map((turn) =>
        turn.status === 'loading' ? { ...turn, status: 'error' as const, error: '已手动停止' } : turn,
      ),
    );
  }, [cancelPendingInteractions]);

  const showExecutionPanel =
    executionStatus !== 'idle' ||
    executionLogs.length > 0 ||
    Boolean(executionError);

  useEffect(() => {
    if (executionStatus === 'running') {
      setBottomPanel('executionLog');
    }
  }, [executionStatus]);

  const selectedTraceItem = selectedTraceIndex != null ? traceItemsSorted[selectedTraceIndex] : null;

  const responseMeta = useMemo(() => resolveAgentResponseMeta(response), [response]);

  const capabilityOperations = useMemo(
    () => (Array.isArray(capabilitiesData?.hap_operations) ? capabilitiesData.hap_operations : []),
    [capabilitiesData?.hap_operations],
  );

  const capabilityQueryTools = useMemo(
    () => filterQueryTools(Array.isArray(capabilitiesData?.mcp_tools) ? capabilitiesData.mcp_tools : []),
    [capabilitiesData?.mcp_tools],
  );

  const capabilityOperationGroups = useMemo(
    () => groupOperationsByModuleAndPage(capabilityOperations, capabilityQuery),
    [capabilityOperations, capabilityQuery],
  );

  const capabilityQueryGroups = useMemo(() => {
    const query = capabilityQuery.trim().toLowerCase();
    const groups = groupQueryToolsByDomain(capabilityQueryTools);
    if (!query) return groups;
    return groups
      .map((group) => ({
        ...group,
        items: group.items.filter(
          (tool) =>
            tool.tool_name.toLowerCase().includes(query)
            || String(tool.title || '').toLowerCase().includes(query)
            || String(tool.description || '').toLowerCase().includes(query),
        ),
      }))
      .filter((group) => group.items.length > 0);
  }, [capabilityQueryTools, capabilityQuery]);
  const inputPlaceholder = useMemo(
    () => buildInputPlaceholder(hapPageContext, capabilitiesData),
    [hapPageContext, capabilitiesData],
  );

  const presetPanel = useMemo(
    () => buildPresetPanelModel(hapPageContext, capabilitiesData),
    [hapPageContext, capabilitiesData],
  );

  const hasWorkflowOutput = conversationTurns.length > 0 || loadingMode === 'chat';

  const historicalTurns = useMemo(
    () => (activeTurn ? conversationTurns.filter((turn) => turn.id !== activeTurn.id) : conversationTurns),
    [conversationTurns, activeTurn],
  );

  const setTurnRef = useCallback(
    (turnId: string) => (node: HTMLDivElement | null) => {
      if (node) turnRefs.current.set(turnId, node);
      else turnRefs.current.delete(turnId);
    },
    [],
  );

  const { pinnedTurn, scrollPinVisible, updateScrollPin, scrollToTurn } = useConversationScrollPin(
    conversationTurns,
    conversationScrollRef,
    turnRefs,
  );

  const handleConversationScroll = useCallback(() => {
    updateScrollPin();
  }, [updateScrollPin]);

  const toggleTurnCollapsed = useCallback((turnId: string) => {
    setConversationTurns((prev) =>
      prev.map((turn) => (turn.id === turnId ? { ...turn, collapsed: !turn.collapsed } : turn)),
    );
  }, []);

  const handleRecallTurn = useCallback(
    (turnId: string) => {
      const turnIndex = conversationTurns.findIndex((turn) => turn.id === turnId);
      if (turnIndex < 0) return;

      const recalledTurn = conversationTurns[turnIndex];
      const wasLoading =
        (recalledTurn.status === 'loading' || loadingMode === 'chat')
        && turnId === conversationTurns[conversationTurns.length - 1]?.id;

      if (wasLoading) {
        agentStreamAbortRef.current?.abort();
        agentStreamAbortRef.current = null;
        cancelPendingInteractions();
        setLoadingMode(null);
      }

      const remaining = conversationTurns.slice(0, turnIndex);
      const prevTurn = remaining[remaining.length - 1] ?? null;

      setConversationTurns(remaining);
      setActiveTurnId(prevTurn?.id ?? null);
      setResponse(prevTurn?.response ?? null);
      setError('');
      setMessageText(recalledTurn.userMessage.trim());
      setComposerQueue(null);
      resetExecutionState();

      if (sessionId) {
        void persistCurrentSession(remaining, sessionId).catch(() => {});
      }

      message.success('已撤回');
    },
    [
      cancelPendingInteractions,
      conversationTurns,
      loadingMode,
      persistCurrentSession,
      resetExecutionState,
      sessionId,
    ],
  );

  const pickResponseSummary = useCallback((turnResponse: any) => {
    if (!turnResponse) return '';
    const flat =
      turnResponse && typeof turnResponse === 'object'
        ? (turnResponse as Record<string, unknown>)
        : null;
    const providerPayload = resolveProviderPayload(turnResponse);
    const copy = pickAgentUnderstandingCopy(flat) || pickString(providerPayload?.summary);
    return softenUserFacingText(copy);
  }, []);

  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    requestAnimationFrame(() => updateScrollPin());
  }, [conversationTurns.length, activeTurnId, loadingMode, updateScrollPin]);

  const handleFetchAudits = useCallback(async () => {
    setAuditPanelLoading(true);
    try {
      await fetchGlobalAudits();
    } catch (e: any) {
      message.error(e?.message || '操作记录加载失败');
    } finally {
      setAuditPanelLoading(false);
    }
  }, [fetchGlobalAudits]);

  const handleSelectBottomPanel = useCallback(
    (panel: BottomPanelKey) => {
      setBottomPanel((prev) => {
        const next = prev === panel ? null : panel;
        if (next === 'audit') {
          if (hasTraceContext) {
            refreshTraceContext();
          } else if (!auditLoaded) {
            void handleFetchAudits();
          }
        }
        return next;
      });
    },
    [auditLoaded, hasTraceContext, refreshTraceContext, handleFetchAudits],
  );

  const handleBottomPanelArrowClick = useCallback(() => {
    setBottomPanel((prev) => (prev ? null : 'presets'));
  }, []);

  const bottomAuditPanel = useMemo(
    () => (
      <div style={{ padding: '8px 12px' }} data-agent-action-id="ml.audit">
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
          <Button
            type="link"
            size="small"
            loading={auditPanelLoading || planAuditLoading}
            onClick={() => {
              if (hasTraceContext) {
                refreshTraceContext();
              } else {
                void handleFetchAudits();
              }
            }}
            style={{ padding: 0, height: 'auto', fontSize: 11, color: '#dc2626' }}
          >
            刷新
          </Button>
        </div>
        {hasTraceContext ? (
          <>
            {planAuditLoading && !planAuditLoaded ? (
              <div style={{ textAlign: 'center', padding: '8px 0' }}>
                <Spin size="small" />
              </div>
            ) : null}
            {planAuditError ? <Alert showIcon type="error" message={planAuditError} style={{ marginBottom: 8 }} /> : null}
            {!planAuditError && planAuditLoaded && planAuditRecords.length === 0 ? (
              <Text style={{ fontSize: 12, color: 'rgba(17,24,39,0.55)' }}>暂无本次操作记录。</Text>
            ) : null}
            {planAuditRecords.length > 0 ? renderAuditRecordList(planAuditRecords) : null}
            <AgentTraceAuditSection
              traceId={currentTraceId || ''}
              traceView={traceView}
              traceLoading={traceLoading}
              traceError={traceError}
              traceItems={traceItems}
              traceGroups={traceGroups}
              filteredTraceGroups={filteredTraceGroups}
              traceEventFilter={traceEventFilter}
              traceStatusFilter={traceStatusFilter}
              onTraceEventFilterChange={setTraceEventFilter}
              onTraceStatusFilterChange={setTraceStatusFilter}
              collapsedTraceGroups={collapsedTraceGroups}
              onToggleTraceGroup={toggleTraceGroup}
              selectedTraceIndex={selectedTraceIndex}
              onSelectTraceIndex={setSelectedTraceIndex}
              selectedTraceItem={selectedTraceItem}
              onRefreshTrace={() => refreshTraceContext()}
              onTriggerCompensation={() => void triggerCompensation()}
              compensationLoading={compensationLoading}
              compensationMessage={compensationMessage}
              formatField={formatField}
              formatResponse={formatResponse}
            />
          </>
        ) : (
          <>
            {auditError ? <Alert showIcon type="error" message={auditError} style={{ marginBottom: 8 }} /> : null}
            {!auditLoaded && !auditError ? (
              <Text style={{ fontSize: 12, color: 'rgba(17,24,39,0.55)' }}>点击「刷新」加载最近操作记录。</Text>
            ) : null}
            {auditLoaded && !auditError && auditRecords.length === 0 ? (
              <Text style={{ fontSize: 12, color: 'rgba(17,24,39,0.55)' }}>暂无最近操作记录。</Text>
            ) : null}
            {auditRecords.length > 0 ? renderAuditRecordList(auditRecords) : null}
          </>
        )}
      </div>
    ),
    [
      auditError,
      auditLoaded,
      auditRecords,
      collapsedTraceGroups,
      hasTraceContext,
      currentTraceId,
      filteredTraceGroups,
      formatField,
      formatResponse,
      handleFetchAudits,
      loadingMode,
      planAuditError,
      planAuditLoaded,
      planAuditLoading,
      planAuditRecords,
      refreshTraceContext,
      selectedTraceIndex,
      selectedTraceItem,
      traceError,
      traceEventFilter,
      traceGroups,
      traceItems,
      traceLoading,
      traceStatusFilter,
      traceView,
    ],
  );

  const handleMessageTextChange = (value: string) => {
    setMessageText(value);
    if (value.trim() !== (composerQueue?.prompt || '').trim()) {
      setComposerQueue(null);
    }
  };

  const handleApplyPreset = useCallback(
    (preset: AgentQuickPreset) => {
      applyComposerPrompt(preset);
      if (preset.action === 'audit' || preset.prompt === AUDIT_QUICK_COMMAND) {
        void handleFetchAudits();
        setBottomPanel('audit');
      }
    },
    [applyComposerPrompt, handleFetchAudits],
  );

  const handleSend = async (contentText = messageText) => {
    if (loadingMode === 'chat') {
      return;
    }
    const content = (contentText || messageText || composerQueue?.prompt || '').trim();
    if (!content) {
      message.warning('请输入问题');
      return;
    }
    if (content === AUDIT_QUICK_COMMAND) {
      handleFetchAudits();
      return;
    }
    const turnId = createConversationTurnId();
    setConversationTurns((prev) => [
      ...prev.map((turn) => ({ ...turn, collapsed: true })),
      {
        id: turnId,
        userMessage: content,
        response: null,
        error: '',
        status: 'loading',
        collapsed: false,
      },
    ]);
    setActiveTurnId(turnId);
    setComposerQueue(null);
    setLoadingMode('chat');
    setError('');
    setResponse(null);
    resetPageFeedback();
    setExecutionLogs([]);
    setExecutionError('');
    setExecutionStatus('running');
    setBottomPanel('executionLog');
    cancelPendingInteractions();
    agentStreamAbortRef.current?.abort();
    const streamAbort = new AbortController();
    agentStreamAbortRef.current = streamAbort;
    setLastUserMessage(content);
    setMessageText('');
    AgentPageController.clearHighlight();
    try {
      const { sessionId: activeSessionId, payload } = await runAgenticStreamSession({
        message: content,
        sessionId,
        signal: streamAbort.signal,
        callbacks: {
          onExecutionLog: (line) => setExecutionLogs((prev) => [...prev, line]),
          onPageActionHint: setPageActionHint,
          onPageActionHintClear: () => setPageActionHint(null),
          onPageActionError: (line) => setPageActionErrors((prev) => [...prev, line]),
          onConfirmRequired: resolveAgentConfirm,
          onClarificationRequired: resolveAgentClarify,
          onClarificationComplete: handleAgentClarifyComplete,
          onClarificationPostFailed: handleAgentClarifyPostFailed,
          onConfirmComplete: handleAgentConfirmComplete,
          onConfirmPostFailed: handleAgentConfirmPostFailed,
          approvedBy,
          onTurnSync: (partial, status) => {
            setConversationTurns((prev) =>
              prev.map((turn) =>
                turn.id === turnId ? { ...turn, response: partial, status } : turn,
              ),
            );
            if (status === 'done') setResponse(partial);
          },
        },
      });
      if (streamAbort.signal.aborted) {
        setExecutionStatus('idle');
        setConversationTurns((prev) =>
          prev.map((turn) =>
            turn.id === turnId
              ? { ...turn, status: 'error' as const, error: '已手动停止' }
              : turn,
          ),
        );
        return;
      }
      setExecutionStatus('done');
      if (activeSessionId !== sessionId) {
        setSessionId(activeSessionId);
      }
      setConversationTurns((prev) => {
        const completedTurns = prev.map((turn) =>
          turn.id === turnId
            ? { ...turn, response: payload, status: 'done' as const }
            : turn,
        );
        void persistCurrentSession(completedTurns, activeSessionId).catch(() => {
          /* 会话落盘失败不阻断主流程，后端 run/stream 仍会记录简要记忆 */
        });
        return completedTurns;
      });
      setResponse(payload);
    } catch (e: any) {
      const aborted = streamAbort.signal.aborted
        || (e instanceof Error && e.name === 'AbortError')
        || (e instanceof DOMException && e.name === 'AbortError');
      if (aborted) {
        setExecutionStatus('idle');
        setConversationTurns((prev) =>
          prev.map((turn) =>
            turn.id === turnId
              ? { ...turn, status: 'error' as const, error: '已手动停止' }
              : turn,
          ),
        );
      } else {
        const errMsg = isRequestTimeoutError(e)
          ? 'Agent 响应超时。请重试，或把需求说得更简短具体。'
          : formatAgentRequestError(e);
        setExecutionError(errMsg);
        setExecutionStatus('error');
        setConversationTurns((prev) =>
          prev.map((turn) => (turn.id === turnId ? { ...turn, error: errMsg, status: 'error' } : turn)),
        );
        setError(errMsg);
        message.error(errMsg);
      }
    } finally {
      agentStreamAbortRef.current = null;
      setLoadingMode(null);
    }
  };

  const handleSaveSessionAndNew = async () => {
    try {
      const hadTurns = conversationTurns.some((turn) => turn.userMessage.trim());
      await saveCurrentSessionAndNew();
      message.success(hadTurns ? '当前会话已保存，已开始新对话' : '已开始新对话');
    } catch (e: any) {
      message.error(e?.message || '保存会话失败');
    }
  };

  const handleDeleteSession = async (targetSessionId: string) => {
    try {
      await removeSession(targetSessionId);
      message.success('会话已删除');
    } catch (e: any) {
      message.error(e?.message || '删除会话失败');
    }
  };

  const shell = (
    <>
      <AgentPageActionHint hint={pageActionErrors.length === 0 ? pageActionHint : null} />
      <div
        id="agent-shell"
        style={{ flex: 1, minHeight: 0, height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
      >
      <AgentPanelFrame>
        <div
          className="hap-agent-panel-layout"
          style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
        >
          {isSplitPanel ? (
            <div
              className="hap-agent-panel-header"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 10px',
                borderBottom: '1px solid rgba(220, 38, 38, 0.12)',
                background: 'rgba(255, 255, 255, 0.55)',
                flexShrink: 0,
              }}
            >
              <span style={{ color: '#111827', fontWeight: 600, fontSize: 13 }}>HAP Agent</span>
              <Space size={0}>
                {sessionReady && sessionId ? (
                  <Tooltip title="New Agent">
                    <Button
                      type="text"
                      size="small"
                      icon={<PlusOutlined />}
                      aria-label="New Agent"
                      onClick={() => void handleSaveSessionAndNew()}
                      style={{ color: '#FF0000', width: 24, height: 24, padding: 0 }}
                    />
                  </Tooltip>
                ) : null}
                {sessionReady ? (
                  <AgentChatHistoryDropdown
                    open={sessionListOpen}
                    onOpenChange={setSessionListOpen}
                    loading={sessionListLoading}
                    items={sessionListItems}
                    activeSessionId={sessionId}
                    onSelect={switchSession}
                    onDelete={handleDeleteSession}
                  >
                    <Button
                      type="text"
                      size="small"
                      icon={<ClockCircleOutlined />}
                      aria-label={sessionListOpen ? 'Hide Chat History' : 'Show Chat History'}
                      style={{
                        color: sessionListOpen ? '#111827' : '#FF0000',
                        width: 24,
                        height: 24,
                        padding: 0,
                        background: sessionListOpen ? 'rgba(15, 23, 42, 0.08)' : 'transparent',
                        borderRadius: 999,
                      }}
                    />
                  </AgentChatHistoryDropdown>
                ) : null}
                <Tooltip title="收起到右下角">
                  <Button
                    type="text"
                    size="small"
                    icon={<CloseOutlined />}
                    aria-label="收起到右下角"
                    onClick={closeHapAgentPanel}
                    style={{ color: 'rgba(17,24,39,0.85)', width: 24, height: 24, padding: 0 }}
                  />
                </Tooltip>
              </Space>
            </div>
          ) : null}

          <div
            ref={conversationScrollRef}
            className="hap-agent-scroll-body"
            data-agent-action-id="ml.workflow.panel"
            onScroll={handleConversationScroll}
            style={{
              flex: '1 1 0',
              minHeight: 0,
              padding: isSplitPanel ? '8px 12px 16px' : '12px 16px 16px',
              color: '#374151',
              overflowY: 'auto',
              overflowX: 'hidden',
              overscrollBehavior: 'contain',
              WebkitOverflowScrolling: 'touch',
            }}
          >
            {!hasWorkflowOutput && !loading ? (
              <Empty
                description={<span style={{ color: 'rgba(17,24,39,0.5)' }}>助手的回复和计划会显示在这里</span>}
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                style={{ marginTop: 24 }}
              />
            ) : null}

            {scrollPinVisible && pinnedTurn ? (
              <ConversationScrollPinHeader
                turn={pinnedTurn}
                onJumpToTurn={() => scrollToTurn(pinnedTurn.id)}
              />
            ) : null}

          {historicalTurns.map((turn) => (
            <ConversationTurnShell
              key={turn.id}
              turn={turn}
              rootRef={setTurnRef(turn.id)}
              summary={summarizeConversationTurn(turn, softenUserFacingText)}
              onToggleCollapsed={() => toggleTurnCollapsed(turn.id)}
              onRecall={() => handleRecallTurn(turn.id)}
            >
              <HistoricalTurnOutput
                turn={turn}
                softenText={softenUserFacingText}
                formatResponse={formatResponse}
                pickSummary={pickResponseSummary}
              />
            </ConversationTurnShell>
          ))}

          {activeTurn ? (
            <ConversationTurnShell
              turn={activeTurn}
              rootRef={setTurnRef(activeTurn.id)}
              summary={summarizeConversationTurn(activeTurn, softenUserFacingText)}
              onToggleCollapsed={() => toggleTurnCollapsed(activeTurn.id)}
              onRecall={() => handleRecallTurn(activeTurn.id)}
            >
          <>
          {loading ? (
            <Alert
              showIcon
              type="info"
              message={loadingMessage}
              style={{
                marginBottom: 16,
                background: 'rgba(220, 38, 38, 0.08)',
                border: '1px solid rgba(220, 38, 38, 0.22)',
                color: '#111827',
              }}
            />
          ) : null}

          {error ? (
            <Card
              size="small"
              bordered={false}
              style={{
                background: '#ffffff',
                border: '1px solid rgba(239, 68, 68, 0.35)',
                borderRadius: 16,
                marginBottom: 16,
              }}
              styles={agentCardStyles(14)}
              title={<span style={{ color: '#111827' }}>错误</span>}
            >
              <Paragraph style={{ marginBottom: 0, color: '#dc2626' }}>{error}</Paragraph>
            </Card>
          ) : null}

          {hasWorkflowOutput ? (
          <>
          <TurnMessageBubble role="assistant">
          <section aria-label="Agent 回复" style={{ flexShrink: 0 }} data-agent-action-id="ml.intent.parse">
            {response ? (
              <div style={{ marginBottom: 8 }}>
                <ProviderSourceTag response={response} meta={responseMeta} compact />
              </div>
            ) : null}
            {reasoning ? (
              <AgentReasoningBlock
                text={reasoning}
                softenText={softenUserFacingText}
                streaming={loadingMode === 'chat' && activeTurn?.status === 'loading'}
              />
            ) : null}
            {activeActivities.length > 0 || (loadingMode === 'chat' && activeTurn?.status === 'loading') ? (
              <div style={{ marginBottom: understanding ? 12 : 0 }}>
                <AgentActivityBlock
                  activities={activeActivities}
                  softenText={softenUserFacingText}
                  streaming={loadingMode === 'chat' && activeTurn?.status === 'loading'}
                />
              </div>
            ) : null}
            {understanding ? (
              <AgentAssistantText
                text={understanding}
                soften={softenUserFacingText}
                streaming={loadingMode === 'chat' && activeTurn?.status === 'loading'}
              />
            ) : null}
          </section>
          </TurnMessageBubble>

          </>
          ) : null}
            </>
            </ConversationTurnShell>
          ) : null}

          <div ref={conversationEndRef} />
        </div>

        {pendingClarify ? (
          <div style={{ padding: '0 12px 8px' }}>
            <AgentClarifyBar
              pending={pendingClarify}
              onSubmit={handleAgentClarifySubmit}
              onSkip={handleAgentClarifySkip}
              submitResetKey={clarifySubmitResetKey}
              postError={clarifyPostError}
            />
          </div>
        ) : null}

        {pendingConfirm ? (
          <div style={{ padding: '0 12px 8px' }} data-agent-action-id="ml.risk.evaluate">
            <div data-agent-action-id="ml.permission.check">
              <AgentConfirmBar
                pending={pendingConfirm}
                permissions={agentPermissions}
                roles={agentRoles}
                busy={confirmSubmitting}
                onApprove={() => handleAgentConfirmDecision('approve')}
                onReject={() => handleAgentConfirmDecision('reject')}
              />
            </div>
          </div>
        ) : null}

        <AgentPanelBottomChrome
          isSplitPanel={isSplitPanel}
          defaultPrompt={inputPlaceholder}
          messageText={messageText}
          loading={loading}
          loadingMessage={loadingMessage}
          queuedPresetLabel={composerQueue?.label ?? null}
          contextPresets={presetPanel.recommended}
          secondaryPresets={presetPanel.scenarios.flatMap((scenario) =>
            scenario.id === 'flows' ? [] : scenario.presets,
          )}
          recentPresets={recentPresets}
          customPresets={customPresets}
          onRemoveCustomPreset={handleRemoveCustomPreset}
          onSaveCurrentPreset={handleSaveCurrentPreset}
          userStepPresets={userStepPresets}
          onApplyStepPreset={handleApplyStepPreset}
          onSaveStepPreset={handleSaveStepPreset}
          onRemoveStepPreset={handleRemoveStepPreset}
          capabilitiesStatus={capabilitiesStatus}
          capabilitiesData={capabilitiesData}
          capabilityTab={capabilityTab}
          capabilityQuery={capabilityQuery}
          capabilityOperationGroups={capabilityOperationGroups}
          capabilityQueryGroups={capabilityQueryGroups}
          onCapabilityTabChange={setCapabilityTab}
          onCapabilityQueryChange={setCapabilityQuery}
          onSelectCapabilityPreset={applyComposerPrompt}
          onMessageTextChange={handleMessageTextChange}
          onSend={() => handleSend()}
          onStopExecution={handleStopExecution}
          onApplyPreset={handleApplyPreset}
          onClearQueuedPreset={() => {
            setComposerQueue(null);
            setMessageText('');
          }}
          softenText={softenUserFacingText}
          statusTagStyle={statusTagStyle}
          bottomPanel={bottomPanel}
          onSelectBottomPanel={handleSelectBottomPanel}
          onBottomPanelArrowClick={handleBottomPanelArrowClick}
          showExecutionLogTab={showExecutionPanel}
          executionLogBadge={
            executionStatus === 'running'
              ? '执行中'
              : executionLogs.length > 0
                ? String(executionLogs.length)
                : undefined
          }
          executionLogPanel={
            <>
              <ExecutionLogPanel
                executionStatus={executionStatus}
                executionError={executionError}
                executionLogs={executionLogs}
              />
            </>
          }
          auditPanel={bottomAuditPanel}
        />
        </div>
      </AgentPanelFrame>
    </div>
    </>
  );

  return shell;
};

export default AgentShell;
