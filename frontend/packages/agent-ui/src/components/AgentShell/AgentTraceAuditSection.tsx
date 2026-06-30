import React from 'react';
import { Alert, Button, List, Space, Spin, Tag, Typography } from 'antd';
import { planSummaryMutedStyle, statusTagStyle } from './AgentPanelTheme';

const { Text, Paragraph } = Typography;

const traceTypeTone = (eventType?: string | null): 'success' | 'error' | 'default' => {
  const normalized = String(eventType || '').toLowerCase();
  if (['tool_execution', 'workflow_state', 'workflow_runtime'].includes(normalized)) return 'success';
  if (['plan_rejected', 'error', 'failed'].includes(normalized)) return 'error';
  return 'default';
};

export type AgentTraceAuditSectionProps = {
  traceId: string;
  traceView: any;
  traceLoading: boolean;
  traceError: string;
  traceItems: any[];
  traceGroups: Array<{ key: string; title: string; items: any[] }>;
  filteredTraceGroups: Array<{ key: string; title: string; items: any[] }>;
  traceEventFilter: string;
  traceStatusFilter: string;
  onTraceEventFilterChange: (value: string) => void;
  onTraceStatusFilterChange: (value: string) => void;
  collapsedTraceGroups: Record<string, boolean>;
  onToggleTraceGroup: (key: string) => void;
  selectedTraceIndex: number | null;
  onSelectTraceIndex: (index: number) => void;
  selectedTraceItem: any;
  relatedStepIndexFromTrace: number | null;
  onJumpToRelatedStep: (index: number) => void;
  onRefreshTrace: () => void;
  formatField: (value: unknown) => string;
  formatResponse: (value: unknown) => string;
};

