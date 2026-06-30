"""Agent API routes (Agentic SSE)."""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from config import settings
from middleware.auth import require_agent_identity
from schemas.agentic import (
    AgentPageResultRequest,
    AgentRunClarifyRequest,
    AgentRunConfirmRequest,
    AgentRunRequest,
)
from services.access_control import (
    assert_audit_trace_access,
    assert_session_access,
    can_access_audit_record,
    is_audit_admin,
)
from services.agentic_runner import AgenticRunner
from services.audit_store import audit_store
from services.compensation_executor import compensation_executor
from services.identity_service import AgentIdentity
from services.mcp_tool_catalog import build_planning_context, list_tools_for_prompt
from services.observability_metrics import compute_rates, evaluate_alerts
from services.orchestrator import AgentOrchestrator
from services.platform_operations_catalog import filter_ui_actions_for_identity, list_operations_for_prompt
from services.run_store import run_store
from services.session_store import session_store
from services.trace_view import trace_view_service

router = APIRouter(prefix="/api/agent", tags=["agent"])
orchestrator = AgentOrchestrator()


def _agent_model_snapshot() -> dict[str, Any]:
    configured = bool(settings.agent_model_api_key) or settings.agent_model_provider == "mock"
    return {
        "enabled": settings.agent_model_enabled,
        "provider": settings.agent_model_provider,
        "model": settings.agent_model_name,
        "configured": configured,
        "stream": settings.agentic_stream_enabled,
        "thinking_enabled": settings.agent_model_thinking_enabled,
        "stream_enabled": settings.agent_model_stream_enabled,
    }


def _capabilities_real_execution_flag() -> bool:
    return settings.platform_api_mode in frozenset({"live", "hybrid"})


def _sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _assert_run_callback_access(run_id: str, identity: AgentIdentity) -> None:
    owner = run_store.get_run_owner(run_id)
    if owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found or expired")
    if owner != identity.username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="run access denied")


def _assert_session_id_access(session_id: str, identity: AgentIdentity) -> None:
    assert_session_access(session_store.get(session_id), identity)


class SaveSessionRequest(BaseModel):
    title: str | None = Field(default=None)
    turns: list[dict[str, Any]] | None = Field(default=None)


class CompensationTriggerRequest(BaseModel):
    strategy: str | None = None
    failed_node_id: str | None = None
    failed_tool_name: str | None = None
    error: str | None = None
    execution_context: dict[str, Any] | None = None


@router.get("/capabilities")
def capabilities(identity: AgentIdentity = Depends(require_agent_identity)) -> dict[str, Any]:
    mcp_tools = list_tools_for_prompt(identity=identity, limit=96)
    hap_operations = list_operations_for_prompt(identity=identity, limit=200)
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "architecture": "mcp_agentic",
            "features": ["agent_run_stream", "hap_operation_tools", "session_memory"],
            "real_execution": _capabilities_real_execution_flag(),
            "agent_model": _agent_model_snapshot(),
            "mcp_tools": mcp_tools,
            "hap_operations": hap_operations,
        },
    }


@router.get("/ui-actions")
def list_allowed_ui_actions(identity: AgentIdentity = Depends(require_agent_identity)) -> dict[str, Any]:
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "items": list_operations_for_prompt(identity=identity, limit=200),
            "allowed_ui_action_ids": filter_ui_actions_for_identity(identity),
        },
    }


@router.get("/sessions")
def list_sessions(
    limit: int = 20,
    offset: int = 0,
    identity: AgentIdentity = Depends(require_agent_identity),
) -> dict[str, Any]:
    items = session_store.list_sessions(
        owner=identity.username,
        include_all=is_audit_admin(identity),
        limit=limit,
        offset=offset,
    )
    return {
        "code": 0,
        "message": "ok",
        "data": {"items": items, "count": len(items), "limit": limit, "offset": offset},
    }


@router.post("/sessions")
def create_session(identity: AgentIdentity = Depends(require_agent_identity)) -> dict[str, Any]:
    session = session_store.create(owner=identity.username)
    payload = session_store.to_api_session(str(session["session_id"]))
    return {"code": 0, "message": "ok", "data": payload, "sessionId": payload.get("sessionId") if payload else None}


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    identity: AgentIdentity = Depends(require_agent_identity),
) -> dict[str, Any]:
    _assert_session_id_access(session_id, identity)
    payload = session_store.to_api_session(session_id)
    if not payload:
        return JSONResponse(status_code=404, content={"code": 404, "message": "session not found"})
    return {"code": 0, "message": "ok", "data": payload}


