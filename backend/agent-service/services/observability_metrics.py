from __future__ import annotations

from typing import Any

from services.audit_store import audit_store

AGENT_MODEL_FAIL_ACTIONS = frozenset({"agent_model_failed"})
MCP_TOOL_ACTION = "tool_execution"
APPROVAL_ACTIONS = frozenset({"approval_checked", "permission_checked", "confirmation_checked"})
AGENTIC_RUN_ACTIONS = frozenset({"agentic_run_started", "agentic_run_completed", "agentic_run_failed"})
AGENTIC_RUN_TERMINAL_ACTIONS = frozenset({"agentic_run_completed", "agentic_run_failed", "run_done"})


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _metadata(record: dict[str, object]) -> dict[str, object]:
    raw = record.get("metadata")
    return raw if isinstance(raw, dict) else {}


def _is_agent_model_attempt(record: dict[str, object]) -> bool:
    action = str(record.get("action") or "")
    if action in AGENT_MODEL_FAIL_ACTIONS:
        return True
    metadata = _metadata(record)
    source = str(record.get("source") or metadata.get("source") or "").lower()
    if source in {"agent_model", "openai", "deepseek", "mock", "fallback"}:
        return True
    return bool(metadata.get("agent_model_runtime"))


def _is_agent_model_fallback(record: dict[str, object]) -> bool:
    metadata = _metadata(record)
    source = str(record.get("source") or metadata.get("source") or "").lower()
    return source == "fallback" or bool(metadata.get("agent_model_fallback"))


def _is_agent_model_failure(record: dict[str, object]) -> bool:
    return str(record.get("action") or "") in AGENT_MODEL_FAIL_ACTIONS


def _is_mcp_attempt(record: dict[str, object]) -> bool:
    return str(record.get("action") or "") == MCP_TOOL_ACTION


def _is_mcp_failure(record: dict[str, object]) -> bool:
    if not _is_mcp_attempt(record):
        return False
    status = str(record.get("status") or "").lower()
    blocked_by = str(record.get("blocked_by") or "").lower()
    return status in {"failed", "blocked", "error"} or blocked_by == "mcp"


def _is_approval_attempt(record: dict[str, object]) -> bool:
    return str(record.get("action") or "") in APPROVAL_ACTIONS


def _is_approval_blocked(record: dict[str, object]) -> bool:
    if not _is_approval_attempt(record):
        return False
    status = str(record.get("status") or "").lower()
    blocked_by = str(record.get("blocked_by") or "").lower()
    return status == "blocked" or blocked_by in {"approval", "permission"}


def _is_real_execution_attempt(record: dict[str, object]) -> bool:
    if not _is_mcp_attempt(record):
        return False
    if bool(record.get("real_execution")):
        return True
    source = str(record.get("source") or "").lower()
    return source in {"real", "platform", "live"}


def _is_real_execution_success(record: dict[str, object]) -> bool:
    return _is_real_execution_attempt(record) and str(record.get("status") or "").lower() in {"succeeded", "completed", "ok"}


def _is_agentic_run(record: dict[str, object]) -> bool:
    action = str(record.get("action") or "")
    if action in AGENTIC_RUN_ACTIONS:
        return True
    metadata = _metadata(record)
    if metadata.get("run_id"):
        return True
    entry = str(record.get("execution_entry") or "").lower()
    return "agentic_runner" in entry or entry.endswith("run/stream")


def _is_agentic_run_success(record: dict[str, object]) -> bool:
    action = str(record.get("action") or "")
    if action == "agentic_run_completed":
        return True
    if action == "agentic_run_failed":
        return False
    if not _is_agentic_run(record):
        return False
    status = str(record.get("status") or "").lower()
    return status in {"succeeded", "completed", "ok", "done"}


def _is_agentic_tool_call(record: dict[str, object]) -> bool:
    if not _is_mcp_attempt(record):
        return False
    entry = str(record.get("execution_entry") or "").lower()
    context = _metadata(record)
    return "agentic_runner" in entry or str(context.get("execution_entry") or "").lower().find("agentic_runner") >= 0


def _filter_records(records: list[dict[str, object]], *, trace_id: str | None = None) -> list[dict[str, object]]:
    if not trace_id:
        return records
    return [record for record in records if str(record.get("trace_id") or "") == trace_id]


_TRACE_TERMINAL_ACTIONS = frozenset(
    {
        "agentic_run_completed",
        "agentic_run_failed",
    }
)
_TRACE_SUCCESS_STATUSES = frozenset({"completed", "succeeded", "ok", "approved", "done"})
_TRACE_FAILURE_STATUSES = frozenset({"failed", "error", "stopped"})