export const AgentTraceAuditSection: React.FC<AgentTraceAuditSectionProps> = ({
  traceId,
  traceView,
  traceLoading,
  traceError,
  traceItems,
  traceGroups,
  filteredTraceGroups,
  traceEventFilter,
  traceStatusFilter,
  onTraceEventFilterChange,
  onTraceStatusFilterChange,
  collapsedTraceGroups,
  onToggleTraceGroup,
  selectedTraceIndex,
  onSelectTraceIndex,
  selectedTraceItem,
  relatedStepIndexFromTrace,
  onJumpToRelatedStep,
  onRefreshTrace,
  formatField,
  formatResponse,
}) => (
  <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px dashed rgba(15,23,42,0.12)' }}>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
      <Text style={{ color: '#111827', fontWeight: 600, fontSize: 12 }}>Trace 与审计（高级）</Text>
      <Button type="link" size="small" onClick={onRefreshTrace} loading={traceLoading} style={{ padding: 0, height: 'auto', fontSize: 11 }}>
        刷新 Trace
      </Button>
    </div>
    <Text style={{ display: 'block', color: 'rgba(17,24,39,0.45)', fontSize: 11, marginBottom: 10 }}>
      traceId: {traceId}
    </Text>

    {traceLoading && !traceView ? (
      <div style={{ textAlign: 'center', padding: '8px 0' }}>
        <Spin size="small" />
      </div>
    ) : null}

    {traceError ? <Alert showIcon type="error" message={traceError} style={{ marginBottom: 8 }} /> : null}

    {traceView ? (
      <div>
        <Space wrap size={8} style={{ marginBottom: 8 }}>
          <Tag style={statusTagStyle('default')}>count: {formatField(traceView.count)}</Tag>
          <Tag style={statusTagStyle('default')}>workflow: {formatField(traceView.workflow_id)}</Tag>
        </Space>
        {traceItems.length > 0 ? (
          <>
            <Space wrap size={[8, 8]} style={{ marginBottom: 8 }}>
              <select
                value={traceEventFilter}
                onChange={(e) => onTraceEventFilterChange(e.target.value)}
                style={{
                  background: '#f9fafb',
                  color: '#111827',
                  border: '1px solid rgba(15,23,42,0.12)',
                  borderRadius: 8,
                  padding: '4px 8px',
                  fontSize: 11,
                }}
              >
                <option value="all">全部事件</option>
                {traceGroups.map((group) => (
                  <option key={group.key} value={group.key}>
                    {group.title}
                  </option>
                ))}
              </select>
              <select
                value={traceStatusFilter}
                onChange={(e) => onTraceStatusFilterChange(e.target.value)}
                style={{
                  background: '#f9fafb',
                  color: '#111827',
                  border: '1px solid rgba(15,23,42,0.12)',
                  borderRadius: 8,
                  padding: '4px 8px',
                  fontSize: 11,
                }}
              >
                <option value="all">全部状态</option>
                <option value="completed">completed</option>
                <option value="logged">logged</option>
                <option value="succeeded">succeeded</option>
                <option value="failed">failed</option>
                <option value="pending">pending</option>
                <option value="running">running</option>
              </select>
            </Space>
            {filteredTraceGroups.slice(0, 3).map((group) => (
              <div key={group.key} style={{ ...planSummaryMutedStyle, marginBottom: 8 }}>
                <Space wrap size={6} style={{ marginBottom: 6 }}>
                  <Tag style={statusTagStyle(traceTypeTone(group.key))}>{group.title}</Tag>
                  <Tag style={statusTagStyle('default')}>{group.items.length}</Tag>
                  <Button type="link" size="small" onClick={() => onToggleTraceGroup(group.key)} style={{ padding: 0, height: 'auto', fontSize: 11 }}>
                    {collapsedTraceGroups[group.key] ? '展开' : '收起'}
                  </Button>
                </Space>
                {!collapsedTraceGroups[group.key] ? (
                  <List
                    size="small"
                    split={false}
                    dataSource={group.items.slice(0, 4)}
                    renderItem={(item: any) => {
                      const globalIndex = traceItems.findIndex((candidate: any) => candidate === item);
                      const active = selectedTraceIndex === globalIndex;
                      return (
                        <List.Item style={{ padding: '4px 0', borderBottom: '1px dashed rgba(15,23,42,0.06)' }}>
                          <button
                            type="button"
                            onClick={() => onSelectTraceIndex(globalIndex)}
                            style={{
                              all: 'unset',
                              cursor: 'pointer',
                              display: 'block',
                              width: '100%',
                              background: active ? 'rgba(220, 38, 38, 0.08)' : 'transparent',
                              border: active ? '1px solid rgba(220, 38, 38, 0.35)' : '1px solid transparent',
                              borderRadius: 8,
                              padding: 8,
                            }}
                          >
                            <div style={{ color: '#111827', fontWeight: 600, fontSize: 12 }}>
                              {formatField(item.summary || item.message || item.action)}
                            </div>
                            <div style={{ color: 'rgba(17,24,39,0.45)', fontSize: 11, marginTop: 2 }}>
                              {formatField(item.timestamp)}
                            </div>
                          </button>
                        </List.Item>
                      );
                    }}
                  />
                ) : null}
              </div>
            ))}
            {selectedTraceItem ? (
              <div style={planSummaryMutedStyle}>
                {relatedStepIndexFromTrace != null && relatedStepIndexFromTrace >= 0 ? (
                  <Button size="small" onClick={() => onJumpToRelatedStep(relatedStepIndexFromTrace)} style={{ marginBottom: 8, borderRadius: 999, fontSize: 11 }}>
                    跳转到步骤 {relatedStepIndexFromTrace + 1}
                  </Button>
                ) : null}
                <div style={{ color: '#111827', fontWeight: 600, fontSize: 12, marginBottom: 4 }}>
                  {formatField(selectedTraceItem.summary || selectedTraceItem.action)}
                </div>
                <details>
                  <summary style={{ cursor: 'pointer', color: '#dc2626', fontSize: 11 }}>查看原始数据</summary>
                  <pre
                    style={{
                      marginTop: 8,
                      marginBottom: 0,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      fontSize: 11,
                      maxHeight: 160,
                      overflow: 'auto',
                      background: '#f9fafb',
                      padding: 8,
                      borderRadius: 8,
                    }}
                  >
                    {formatResponse(selectedTraceItem.metadata || selectedTraceItem)}
                  </pre>
                </details>
              </div>
            ) : null}
          </>
        ) : (
          <Paragraph style={{ marginBottom: 0, fontSize: 12, color: 'rgba(17,24,39,0.55)' }}>暂无 trace 事件。</Paragraph>
        )}
      </div>
    ) : !traceLoading ? (
      <Text style={{ fontSize: 12, color: 'rgba(17,24,39,0.55)' }}>执行开始后加载 Trace 链路。</Text>
    ) : null}
  </div>
);
