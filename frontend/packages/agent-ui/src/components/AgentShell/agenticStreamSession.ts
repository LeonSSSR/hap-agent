import {
  createSession,
  postAgentPageResult,
  postAgentRunClarify,
  postAgentRunConfirm,
  runAgentStream,
  type AgentRunStreamMessage,
} from '@/services/agent';
import { AGENT_SESSION_STORAGE_KEY } from './agentSession';
import { AgentPageController } from './AgentPageController';
import type { AgentActivity } from './agentStreamTypes';
import type { AgentClarifyPending, AgentClarifyResult } from './agentClarifyTypes';
import type { AgentConfirmDecision, AgentConfirmPending } from './agentConfirmTypes';
import { getOperationByUiActionId, isOperationTool, uiActionIdFromOperationTool } from './platformOperationsMap';
import type { PageActionHintState } from './AgentPageActionHint';

export type AgenticTurnPayload = {
  architecture: 'mcp_agentic';
  summary: string;
  understanding: string;
  sessionId: string;
  agentRun: {
    runId: string | null;
    traceId: string | null;
    assistantText: string;
    reasoningText: string;
    activities: AgentActivity[];
  };
};

export type AgenticStreamTerminalStatus = 'completed' | 'stopped' | 'failed' | 'aborted';

export type AgenticStreamSessionCallbacks = {
  onExecutionLog: (line: string) => void;
  onPageActionHint: (hint: PageActionHintState) => void;
  onPageActionHintClear: () => void;
  onPageActionError: (line: string) => void;
  onTurnSync: (partial: AgenticTurnPayload, status: 'loading' | 'done') => void;
  onConfirmRequired: (pending: AgentConfirmPending) => Promise<AgentConfirmDecision>;
  onClarificationRequired: (pending: AgentClarifyPending) => Promise<AgentClarifyResult>;
  onClarificationComplete?: () => void;
  onClarificationPostFailed?: (message: string) => void;
  onConfirmComplete?: () => void;
  onConfirmPostFailed?: (message: string) => void;
  approvedBy?: string;
};

function resolveUiActionIdFromPreview(
  toolName: string,
  preview?: Record<string, unknown>,
): string {
  if (!preview) return uiActionIdFromOperationTool(toolName) || '';
  const direct = String(preview.ui_action_id || '').trim();
  if (direct) return direct;
  return uiActionIdFromOperationTool(toolName) || '';
}

function toolDisplayName(toolName: string, uiActionId?: string): string {
  const resolvedId = uiActionId || uiActionIdFromOperationTool(toolName);
  if ((isOperationTool(toolName) || toolName === 'hap_ui_action') && resolvedId) {
    return getOperationByUiActionId(resolvedId)?.label || resolvedId;
  }
  return toolName;
}

function buildPartial(
  sessionId: string,
  runId: string | null,
  traceId: string | null,
  assistantText: string,
  reasoningText: string,
  activities: AgentActivity[],
  status: 'loading' | 'done',
): AgenticTurnPayload {
  const text = assistantText || (status === 'loading' ? '处理中…' : '已完成');
  return {
    architecture: 'mcp_agentic',
    summary: text,
    understanding: text,
    sessionId,
    agentRun: { runId, traceId, assistantText, reasoningText, activities },
  };
}