def _trace_terminal_status(records: list[dict[str, object]]) -> str | None:
    for record in reversed(records):
        action = str(record.get("action") or "")
        if action not in _TRACE_TERMINAL_ACTIONS:
            continue
        metadata = _metadata(record)
        status = str(record.get("status") or metadata.get("stream_status") or "").lower()
        if status:
            return status
    return None


def compute_trace_outcomes(*, limit: int | None = None) -> dict[str, Any]:
    records = audit_store.list(limit=limit)
    by_trace: dict[str, list[dict[str, object]]] = {}
    for record in records:
        trace = str(record.get("trace_id") or "").strip()
        if not trace:
            continue
        by_trace.setdefault(trace, []).append(record)

    successes = failures = blocked = unknown = 0
    for trace_records in by_trace.values():
        status = _trace_terminal_status(trace_records)
        if status in _TRACE_SUCCESS_STATUSES:
            successes += 1
        elif status in _TRACE_FAILURE_STATUSES:
            failures += 1
        elif status == "blocked":
            blocked += 1
        else:
            unknown += 1

    total = len(by_trace)
    terminal = successes + failures
    return {
        "trace_count": total,
        "trace_successes": successes,
        "trace_failures": failures,
        "trace_blocked": blocked,
        "trace_unknown": unknown,
        "agent_success_rate": _rate(successes, terminal),
        "agent_failure_rate": _rate(failures, terminal),
    }


def _agent_model_rate_fields(
    *,
    attempts: int,
    failures: int,
    fallbacks: int,
) -> dict[str, Any]:
    return {
        "agent_model_failure_rate": _rate(failures, attempts),
        "agent_model_failures": failures,
        "agent_model_attempts": attempts,
        "agent_model_fallback_rate": _rate(fallbacks, attempts),
        "agent_model_fallbacks": fallbacks,
    }


def compute_rates(*, trace_id: str | None = None, limit: int | None = None) -> dict[str, Any]:
    records = _filter_records(audit_store.list(limit=limit), trace_id=trace_id)
    agent_model_attempts = sum(1 for record in records if _is_agent_model_attempt(record))
    agent_model_failures = sum(1 for record in records if _is_agent_model_failure(record))
    agent_model_fallbacks = sum(1 for record in records if _is_agent_model_fallback(record))
    mcp_attempts = sum(1 for record in records if _is_mcp_attempt(record))
    mcp_failures = sum(1 for record in records if _is_mcp_failure(record))
    approval_attempts = sum(1 for record in records if _is_approval_attempt(record))
    approval_blocks = sum(1 for record in records if _is_approval_blocked(record))
    real_attempts = sum(1 for record in records if _is_real_execution_attempt(record))
    real_successes = sum(1 for record in records if _is_real_execution_success(record))
    agentic_runs = sum(1 for record in records if _is_agentic_run(record))
    agentic_run_successes = sum(1 for record in records if _is_agentic_run_success(record))
    agentic_tool_calls = sum(1 for record in records if _is_agentic_tool_call(record))
    agentic_tool_failures = sum(
        1 for record in records if _is_agentic_tool_call(record) and _is_mcp_failure(record)
    )

    rates: dict[str, Any] = {
        "scope": "trace" if trace_id else "global",
        "trace_id": trace_id,
        "sample_size": len(records),
        **_agent_model_rate_fields(
            attempts=agent_model_attempts,
            failures=agent_model_failures,
            fallbacks=agent_model_fallbacks,
        ),
        "mcp_call_failure_rate": _rate(mcp_failures, mcp_attempts),
        "mcp_tool_error_rate": _rate(mcp_failures, mcp_attempts),
        "mcp_failures": mcp_failures,
        "mcp_attempts": mcp_attempts,
        "approval_blockage_rate": _rate(approval_blocks, approval_attempts),
        "approval_blocks": approval_blocks,
        "approval_attempts": approval_attempts,
        "real_execution_success_rate": _rate(real_successes, real_attempts),
        "real_execution_rate": _rate(real_attempts, mcp_attempts),
        "real_execution_successes": real_successes,
        "real_execution_attempts": real_attempts,
        "agentic_run_total": agentic_runs,
        "agentic_run_successes": agentic_run_successes,
        "agentic_run_success_rate": _rate(agentic_run_successes, agentic_runs),
        "agentic_tool_calls_total": agentic_tool_calls,
        "agentic_tool_call_failure_rate": _rate(agentic_tool_failures, agentic_tool_calls),
        "agentic_tool_call_failures": agentic_tool_failures,
    }
    if not trace_id:
        rates.update(compute_trace_outcomes(limit=limit))
    return rates


