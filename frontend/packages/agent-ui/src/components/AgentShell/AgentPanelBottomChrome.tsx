import React, { useMemo, useState } from 'react';
import { Button, Checkbox, Input, Space, Spin, Tag, Typography } from 'antd';
import { PlusOutlined, RightOutlined, UpOutlined } from '@ant-design/icons';
import { HAP_AGENT_THEME, statusTagStyle } from './AgentPanelTheme';
import {
  BUILTIN_STEP_PRESETS,
  ML_STEP_CATALOG,
  PRIMARY_ML_STEPS,
  type StepPreset,
  buildStepPresetLabel,
  buildStepPresetPrompt,
  isPanelOnlyStep,
} from './stepPresets';
import type { AgentQuickPreset } from './agentPresets';
import {
  type AgentCapabilitiesPayload,
  type AgentHapOperation,
  type AgentMcpTool,
  type CapabilityViewTab,
  hapOperationToPreset,
  mcpToolToPreset,
  riskLevelLabel,
} from './agentCapabilitiesView';

const { TextArea } = Input;
const { Text } = Typography;

export type BottomPanelKey = 'presets' | 'executionLog' | 'audit';

type CapabilitiesStatus = 'idle' | 'loading' | 'connected' | 'failed';

export type AgentPanelBottomChromeProps = {
  isSplitPanel: boolean;
  defaultPrompt: string;
  messageText: string;
  loading: boolean;
  loadingMessage: string;
  queuedPresetLabel: string | null;
  recentPresets: AgentQuickPreset[];
  contextPresets: AgentQuickPreset[];
  secondaryPresets: AgentQuickPreset[];
  customPresets: AgentQuickPreset[];
  onRemoveCustomPreset: (id: string) => void;
  onSaveCurrentPreset: () => void;
  userStepPresets: StepPreset[];
  onApplyStepPreset: (preset: StepPreset) => void;
  onSaveStepPreset: (stepIds: string[]) => void;
  onRemoveStepPreset: (id: string) => void;
  capabilitiesStatus: CapabilitiesStatus;
  capabilitiesData: AgentCapabilitiesPayload | null;
  capabilityTab: CapabilityViewTab;
  capabilityQuery: string;
  capabilityOperationGroups: Array<{ module: string; label: string; items: AgentHapOperation[] }>;
  capabilityQueryGroups: Array<{ domain: string; label: string; items: AgentMcpTool[] }>;
  onCapabilityTabChange: (tab: CapabilityViewTab) => void;
  onCapabilityQueryChange: (value: string) => void;
  onSelectCapabilityPreset: (preset: AgentQuickPreset) => void;
  onMessageTextChange: (value: string) => void;
  onSend: () => void;
  onStopExecution?: () => void;
  onApplyPreset: (preset: AgentQuickPreset) => void;
  onClearQueuedPreset: () => void;
  softenText: (value: string) => string;
  statusTagStyle: (tone: 'default' | 'success' | 'error') => React.CSSProperties;
  bottomPanel: BottomPanelKey | null;
  onSelectBottomPanel: (panel: BottomPanelKey) => void;
  onBottomPanelArrowClick: () => void;
  showExecutionLogTab?: boolean;
  executionLogBadge?: string;
  executionLogPanel?: React.ReactNode;
  auditPanel?: React.ReactNode;
};

function bottomTabStyle(active: boolean): React.CSSProperties {
  return {
    borderRadius: 999,
    border: `1px solid ${active ? HAP_AGENT_THEME.borderAccent : HAP_AGENT_THEME.border}`,
    background: active ? HAP_AGENT_THEME.accentSoft : HAP_AGENT_THEME.bgElevated,
    color: active ? HAP_AGENT_THEME.textAccent : HAP_AGENT_THEME.textSecondary,
    fontSize: 11,
    height: 26,
    padding: '0 10px',
    fontWeight: active ? 600 : 400,
    cursor: 'pointer',
    whiteSpace: 'nowrap' as const,
  };
}