@router.put("/sessions/{session_id}")
def save_session(
    session_id: str,
    body: SaveSessionRequest,
    identity: AgentIdentity = Depends(require_agent_identity),
) -> dict[str, Any]:
    _assert_session_id_access(session_id, identity)
    saved = session_store.save_conversation(session_id, title=body.title, turns=body.turns)
    if not saved:
        return JSONResponse(status_code=404, content={"code": 404, "message": "session not found"})
    return {"code": 0, "message": "ok", "data": saved}


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    identity: AgentIdentity = Depends(require_agent_identity),
) -> dict[str, Any]:
    _assert_session_id_access(session_id, identity)
    if not session_store.delete_session(session_id):
        return JSONResponse(status_code=404, content={"code": 404, "message": "session not found", "sessionId": session_id})
    return {"code": 0, "message": "ok", "data": {"sessionId": session_id, "deleted": True}}


@router.get("/memory/search")
def search_long_term_memory(
    q: str,
    limit: int = 5,
    session_id: str | None = None,
    identity: AgentIdentity = Depends(require_agent_identity),
) -> dict[str, Any]:
    if session_id:
        _assert_session_id_access(session_id, identity)
    items = session_store.search_long_term_memory(
        q,
        session_id=session_id,
        owner=identity.username,
        limit=limit,
    )
    return {"code": 0, "message": "ok", "data": {"query": q, "items": items, "count": len(items)}}


@router.get("/audits")
def list_audits(
    action: str | None = None,
    risk_level: str | None = None,
    trace_id: str | None = None,
    limit: int = 20,
    identity: AgentIdentity = Depends(require_agent_identity),
) -> dict[str, Any]:
    include_all = is_audit_admin(identity)
    if trace_id:
        items = audit_store.list_by_trace_id(
            trace_id,
            limit=limit,
            username=identity.username,
            include_all=include_all,
        )
        if items:
            assert_audit_trace_access(items, identity)
    else:
        items = audit_store.list(
            action=action,
            risk_level=risk_level,
            limit=limit,
            username=identity.username,
            include_all=include_all,
        )
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "items": items,
            "count": len(items),
            "filters": {"action": action, "risk_level": risk_level, "trace_id": trace_id, "limit": limit},
        },
    }


@router.get("/audits/{audit_id}")
def get_audit(
    audit_id: str,
    identity: AgentIdentity = Depends(require_agent_identity),
) -> dict[str, Any]:
    record = audit_store.get(audit_id)
    if not record:
        return JSONResponse(status_code=404, content={"code": 404, "message": "audit not found"})
    if not can_access_audit_record(record, identity):
        return JSONResponse(status_code=403, content={"code": 403, "message": "audit access denied"})
    return {"code": 0, "message": "ok", "data": record}


@router.get("/audits/trace/{trace_id}")
def get_audit_trace(
    trace_id: str,
    limit: int = 50,
    identity: AgentIdentity = Depends(require_agent_identity),
) -> dict[str, Any]:
    include_all = is_audit_admin(identity)
    trace_exists = bool(audit_store.list_by_trace_id(trace_id, limit=1, include_all=True))
    items = audit_store.list_by_trace_id(
        trace_id,
        limit=limit,
        username=identity.username,
        include_all=include_all,
    )
    assert_audit_trace_access(items, identity, trace_exists=trace_exists)
    return {"code": 0, "message": "ok", "data": {"trace_id": trace_id, "items": items, "count": len(items)}}


@router.get("/traces/{trace_id}")
def get_execution_trace(
    trace_id: str,
    limit: int = 50,
    identity: AgentIdentity = Depends(require_agent_identity),
) -> dict[str, Any]:
    include_all = is_audit_admin(identity)
    trace_exists = bool(audit_store.list_by_trace_id(trace_id, limit=1, include_all=True))
    records = audit_store.list_by_trace_id(
        trace_id,
        limit=1,
        username=identity.username,
        include_all=include_all,
    )
    assert_audit_trace_access(records, identity, trace_exists=trace_exists)
    trace_view = trace_view_service.build_by_trace_id(trace_id, limit=limit)
    return {"code": 0, "message": "ok", "data": trace_view}