def evaluate_alerts(rates: dict[str, Any]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if rates.get("agent_model_attempts", 0) and float(rates.get("agent_model_failure_rate") or 0) >= 0.5:
        alerts.append(
            {
                "severity": "warning",
                "code": "agent_model_failure_rate_high",
                "message": "Agent 模型失败率偏高，请检查 LLM 连通性与 AGENT_MODEL_* 配置。",
                "value": rates.get("agent_model_failure_rate"),
            }
        )
    if rates.get("mcp_attempts", 0) and float(rates.get("mcp_call_failure_rate") or 0) >= 0.3:
        alerts.append(
            {
                "severity": "critical",
                "code": "mcp_failure_rate_high",
                "message": "MCP 调用失败率偏高，请检查工具契约与平台 API。",
                "value": rates.get("mcp_call_failure_rate"),
            }
        )
    if rates.get("approval_attempts", 0) and float(rates.get("approval_blockage_rate") or 0) >= 0.4:
        alerts.append(
            {
                "severity": "warning",
                "code": "approval_blockage_rate_high",
                "message": "审批阻断率偏高，请核对权限与审批链。",
                "value": rates.get("approval_blockage_rate"),
            }
        )
    if rates.get("real_execution_attempts", 0) and float(rates.get("real_execution_success_rate") or 0) < 0.6:
        alerts.append(
            {
                "severity": "warning",
                "code": "real_execution_success_rate_low",
                "message": "真实执行成功率偏低，请结合 Trace 定位失败节点。",
                "value": rates.get("real_execution_success_rate"),
            }
        )
    if rates.get("agent_model_attempts", 0) and float(rates.get("agent_model_fallback_rate") or 0) >= 0.3:
        alerts.append(
            {
                "severity": "warning",
                "code": "agent_model_fallback_rate_high",
                "message": "Agent 模型 fallback 率偏高，请检查 API Key 与 provider 配置。",
                "value": rates.get("agent_model_fallback_rate"),
            }
        )
    if rates.get("agentic_run_total", 0) and float(rates.get("agentic_run_success_rate") or 0) < 0.6:
        alerts.append(
            {
                "severity": "warning",
                "code": "agentic_run_success_rate_low",
                "message": "Agentic run 成功率偏低，请检查 run/stream 日志与 MCP 工具。",
                "value": rates.get("agentic_run_success_rate"),
            }
        )
    if rates.get("trace_count", 0) and float(rates.get("agent_failure_rate") or 0) >= 0.3:
        alerts.append(
            {
                "severity": "critical",
                "code": "agent_failure_rate_high",
                "message": "Agent 执行失败率偏高，请启动事故流程排查。",
                "value": rates.get("agent_failure_rate"),
            }
        )
    return alerts


def build_log_links(*, trace_id: str) -> dict[str, str]:
    from config import settings

    links: dict[str, str] = {
        "audit_trace": f"/api/agent/audits/trace/{trace_id}",
    }
    if settings.prometheus_url:
        query = f'{{trace_id="{trace_id}"}}'
        links["prometheus"] = f"{settings.prometheus_url.rstrip('/')}/graph?g0.expr=agent_execution_events{query}"
    if settings.grafana_url:
        links["grafana"] = f"{settings.grafana_url.rstrip('/')}/d/agent-trace?var-trace_id={trace_id}"
    if settings.loki_url:
        links["loki"] = f"{settings.loki_url.rstrip('/')}/explore?query={trace_id}"
    return links


def to_prometheus_lines(rates: dict[str, Any]) -> str:
    scope = str(rates.get("scope") or "global")
    trace = str(rates.get("trace_id") or "")
    label_suffix = f'trace_id="{trace}"' if trace else 'scope="global"'
    metrics = [
        ("agent_model_failure_rate", rates.get("agent_model_failure_rate")),
        ("agent_model_fallback_rate", rates.get("agent_model_fallback_rate")),

        ("agent_mcp_call_failure_rate", rates.get("mcp_call_failure_rate")),
        ("agent_mcp_tool_error_rate", rates.get("mcp_tool_error_rate")),
        ("agent_approval_blockage_rate", rates.get("approval_blockage_rate")),
        ("agent_real_execution_success_rate", rates.get("real_execution_success_rate")),
        ("agent_real_execution_rate", rates.get("real_execution_rate")),
        ("agent_success_rate", rates.get("agent_success_rate")),
        ("agent_failure_rate", rates.get("agent_failure_rate")),
        ("agentic_run_total", rates.get("agentic_run_total")),
        ("agentic_run_success_rate", rates.get("agentic_run_success_rate")),
        ("agentic_tool_calls_total", rates.get("agentic_tool_calls_total")),
        ("agentic_tool_call_failure_rate", rates.get("agentic_tool_call_failure_rate")),
    ]
    lines: list[str] = []
    for name, value in metrics:
        lines.append(f"# TYPE {name} gauge")
        lines.append(f"{name}{{{label_suffix}}} {float(value or 0)}")
    return "\n".join(lines) + "\n"
