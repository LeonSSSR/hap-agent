from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ExecutionModeCode = Literal["controlled_mock", "controlled_real"]


class AgentRunOptions(BaseModel):
    max_turns: int | None = Field(default=None, ge=1, le=100)
    execution_mode: ExecutionModeCode | str | None = None
    confirm_high_risk: bool = True


class AgentRunRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None
    options: AgentRunOptions = Field(default_factory=AgentRunOptions)


class AgentPageResultRequest(BaseModel):
    tool_call_id: str
    ui_action_id: str
    success: bool = True
    message: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)


class AgentRunConfirmRequest(BaseModel):
    resume_token: str
    approved_by: str | None = None
    decision: Literal["approve", "reject"] = "approve"


class AgentRunClarifyRequest(BaseModel):
    resume_token: str
    answer: str = ""
    skipped: bool = False
