import React, { useMemo } from 'react';
import { HAP_AGENT_THEME } from './AgentPanelTheme';

type AgentAssistantTextProps = {
  text: string;
  soften?: (value: string) => string;
  streaming?: boolean;
};

/** 折叠摘要等单行场景：去掉 Markdown 符号 */
export function stripMarkdownForSummary(text: string): string {
  return text
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^#{1,3}\s+/gm, '')
    .replace(/^[-*•]\s+/gm, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function normalizeStreamingMarkdown(text: string, streaming?: boolean): string {
  if (!streaming) return text;
  // 流式未闭合的 ** 先去掉尾部孤立符号，避免闪出 "**"
  return text.replace(/\*\*([^*\n]{0,48})?$/u, (_, inner: string | undefined) => (inner ? inner : ''));
}

function renderInline(text: string): React.ReactNode[] {
  const pattern = /(\*\*[^*\n]+\*\*|`[^`\n]+`)/g;
  const segments = text.split(pattern).filter((segment) => segment.length > 0);
  if (!segments.length) return [text];

  return segments.map((segment, key) => {
    if (segment.startsWith('**') && segment.endsWith('**') && segment.length > 4) {
      return (
        <strong key={key} style={{ fontWeight: 600, color: HAP_AGENT_THEME.text }}>
          {segment.slice(2, -2)}
        </strong>
      );
    }
    if (segment.startsWith('`') && segment.endsWith('`') && segment.length > 2) {
      return (
        <code
          key={key}
          style={{
            fontSize: '0.92em',
            padding: '1px 5px',
            borderRadius: 4,
            background: HAP_AGENT_THEME.preBg,
            border: `1px solid ${HAP_AGENT_THEME.preBorder}`,
          }}
        >
          {segment.slice(1, -1)}
        </code>
      );
    }
    return <span key={key}>{segment}</span>;
  });
}

function renderBulletList(items: string[], key: string): React.ReactNode {
  return (
    <ul
      key={key}
      style={{ margin: '0 0 10px', paddingLeft: 20, color: HAP_AGENT_THEME.textSecondary }}
    >
      {items.map((line, i) => (
        <li key={i} style={{ marginBottom: 4, lineHeight: 1.6 }}>
          {renderInline(line)}
        </li>
      ))}
    </ul>
  );
}

function renderNumberedList(items: string[], key: string): React.ReactNode {
  return (
    <ol
      key={key}
      style={{ margin: '0 0 10px', paddingLeft: 20, color: HAP_AGENT_THEME.textSecondary }}
    >
      {items.map((line, i) => (
        <li key={i} style={{ marginBottom: 4, lineHeight: 1.6 }}>
          {renderInline(line)}
        </li>
      ))}
    </ol>
  );
}

function isBoldHeadingLine(line: string): boolean {
  const trimmed = line.trim();
  return /^\*\*[^*\n]+\*\*:?\s*$/u.test(trimmed) || /^#{1,3}\s+\S/u.test(trimmed);
}

function renderHeadingLine(line: string, key: string): React.ReactNode {
  const trimmed = line.trim();
  const heading = trimmed.replace(/^#{1,3}\s+/, '').replace(/^\*\*([^*]+)\*\*:?\s*$/u, '$1');
  return (
    <div
      key={key}
      style={{
        fontWeight: 600,
        color: HAP_AGENT_THEME.text,
        marginBottom: 6,
        fontSize: 14,
        lineHeight: 1.5,
      }}
    >
      {renderInline(heading)}
    </div>
  );
}

function renderBlock(block: string, index: number): React.ReactNode {
  const lines = block
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
  if (!lines.length) return null;

  const nodes: React.ReactNode[] = [];
  let lineIndex = 0;
  let partKey = 0;

  while (lineIndex < lines.length) {
    const line = lines[lineIndex];

    if (/^[-*•]\s+/.test(line)) {
      const items: string[] = [];
      while (lineIndex < lines.length && /^[-*•]\s+/.test(lines[lineIndex])) {
        items.push(lines[lineIndex].replace(/^[-*•]\s+/, ''));
        lineIndex += 1;
      }
      nodes.push(renderBulletList(items, `${index}-${partKey++}`));
      continue;
    }

    if (/^\d+[.)]\s+/.test(line)) {
      const items: string[] = [];
      while (lineIndex < lines.length && /^\d+[.)]\s+/.test(lines[lineIndex])) {
        items.push(lines[lineIndex].replace(/^\d+[.)]\s+/, ''));
        lineIndex += 1;
      }
      nodes.push(renderNumberedList(items, `${index}-${partKey++}`));
      continue;
    }

    if (isBoldHeadingLine(line)) {
      nodes.push(renderHeadingLine(line, `${index}-${partKey++}`));
      lineIndex += 1;
      continue;
    }

    nodes.push(
      <p
        key={`${index}-${partKey++}`}
        style={{ margin: '0 0 10px', lineHeight: 1.65, color: HAP_AGENT_THEME.textSecondary, fontSize: 13 }}
      >
        {renderInline(line)}
      </p>,
    );
    lineIndex += 1;
  }

  return <div key={index}>{nodes}</div>;
}

export function AgentAssistantText({ text, soften, streaming }: AgentAssistantTextProps) {
  const display = useMemo(() => {
    const base = soften ? soften(text) : text;
    return normalizeStreamingMarkdown(base, streaming);
  }, [soften, streaming, text]);

  const blocks = useMemo(
    () => display.split(/\n{2,}/).map((block) => block.trim()).filter(Boolean),
    [display],
  );

  if (!display.trim()) return null;

  return (
    <div style={{ color: HAP_AGENT_THEME.text }}>
      {blocks.map((block, index) => renderBlock(block, index))}
      {streaming ? (
        <span
          aria-hidden
          style={{
            display: 'inline-block',
            width: 8,
            height: 14,
            marginLeft: 2,
            background: HAP_AGENT_THEME.textMuted,
            animation: 'hap-agent-cursor 1s step-end infinite',
            verticalAlign: 'text-bottom',
          }}
        />
      ) : null}
      <style>{`@keyframes hap-agent-cursor { 50% { opacity: 0; } }`}</style>
    </div>
  );
}

export function formatActivityResultPreview(raw: string, limit = 160): string {
  const text = stripMarkdownForSummary(raw);
  if (!text) return '';
  if (raw.trim().startsWith('{') || raw.trim().startsWith('[')) {
    try {
      const parsed = JSON.parse(raw.trim()) as Record<string, unknown>;
      const summary = String(parsed.summary || parsed.message || '').trim();
      if (summary) return summary.length > limit ? `${summary.slice(0, limit - 1)}…` : summary;
      const services = parsed.services;
      if (Array.isArray(services) && services.length) {
        const first = services[0] as Record<string, unknown>;
        const name = String(first.name || first.service || '服务');
        const status = first.reachable === true ? '正常' : first.reachable === false ? '不可达' : String(first.status || '');
        const extra = services.length > 1 ? ` 等 ${services.length} 项` : '';
        const line = `${name}：${status}${extra}`;
        return line.length > limit ? `${line.slice(0, limit - 1)}…` : line;
      }
    } catch {
      /* keep stripped text */
    }
  }
  return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
}