@router.get("/observability/metrics")
def get_observability_metrics(
    trace_id: str | None = None,
    limit: int = 200,
    identity: AgentIdentity = Depends(require_agent_identity),
) -> dict[str, Any]:
    _ = identity
    rates = compute_rates(trace_id=trace_id, limit=limit if trace_id else None)
    return {"code": 0, "message": "ok", "data": {"metrics": rates, "alerts": evaluate_alerts(rates)}}


@router.post("/traces/{trace_id}/compensate")
def trigger_trace_compensation(
    trace_id: str,
    body: CompensationTriggerRequest | None = None,
    identity: AgentIdentity = Depends(require_agent_identity),
) -> dict[str, Any]:
    include_all = is_audit_admin(identity)
    trace_exists = bool(audit_store.list_by_trace_id(trace_id, limit=1, include_all=True))
    records = audit_store.list_by_trace_id(
        trace_id,
        limit=None,
        username=identity.username,
        include_all=include_all,
    )
    if not records:
        if trace_exists:
            assert_audit_trace_access([], identity, trace_exists=True)
        return {"code": 404, "message": "trace not found", "data": None}
    assert_audit_trace_access(records, identity, trace_exists=trace_exists)
    first = records[0]
    task_id = str(first.get("task_id") or f"task-{trace_id[:12]}")
    workflow_id = str(first.get("workflow_id") or "agentic_compensation")
    payload = body or CompensationTriggerRequest()
    failed_tool = payload.failed_tool_name
    if not failed_tool:
        for record in reversed(records):
            if str(record.get("action") or "") != "tool_execution":
                continue
            if str(record.get("status") or "").lower() not in frozenset({"error", "failed", "blocked"}):
                continue
            failed_tool = str(record.get("tool_name") or record.get("mcp_tool_name") or "")
            if failed_tool:
                break
    result = compensation_executor.execute(
        trace_id=trace_id,
        task_id=task_id,
        workflow_id=workflow_id,
        failed_node_id=str(payload.failed_node_id or "manual_compensation"),
        failed_tool_name=failed_tool,
        error=str(payload.error or "manual compensation trigger"),
        strategy=payload.strategy,
        execution_context=payload.execution_context if isinstance(payload.execution_context, dict) else {},
        tool_executor=lambda name, tool_payload: orchestrator.execute_tool(
            name,
            tool_payload,
            build_planning_context("compensation", identity=identity),
            trace_id=trace_id,
            task_id=task_id,
            workflow_id=workflow_id,
            node_id="compensation",
            confirmed=True,
            approved_by=identity.username,
        ),
    )
    _ = identity
    return {"code": 0, "message": "ok", "data": result}