export function AgentPanelBottomChrome({
  isSplitPanel,
  defaultPrompt,
  messageText,
  loading,
  loadingMessage,
  queuedPresetLabel,
  recentPresets,
  contextPresets = [],
  secondaryPresets = [],
  customPresets,
  onRemoveCustomPreset,
  onSaveCurrentPreset,
  userStepPresets,
  onApplyStepPreset,
  onSaveStepPreset,
  onRemoveStepPreset,
  capabilitiesStatus,
  capabilitiesData,
  capabilityTab,
  capabilityQuery,
  capabilityOperationGroups,
  capabilityQueryGroups,
  onCapabilityTabChange,
  onCapabilityQueryChange,
  onSelectCapabilityPreset,
  onMessageTextChange,
  onSend,
  onStopExecution,
  onApplyPreset,
  onClearQueuedPreset,
  softenText,
  statusTagStyle: tagStyle,
  bottomPanel,
  onSelectBottomPanel,
  onBottomPanelArrowClick,
  showExecutionLogTab = false,
  executionLogBadge,
  executionLogPanel,
  auditPanel,
}: AgentPanelBottomChromeProps) {
  const [stepPickerOpen, setStepPickerOpen] = useState(false);
  const [stepPickerShowAll, setStepPickerShowAll] = useState(false);
  const [draftStepIds, setDraftStepIds] = useState<string[]>([]);

  const pad = isSplitPanel ? '8px 12px' : '10px 16px';
  const allStepPresets = useMemo(
    () => [...BUILTIN_STEP_PRESETS, ...userStepPresets],
    [userStepPresets],
  );
  const stepCatalogForPicker = stepPickerShowAll ? ML_STEP_CATALOG : PRIMARY_ML_STEPS;

  const capabilityCount = useMemo(() => {
    const pages = capabilityOperationGroups.reduce((n, g) => n + g.items.length, 0);
    const queries = capabilityQueryGroups.reduce((n, g) => n + g.items.length, 0);
    return pages + queries;
  }, [capabilityOperationGroups, capabilityQueryGroups]);

  const presetCount =
    contextPresets.length +
    secondaryPresets.length +
    recentPresets.length +
    customPresets.length +
    allStepPresets.length +
    capabilityCount;

  const chipStyle = {
    borderRadius: 999,
    background: HAP_AGENT_THEME.bgElevated,
    borderColor: HAP_AGENT_THEME.borderAccent,
    color: HAP_AGENT_THEME.textAccent,
    fontSize: 11,
  } as const;

  const renderPresetChip = (item: AgentQuickPreset, accent?: boolean) => (
    <Button
      key={item.id}
      size="small"
      disabled={loading}
      onClick={() => onApplyPreset(item)}
      title={item.hint || item.prompt}
      style={{
        ...chipStyle,
        ...(accent
          ? {
              background: 'rgba(220, 38, 38, 0.1)',
              borderColor: 'rgba(220, 38, 38, 0.35)',
              fontWeight: 600,
            }
          : {}),
      }}
    >
      {item.label}
    </Button>
  );

  const presetSummary = queuedPresetLabel ? softenText(queuedPresetLabel) : null;

  const capabilitySummary = useMemo(() => {
    if (!capabilitiesData) return null;
    const model = capabilitiesData.agent_model;
    const parts: string[] = [];
    if (model?.model) parts.push(String(model.model));
    if (model?.thinking_enabled) parts.push('思考模式');
    if (capabilitiesData.realExecution) parts.push('正式执行');
    else parts.push('预览模式');
    return parts.join(' · ');
  }, [capabilitiesData]);

  const renderCapabilityItem = (preset: AgentQuickPreset, badge?: string) => (
    <button
      key={preset.id}
      type="button"
      onClick={() => onSelectCapabilityPreset(preset)}
      style={{
        all: 'unset',
        cursor: 'pointer',
        display: 'block',
        width: '100%',
        background: HAP_AGENT_THEME.bgMuted,
        border: `1px solid ${HAP_AGENT_THEME.border}`,
        borderRadius: 8,
        padding: '6px 10px',
        color: HAP_AGENT_THEME.textAccent,
        fontSize: 12,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
        <span>{softenText(preset.label)}</span>
        {badge ? (
          <Tag style={{ margin: 0, ...tagStyle('default'), fontSize: 10, padding: '0 6px' }}>
            {badge}
          </Tag>
        ) : null}
      </div>
      {preset.hint ? (
        <div style={{ color: HAP_AGENT_THEME.textMuted, fontSize: 11, marginTop: 2 }}>{preset.hint}</div>
      ) : null}
    </button>
  );

  const presetPanelContent = (
    <div
      data-agent-action-id="ml.skill.select"
      style={{ maxHeight: 360, overflowY: 'auto', padding: '8px 12px', overscrollBehavior: 'contain' }}
    >
      {contextPresets.length > 0 ? (
        <div style={{ marginBottom: 12 }}>
          <Text style={{ color: HAP_AGENT_THEME.textSecondary, fontSize: 11, display: 'block', marginBottom: 6 }}>
            当前页面
          </Text>
          <Space wrap size={[6, 6]}>
            {contextPresets.map((item) => renderPresetChip(item, true))}
          </Space>
        </div>
      ) : null}

      {secondaryPresets.length > 0 ? (
        <div style={{ marginBottom: 12 }}>
          <Text style={{ color: HAP_AGENT_THEME.textSecondary, fontSize: 11, display: 'block', marginBottom: 6 }}>
            平台常用
          </Text>
          <Space wrap size={[6, 6]}>
            {secondaryPresets.map((item) => renderPresetChip(item))}
          </Space>
        </div>
      ) : null}

      {recentPresets.length > 0 ? (
        <div style={{ marginBottom: 12 }}>
          <Text style={{ color: HAP_AGENT_THEME.textSecondary, fontSize: 11, display: 'block', marginBottom: 6 }}>
            最近使用
          </Text>
          <Space wrap size={[6, 6]}>
            {recentPresets.map((item) => renderPresetChip(item))}
          </Space>
        </div>
      ) : null}

      {customPresets.length > 0 ? (
        <div style={{ marginBottom: 12 }}>
          <Text style={{ color: HAP_AGENT_THEME.textSecondary, fontSize: 11, display: 'block', marginBottom: 6 }}>
            我的预设
          </Text>
          <Space wrap size={[6, 6]}>
            {customPresets.map((item) => (
              <Tag
                key={item.id}
                closable
                onClose={(e) => {
                  e.preventDefault();
                  onRemoveCustomPreset(item.id);
                }}
                onClick={() => onApplyPreset(item)}
                style={{ cursor: 'pointer', margin: 0, ...tagStyle('default'), fontSize: 11, padding: '2px 8px' }}
                title={item.prompt}
              >
                {item.label}
              </Tag>
            ))}
          </Space>
        </div>
      ) : null}

      <div style={{ marginBottom: 10 }}>
        <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 6 }}>
          <Text style={{ color: HAP_AGENT_THEME.textSecondary, fontSize: 11 }}>组合流程</Text>
          <Button
            type="link"
            size="small"
            onClick={onSaveCurrentPreset}
            style={{ padding: 0, height: 'auto', fontSize: 11, color: HAP_AGENT_THEME.textLink }}
          >
            保存当前输入为预设
          </Button>
        </Space>
        <Space wrap size={[6, 6]} style={{ marginBottom: stepPickerOpen ? 8 : 0 }}>
          {allStepPresets.map((preset) => {
            const isBuiltin = preset.id.startsWith('builtin-');
            return (
              <Tag
                key={preset.id}
                closable={!isBuiltin}
                onClose={(e) => {
                  e.preventDefault();
                  if (!isBuiltin) onRemoveStepPreset(preset.id);
                }}
                onClick={() => {
                  onApplyStepPreset(preset);
                  setStepPickerOpen(false);
                }}
                title={preset.prompt}
                style={{ cursor: 'pointer', margin: 0, ...tagStyle('default'), fontSize: 11, padding: '2px 8px' }}
              >
                {preset.label}
                <span style={{ color: HAP_AGENT_THEME.textMuted, marginLeft: 4 }}>({preset.stepIds.length})</span>
              </Tag>
            );
          })}
          <Button
            size="small"
            type="dashed"
            icon={<PlusOutlined />}
            disabled={loading}
            onClick={() => {
              setStepPickerOpen((v) => !v);
              if (!stepPickerOpen) setDraftStepIds([]);
            }}
            style={chipStyle}
          >
            自选步骤
          </Button>
        </Space>
        {stepPickerOpen ? (
          <div
            style={{
              background: HAP_AGENT_THEME.bgMuted,
              border: `1px solid ${HAP_AGENT_THEME.border}`,
              borderRadius: 8,
              padding: '8px 10px',
            }}
          >
            <Space wrap size={[8, 8]} style={{ marginBottom: 6, width: '100%', justifyContent: 'space-between' }}>
              <Checkbox
                checked={stepPickerShowAll}
                onChange={(e) => setStepPickerShowAll(e.target.checked)}
                style={{ color: HAP_AGENT_THEME.textMuted, fontSize: 11 }}
              >
                显示面板内步骤
              </Checkbox>
              <Button
                type="link"
                size="small"
                style={{ padding: 0, height: 'auto', fontSize: 11, color: HAP_AGENT_THEME.textLink }}
                onClick={() => setDraftStepIds(stepCatalogForPicker.map((s) => s.node_id))}
              >
                全选
              </Button>
              <Button
                type="link"
                size="small"
                style={{ padding: 0, height: 'auto', fontSize: 11, color: HAP_AGENT_THEME.textMuted }}
                onClick={() => setDraftStepIds([])}
              >
                清空
              </Button>
            </Space>
            <Checkbox.Group
              value={draftStepIds}
              onChange={(vals) => setDraftStepIds(vals as string[])}
              style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 140, overflowY: 'auto' }}
            >
              {stepCatalogForPicker.map((step) => (
                <Checkbox
                  key={step.node_id}
                  value={step.node_id}
                  style={{ color: HAP_AGENT_THEME.textAccent, fontSize: 11, marginInlineStart: 0 }}
                >
                  {softenText(step.label)}
                  {isPanelOnlyStep(step.node_id) ? (
                    <span style={{ color: HAP_AGENT_THEME.textMuted, marginLeft: 4 }}>面板</span>
                  ) : null}
                </Checkbox>
              ))}
            </Checkbox.Group>
            <Space style={{ marginTop: 8 }}>
              <Button
                size="small"
                type="primary"
                disabled={draftStepIds.length === 0}
                onClick={() => {
                  const ordered = ML_STEP_CATALOG.filter((s) => draftStepIds.includes(s.node_id)).map((s) => s.node_id);
                  onSaveStepPreset(ordered);
                  setStepPickerOpen(false);
                  setDraftStepIds([]);
                }}
                style={{ borderRadius: 999, fontSize: 11 }}
              >
                保存为预设
              </Button>
              <Button
                size="small"
                disabled={draftStepIds.length === 0}
                onClick={() => {
                  const ordered = ML_STEP_CATALOG.filter((s) => draftStepIds.includes(s.node_id)).map((s) => s.node_id);
                  onApplyStepPreset({
                    id: 'draft',
                    label: buildStepPresetLabel(ordered),
                    stepIds: ordered,
                    prompt: buildStepPresetPrompt(ordered),
                  });
                  setStepPickerOpen(false);
                }}
                style={{ ...chipStyle, fontSize: 11 }}
              >
                仅填入
              </Button>
            </Space>
          </div>
        ) : null}
      </div>

      {capabilitiesStatus === 'connected' && capabilitiesData ? (
        <div style={{ marginTop: 4 }}>
          <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 6 }}>
            <Text style={{ color: HAP_AGENT_THEME.textSecondary, fontSize: 11 }}>我能做什么</Text>
            {capabilitySummary ? (
              <Text style={{ color: HAP_AGENT_THEME.textMuted, fontSize: 10 }}>{capabilitySummary}</Text>
            ) : null}
          </Space>
          <Space wrap size={[6, 6]} style={{ marginBottom: 8 }}>
            {(['pages', 'queries', 'flows'] as CapabilityViewTab[]).map((tab) => (
              <Button
                key={tab}
                size="small"
                onClick={() => onCapabilityTabChange(tab)}
                style={{
                  ...chipStyle,
                  background: capabilityTab === tab ? HAP_AGENT_THEME.accentSoft : HAP_AGENT_THEME.bgElevated,
                }}
              >
                {tab === 'pages' ? '页面操作' : tab === 'queries' ? '数据查询' : '组合流程'}
              </Button>
            ))}
            {capabilityTab !== 'flows' ? (
              <input
                value={capabilityQuery}
                onChange={(e) => onCapabilityQueryChange(e.target.value)}
                placeholder="搜索"
                style={{
                  background: HAP_AGENT_THEME.inputBg,
                  color: HAP_AGENT_THEME.text,
                  border: `1px solid ${HAP_AGENT_THEME.inputBorder}`,
                  borderRadius: 8,
                  padding: '4px 10px',
                  minWidth: 120,
                  fontSize: 12,
                }}
              />
            ) : null}
          </Space>

          {capabilityTab === 'pages' ? (
            <div style={{ display: 'grid', gap: 10 }}>
              {capabilityOperationGroups.map((group) => (
                <div key={group.module}>
                  <Text style={{ color: HAP_AGENT_THEME.textMuted, fontSize: 11, display: 'block', marginBottom: 4 }}>
                    {group.label}
                  </Text>
                  <div style={{ display: 'grid', gap: 6 }}>
                    {group.items.map((op) => {
                      const preset = hapOperationToPreset(op);
                      return renderCapabilityItem(preset, riskLevelLabel(op.risk_level));
                    })}
                  </div>
                </div>
              ))}
              {capabilityOperationGroups.length === 0 ? (
                <Text style={{ color: HAP_AGENT_THEME.textMuted, fontSize: 12 }}>当前账号暂无可用页面操作</Text>
              ) : null}
            </div>
          ) : null}

          {capabilityTab === 'queries' ? (
            <div style={{ display: 'grid', gap: 10 }}>
              {capabilityQueryGroups.map((group) => (
                <div key={group.domain}>
                  <Text style={{ color: HAP_AGENT_THEME.textMuted, fontSize: 11, display: 'block', marginBottom: 4 }}>
                    {group.label}
                  </Text>
                  <div style={{ display: 'grid', gap: 6 }}>
                    {group.items.map((tool) => {
                      const preset = mcpToolToPreset(tool);
                      return renderCapabilityItem(preset, '仅查看');
                    })}
                  </div>
                </div>
              ))}
              {capabilityQueryGroups.length === 0 ? (
                <Text style={{ color: HAP_AGENT_THEME.textMuted, fontSize: 12 }}>暂无可用查询能力</Text>
              ) : null}
            </div>
          ) : null}

          {capabilityTab === 'flows' ? (
            <div style={{ display: 'grid', gap: 6 }}>
              {allStepPresets.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => onApplyStepPreset(preset)}
                  style={{
                    all: 'unset',
                    cursor: 'pointer',
                    background: HAP_AGENT_THEME.bgMuted,
                    border: `1px solid ${HAP_AGENT_THEME.border}`,
                    borderRadius: 8,
                    padding: '6px 10px',
                    color: HAP_AGENT_THEME.textAccent,
                    fontSize: 12,
                  }}
                >
                  <div>{preset.label}</div>
                  <div style={{ color: HAP_AGENT_THEME.textMuted, fontSize: 11, marginTop: 2 }}>
                    {preset.stepIds.length} 步 · {softenText(preset.prompt.slice(0, 80))}
                    {preset.prompt.length > 80 ? '…' : ''}
                  </div>
                </button>
              ))}
            </div>
          ) : null}
        </div>
      ) : capabilitiesStatus === 'loading' ? (
        <Text style={{ color: HAP_AGENT_THEME.textMuted, fontSize: 12 }}>正在加载能力目录…</Text>
      ) : capabilitiesStatus === 'failed' ? (
        <Text style={{ color: HAP_AGENT_THEME.textMuted, fontSize: 12 }}>能力目录加载失败，仍可使用上方预设</Text>
      ) : null}
    </div>
  );

  const panelBody =
    bottomPanel === 'presets'
      ? presetPanelContent
      : bottomPanel === 'executionLog'
        ? executionLogPanel
        : bottomPanel === 'audit'
          ? auditPanel
          : null;

  return (
    <div
      className="hap-agent-composer"
      style={{
        flexShrink: 0,
        margin: pad,
        border: `1px solid ${HAP_AGENT_THEME.border}`,
        borderRadius: 12,
        background: HAP_AGENT_THEME.bgComposer,
        overflow: 'hidden',
        boxShadow: HAP_AGENT_THEME.shadow,
      }}
    >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '8px 12px',
            borderBottom: bottomPanel ? `1px solid ${HAP_AGENT_THEME.border}` : undefined,
            flexWrap: 'wrap',
          }}
        >
          <button
            type="button"
            onClick={onBottomPanelArrowClick}
            aria-label={bottomPanel ? '收起面板' : '展开面板'}
            style={{
              all: 'unset',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 22,
              height: 22,
              flexShrink: 0,
            }}
          >
            {bottomPanel ? (
              <UpOutlined style={{ color: HAP_AGENT_THEME.textMuted, fontSize: 11 }} />
            ) : (
              <RightOutlined style={{ color: HAP_AGENT_THEME.textMuted, fontSize: 11 }} />
            )}
          </button>

          <button type="button" onClick={() => onSelectBottomPanel('presets')} style={bottomTabStyle(bottomPanel === 'presets')}>
            预设与能力{presetCount > 0 ? ` · ${presetCount}` : ''}
            {presetSummary ? ` · ${presetSummary}` : ''}
          </button>

          {showExecutionLogTab ? (
            <button
              type="button"
              onClick={() => onSelectBottomPanel('executionLog')}
              style={bottomTabStyle(bottomPanel === 'executionLog')}
            >
              执行日志{executionLogBadge ? ` · ${executionLogBadge}` : ''}
            </button>
          ) : null}

          {capabilitiesStatus === 'loading' ? <Spin size="small" style={{ marginLeft: 4 }} /> : null}

          <div style={{ flex: 1, minWidth: 8 }} />

          {queuedPresetLabel ? (
            <Button
              type="link"
              size="small"
              onClick={onClearQueuedPreset}
              style={{ color: HAP_AGENT_THEME.textLink, padding: 0, height: 'auto', fontSize: 11, flexShrink: 0 }}
            >
              清除已选
            </Button>
          ) : null}
        </div>

        {panelBody ? (
          <div
            style={{
              borderBottom: `1px solid ${HAP_AGENT_THEME.border}`,
              background: HAP_AGENT_THEME.bgMuted,
              maxHeight: bottomPanel === 'audit' ? 360 : 360,
              overflowY: 'auto',
              overscrollBehavior: 'contain',
            }}
          >
            {panelBody}
          </div>
        ) : null}

        <div style={{ padding: '6px 12px 8px' }}>
          <TextArea
            rows={1}
            autoSize={{ minRows: 1, maxRows: 4 }}
            value={messageText}
            onChange={(e) => onMessageTextChange(e.target.value)}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                onSend();
              }
            }}
            placeholder={defaultPrompt}
            variant="borderless"
            style={{ background: 'transparent', color: HAP_AGENT_THEME.text, padding: 0, marginBottom: 6, resize: 'none' }}
          />
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <Button
              type="primary"
              onClick={onSend}
              loading={loading}
              disabled={loading || (!messageText.trim() && !queuedPresetLabel)}
              style={{
                flex: 1,
                background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
                borderColor: HAP_AGENT_THEME.borderAccent,
                borderRadius: 999,
                boxShadow: HAP_AGENT_THEME.shadow,
                height: 32,
              }}
            >
              {loading ? loadingMessage : '发送'}
            </Button>
            {loading && onStopExecution ? (
              <button
                type="button"
                aria-label="停止"
                title="停止"
                onClick={onStopExecution}
                style={{
                  width: 32,
                  height: 32,
                  minWidth: 32,
                  padding: 0,
                  border: 'none',
                  borderRadius: '50%',
                  flexShrink: 0,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: '#98999B',
                  cursor: 'pointer',
                }}
              >
                <span
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: 2,
                    background: '#ffffff',
                    display: 'block',
                  }}
                />
              </button>
            ) : null}
          </div>
        </div>
    </div>
  );
}
