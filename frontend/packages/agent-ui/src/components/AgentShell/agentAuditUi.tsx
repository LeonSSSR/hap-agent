import React from 'react';
import { List, Space, Tag, Typography } from 'antd';
import { executionModeLabel, formatField, softenUserFacingText, type AuditRecord } from './agentUtils';
import { riskLevelLabel } from './agentLabels';

const { Text } = Typography;

export function renderAuditRecordList(records: AuditRecord[]) {
  return (
    <List
      size="small"
      dataSource={records}
      split={false}
      renderItem={(record: AuditRecord) => {
        const risk = riskLevelLabel(record.risk_level);
        return (
          <List.Item style={{ padding: '0 0 12px', border: 'none' }}>
            <div
              style={{
                width: '100%',
                background: '#f9fafb',
                border: '1px solid rgba(220, 38, 38, 0.18)',
                borderRadius: 12,
                padding: 12,
              }}
            >
              <Space wrap size={[8, 8]} style={{ marginBottom: 8 }}>
                <Tag
                  style={{
                    margin: 0,
                    background: 'rgba(220, 38, 38, 0.14)',
                    borderColor: 'rgba(220, 38, 38, 0.35)',
                    color: '#991b1b',
                  }}
                >
                  {formatField(record.action)}
                </Tag>
                <Tag color={risk.color} style={{ margin: 0 }}>
                  {risk.text}
                </Tag>
                <Tag
                  style={{
                    margin: 0,
                    background: 'rgba(15,23,42,0.06)',
                    borderColor: 'rgba(15,23,42,0.12)',
                    color: '#6b7280',
                  }}
                >
                  {formatField(record.status)}
                </Tag>
                <Tag
                  style={{
                    margin: 0,
                    background: 'rgba(15,23,42,0.06)',
                    borderColor: 'rgba(15,23,42,0.12)',
                    color: '#6b7280',
                  }}
                >
                  {executionModeLabel(record.real_execution)}
                </Tag>
              </Space>
              <div style={{ color: '#111827', fontWeight: 600, marginBottom: 6 }}>
                {softenUserFacingText(formatField(record.summary))}
              </div>
              <Text style={{ color: 'rgba(17,24,39,0.58)', fontSize: 12 }}>
                time: {formatField(record.timestamp)}
              </Text>
            </div>
          </List.Item>
        );
      }}
    />
  );
}