@router.post("/run/stream")
async def agent_run_stream(
    http_request: Request,
    body: AgentRunRequest,
    identity: AgentIdentity = Depends(require_agent_identity),
) -> StreamingResponse:
    allow_real_write = settings.platform_api_mode in {"live", "hybrid"}
    session_id = str(body.session_id or "").strip() or None
    if session_id:
        _assert_session_id_access(session_id, identity)
    exec_ctx = build_planning_context(body.message, identity=identity)
    exec_ctx["user_input"] = orchestrator.build_contextual_input(body.message, session_id, identity=identity)
    runner = AgenticRunner(
        tool_executor=orchestrator.bind_tool_executor(
            exec_ctx,
            identity=identity,
            allow_real_write=allow_real_write,
        ),
    )
    trace_holder: dict[str, str] = {}
    user_message = body.message.strip()
    assistant_summary = ""
    run_status = "completed"

    async def event_generator():
        nonlocal assistant_summary, run_status
        # Use asyncio.Queue (not thread pool + queue.Queue) to avoid exhausting the
        # default executor when many concurrent run/stream clients are connected.
        event_queue: asyncio.Queue[tuple[str, Any] | None] = asyncio.Queue()
        disconnected = threading.Event()
        loop = asyncio.get_running_loop()

        def cancel_check() -> bool:
            return disconnected.is_set()

        def _enqueue(item: tuple[str, Any] | None) -> None:
            asyncio.run_coroutine_threadsafe(event_queue.put(item), loop)

        def producer() -> None:
            try:
                for event, data in runner.run_events(
                    request=body,
                    identity=identity,
                    cancel_check=cancel_check,
                ):
                    if disconnected.is_set():
                        break
                    _enqueue((event, data))
            except Exception as exc:  # noqa: BLE001 — surface producer failures to client
                _enqueue(("error", {"message": str(exc)}))
            finally:
                _enqueue(None)

        producer_thread = threading.Thread(target=producer, daemon=True)
        producer_thread.start()

        try:
            while True:
                if await http_request.is_disconnected():
                    disconnected.set()
                    run_status = "stopped"
                try:
                    item = await asyncio.wait_for(event_queue.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    if disconnected.is_set() and not producer_thread.is_alive():
                        break
                    continue
                if item is None:
                    break
                event, data = item
                if event == "run_start" and isinstance(data, dict):
                    trace_holder["trace_id"] = str(data.get("trace_id") or "")
                    trace_holder["run_id"] = str(data.get("run_id") or "")
                elif event == "assistant_message" and isinstance(data, dict):
                    content = str(data.get("content") or "").strip()
                    if content:
                        assistant_summary = content
                elif event == "run_done" and isinstance(data, dict):
                    run_status = str(data.get("status") or "completed")
                    summary = str(data.get("summary") or "").strip()
                    if summary:
                        assistant_summary = summary
                yield _sse_event(event, data)
                if disconnected.is_set() and event == "run_done":
                    break
                await asyncio.sleep(0)
        finally:
            disconnected.set()
            producer_thread.join(timeout=10.0)
            if trace_holder.get("run_id"):
                run_store.clear_run(trace_holder["run_id"])
            if session_id and user_message and run_status in {"completed", "stopped"}:
                if session_store.get(session_id) is not None:
                    session_store.record_turn(
                        session_id,
                        user_message=user_message,
                        assistant_message=assistant_summary,
                        run_id=trace_holder.get("run_id") or None,
                        status=run_status,
                    )

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    if trace_holder.get("trace_id"):
        headers["X-Trace-Id"] = trace_holder["trace_id"]
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@router.post("/run/{run_id}/page-result")
def agent_run_page_result(
    run_id: str,
    body: AgentPageResultRequest,
    identity: AgentIdentity = Depends(require_agent_identity),
) -> dict[str, Any]:
    _assert_run_callback_access(run_id, identity)
    ok = run_store.set_page_result(
        run_id,
        body.tool_call_id,
        {
            "success": body.success,
            "message": body.message,
            "ui_action_id": body.ui_action_id,
            "detail": body.detail,
        },
    )
    if not ok:
        return {"code": 404, "message": "run or tool_call not waiting", "data": {"run_id": run_id}}
    return {
        "code": 0,
        "message": "ok",
        "data": {"run_id": run_id, "tool_call_id": body.tool_call_id},
    }


@router.post("/run/{run_id}/confirm")
def agent_run_confirm(
    run_id: str,
    body: AgentRunConfirmRequest,
    identity: AgentIdentity = Depends(require_agent_identity),
) -> dict[str, Any]:
    _assert_run_callback_access(run_id, identity)
    ok = run_store.set_confirm_decision(
        run_id,
        body.resume_token,
        decision=body.decision,
        approved_by=body.approved_by,
    )
    if not ok:
        return {"code": 404, "message": "run or resume_token not waiting", "data": {"run_id": run_id}}
    return {
        "code": 0,
        "message": "ok",
        "data": {"run_id": run_id, "resume_token": body.resume_token, "decision": body.decision},
    }


@router.post("/run/{run_id}/clarify")
def agent_run_clarify(
    run_id: str,
    body: AgentRunClarifyRequest,
    identity: AgentIdentity = Depends(require_agent_identity),
) -> dict[str, Any]:
    _assert_run_callback_access(run_id, identity)
    ok = run_store.set_clarify_answer(
        run_id,
        body.resume_token,
        answer=body.answer,
        skipped=body.skipped,
    )
    if not ok:
        return {"code": 404, "message": "run or resume_token not waiting", "data": {"run_id": run_id}}
    return {
        "code": 0,
        "message": "ok",
        "data": {"run_id": run_id, "resume_token": body.resume_token, "skipped": body.skipped},
    }