export async function runAgenticStreamSession(params: {
  message: string;
  sessionId: string | null;
  signal: AbortSignal;
  callbacks: AgenticStreamSessionCallbacks;
}): Promise<{
  sessionId: string;
  payload: AgenticTurnPayload;
  terminalStatus: AgenticStreamTerminalStatus;
}> {
  const { message, signal, callbacks } = params;
  let activeSessionId = params.sessionId?.trim() || '';
  if (!activeSessionId) {
    const session = await createSession();
    activeSessionId = session.sessionId;
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(AGENT_SESSION_STORAGE_KEY, activeSessionId);
    }
  }

  let assistantText = '';
  let reasoningText = '';
  let runId: string | null = null;
  let traceId: string | null = null;
  let terminalStatus: AgenticStreamTerminalStatus = 'completed';
  let streamError: string | null = null;
  const activities: AgentActivity[] = [];

  const upsertActivity = (next: AgentActivity) => {
    const idx = activities.findIndex((a) => a.toolCallId === next.toolCallId);
    if (idx < 0) activities.push(next);
    else activities[idx] = { ...activities[idx], ...next };
  };

  const syncTurn = (status: 'loading' | 'done' = 'loading') => {
    callbacks.onTurnSync(
      buildPartial(activeSessionId, runId, traceId, assistantText, reasoningText, [...activities], status),
      status,
    );
  };

  const handlePageAction = (parsed: Record<string, unknown>) => {
    if (!runId || signal.aborted) return;
    const uiActionId = String(parsed.ui_action_id || '');
    const toolCallId = String(parsed.tool_call_id || '');
    const stepTitle = String(parsed.title || 'Agent 页面操作');
    if (!uiActionId || !toolCallId) return;

    const opLabel = getOperationByUiActionId(uiActionId)?.label || stepTitle;
    callbacks.onExecutionLog(`[页面] ${opLabel}（${uiActionId}）`);

    void (async () => {
      if (signal.aborted) return;
      try {
        callbacks.onPageActionHint({ kind: 'page_action', stepTitle: opLabel, uiActionId });
        const actionType = String(parsed.action_type || '').trim();
        const route = String(parsed.route || '').trim();
        const navigateRoute = String(parsed.navigate_route || '').trim();
        const paramsArg =
          parsed.params && typeof parsed.params === 'object'
            ? (parsed.params as Record<string, unknown>)
            : undefined;
        const routeParams =
          paramsArg && typeof paramsArg === 'object'
            ? {
                id: paramsArg.id != null ? String(paramsArg.id) : undefined,
              }
            : undefined;
        const result = await AgentPageController.execute({
          title: stepTitle,
          step_type: 'page_action',
          ui_action_id: uiActionId,
          page_action: actionType || undefined,
          route: route || undefined,
          navigate_route: navigateRoute || undefined,
          route_params: routeParams,
          value: paramsArg?.value != null ? String(paramsArg.value) : undefined,
        });
        if (signal.aborted) return;
        await postAgentPageResult(runId!, {
          tool_call_id: toolCallId,
          ui_action_id: uiActionId,
          success: result.success,
          message: result.message,
          detail: {
            error: result.error,
            route,
            navigate_route: navigateRoute,
            route_params: routeParams,
          },
        });
        callbacks.onExecutionLog(
          `[页面] ${opLabel} ${result.success ? '完成' : '失败'}${result.message ? `：${result.message}` : ''}`,
        );
        if (!result.success) {
          callbacks.onPageActionError(`[页面联动] ${uiActionId}：${result.message}`);
        }
      } catch (e: unknown) {
        if (signal.aborted) return;
        const errMsg = e instanceof Error ? e.message : String(e);
        callbacks.onPageActionError(`[页面联动] ${uiActionId}：${errMsg}`);
        callbacks.onExecutionLog(`[页面] ${opLabel} 失败：${errMsg}`);
        try {
          await postAgentPageResult(runId!, {
            tool_call_id: toolCallId,
            ui_action_id: uiActionId,
            success: false,
            message: errMsg,
            detail: { error: 'execution_exception' },
          });
        } catch {
          /* backend may already have timed out */
        }
      } finally {
        callbacks.onPageActionHintClear();
      }
    })();
  };

  const onStream = (msg: AgentRunStreamMessage) => {
    const parsed = msg.parsed;
    if (!parsed) return;

    if (msg.event === 'run_start') {
      runId = String(parsed.run_id || '') || null;
      traceId = String(parsed.trace_id || '') || null;
      syncTurn('loading');
      return;
    }

    if (msg.event === 'error') {
      streamError = String(parsed.message || parsed.code || 'Agent 执行失败');
      callbacks.onExecutionLog(`[错误] ${streamError}`);
      terminalStatus = 'failed';
      syncTurn('loading');
      return;
    }

    if (msg.event === 'reasoning_delta') {
      reasoningText += String(parsed.delta || '');
      syncTurn('loading');
      return;
    }

    if (msg.event === 'reasoning_message' && parsed.content) {
      reasoningText = String(parsed.content);
      syncTurn('loading');
      return;
    }

    if (msg.event === 'assistant_delta') {
      assistantText += String(parsed.delta || '');
      syncTurn('loading');
      return;
    }

    if (msg.event === 'assistant_message' && parsed.content) {
      assistantText = String(parsed.content);
      syncTurn('loading');
      return;
    }

    if (msg.event === 'clarification_required') {
      const toolCallId = String(parsed.tool_call_id || '');
      const resumeToken = String(parsed.resume_token || '');
      const question = String(parsed.question || '请补充信息');
      const fields = Array.isArray(parsed.fields)
        ? (parsed.fields as unknown[]).map((item) => String(item))
        : undefined;
      const placeholder = String(parsed.placeholder || '') || undefined;
      const choices = Array.isArray(parsed.choices)
        ? (parsed.choices as unknown[]).map((item) => String(item)).filter(Boolean)
        : undefined;
      const eventRunId = String(parsed.run_id || '').trim();
      if (eventRunId) runId = eventRunId;
      if (!runId || !resumeToken) return;
      upsertActivity({
        toolCallId,
        toolName: 'hap_request_clarification',
        status: 'awaiting_clarification',
        resultPreview: question,
        startedAt: Date.now(),
      });
      callbacks.onExecutionLog(`[补充] ${question}`);
      syncTurn('loading');
      void (async () => {
        let result = await callbacks.onClarificationRequired({
          runId,
          toolCallId,
          question,
          resumeToken,
          fields,
          placeholder,
          choices,
        });
        while (!signal.aborted) {
          try {
            await postAgentRunClarify(runId!, {
              resume_token: resumeToken,
              answer: result.answer,
              skipped: result.skipped,
            });
            callbacks.onClarificationComplete?.();
            if (!result.skipped && result.answer) {
              callbacks.onExecutionLog(`[补充] 已收到：${result.answer}`);
              upsertActivity({
                toolCallId,
                toolName: 'hap_request_clarification',
                status: 'ok',
                resultPreview: result.answer,
                startedAt: Date.now(),
              });
            } else {
              callbacks.onExecutionLog('[补充] 用户选择跳过');
              upsertActivity({
                toolCallId,
                toolName: 'hap_request_clarification',
                status: 'blocked',
                resultPreview: '已跳过',
                startedAt: Date.now(),
              });
            }
            syncTurn('loading');
            break;
          } catch (e: unknown) {
            const errMsg = e instanceof Error ? e.message : String(e);
            callbacks.onExecutionLog(`[补充] 提交失败：${errMsg}`);
            callbacks.onClarificationPostFailed?.(errMsg);
            if (signal.aborted) return;
            result = await callbacks.onClarificationRequired({
              runId,
              toolCallId,
              question,
              resumeToken,
              fields,
              placeholder,
              choices,
            });
          }
        }
      })();
      return;
    }

    if (msg.event === 'confirm_required') {
      const toolName = String(parsed.tool_name || 'tool');
      const toolCallId = String(parsed.tool_call_id || '');
      const resumeToken = String(parsed.resume_token || '');
      const riskLevel = String(parsed.risk_level || 'high');
      const uiActionId = String(parsed.ui_action_id || '') || undefined;
      const eventRunId = String(parsed.run_id || '').trim();
      if (eventRunId) runId = eventRunId;
      if (!runId || !resumeToken) return;
      upsertActivity({
        toolCallId,
        toolName,
        status: 'awaiting_confirm',
        argumentsPreview: uiActionId ? { ui_action_id: uiActionId } : undefined,
        resultPreview: `需确认（${riskLevel}）`,
        startedAt: Date.now(),
      });
      callbacks.onExecutionLog(
        `[确认] ${toolDisplayName(toolName, uiActionId)} 等待用户确认（${riskLevel}）`,
      );
      syncTurn('loading');
      void (async () => {
        try {
          const decision = await callbacks.onConfirmRequired({
            runId,
            toolCallId,
            toolName,
            riskLevel,
            resumeToken,
            uiActionId,
          });
          if (signal.aborted) return;
          await postAgentRunConfirm(runId!, {
            resume_token: resumeToken,
            decision,
            approved_by: callbacks.approvedBy,
          });
          callbacks.onConfirmComplete?.();
          if (decision === 'approve') {
            callbacks.onExecutionLog(`[确认] ${toolDisplayName(toolName, uiActionId)} 已确认继续`);
            upsertActivity({
              toolCallId,
              toolName,
              status: 'running',
              startedAt: Date.now(),
            });
          } else {
            callbacks.onExecutionLog(`[确认] ${toolDisplayName(toolName, uiActionId)} 已拒绝`);
            upsertActivity({
              toolCallId,
              toolName,
              status: 'blocked',
              resultPreview: '用户拒绝',
              startedAt: Date.now(),
            });
          }
          syncTurn('loading');
        } catch (e: unknown) {
          const errMsg = e instanceof Error ? e.message : String(e);
          callbacks.onExecutionLog(`[确认] ${toolDisplayName(toolName, uiActionId)} 失败：${errMsg}`);
          callbacks.onConfirmPostFailed?.(errMsg);
        }
      })();
      return;
    }

    if (msg.event === 'tool_start') {
      const toolName = String(parsed.tool_name || 'tool');
      const argsPreview =
        parsed.arguments_preview && typeof parsed.arguments_preview === 'object'
          ? (parsed.arguments_preview as Record<string, unknown>)
          : undefined;
      const uiActionId = resolveUiActionIdFromPreview(toolName, argsPreview);
      upsertActivity({
        toolCallId: String(parsed.tool_call_id || ''),
        toolName,
        status: 'running',
        argumentsPreview: argsPreview,
        startedAt: Date.now(),
      });
      callbacks.onExecutionLog(`[工具] ${toolDisplayName(toolName, uiActionId)} 开始`);
      syncTurn('loading');
      return;
    }

    if (msg.event === 'tool_result') {
      const toolName = String(parsed.tool_name || 'tool');
      const ok = parsed.status === 'ok';
      upsertActivity({
        toolCallId: String(parsed.tool_call_id || ''),
        toolName,
        status: ok ? 'ok' : 'error',
        resultPreview: String(parsed.result_preview || ''),
        durationMs: typeof parsed.duration_ms === 'number' ? parsed.duration_ms : undefined,
        startedAt: Date.now(),
      });
      callbacks.onExecutionLog(
        `[工具] ${toolName} ${ok ? '完成' : '失败'}${parsed.result_preview ? `：${String(parsed.result_preview).slice(0, 120)}` : ''}`,
      );
      syncTurn('loading');
      return;
    }

    if (msg.event === 'tool_blocked') {
      const toolName = String(parsed.tool_name || 'tool');
      const blockedLabel = String(parsed.blocked_label || parsed.blocked_reason || '策略拦截');
      upsertActivity({
        toolCallId: String(parsed.tool_call_id || ''),
        toolName,
        status: 'blocked',
        resultPreview: blockedLabel,
        startedAt: Date.now(),
      });
      callbacks.onExecutionLog(`[阻断] ${toolDisplayName(toolName)}：${blockedLabel}`);
      syncTurn('loading');
      return;
    }

    if (msg.event === 'page_action') {
      handlePageAction(parsed);
      return;
    }

    if (msg.event === 'run_done') {
      const summary = String(parsed.summary || '').trim();
      if (summary) assistantText = summary;
      const status = String(parsed.status || 'completed');
      if (status === 'stopped') terminalStatus = 'stopped';
      else if (status === 'failed') terminalStatus = 'failed';
      else terminalStatus = 'completed';
      if (parsed.run_id) runId = String(parsed.run_id);
      if (parsed.trace_id) traceId = String(parsed.trace_id);
      syncTurn('loading');
    }
  };

  await new Promise<void>((resolve, reject) => {
    runAgentStream(
      { message, session_id: activeSessionId },
      onStream,
      () => resolve(),
      (err) => reject(err),
      signal,
    ).catch(reject);
  });

  if (signal.aborted) {
    throw new DOMException('Aborted', 'AbortError');
  }
  if (streamError) {
    throw new Error(streamError);
  }
  if (terminalStatus === 'failed') {
    throw new Error(assistantText || 'Agent 执行失败');
  }
  if (terminalStatus === 'stopped') {
    throw new DOMException('Stopped', 'AbortError');
  }

  const payload = buildPartial(
    activeSessionId,
    runId,
    traceId,
    assistantText || '已完成',
    reasoningText,
    [...activities],
    'done',
  );
  return { sessionId: activeSessionId, payload, terminalStatus };
}
