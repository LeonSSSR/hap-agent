"""Restricted MCP executor boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ExecutionContext:
    allowed_tools: list[str] = field(default_factory=list)
    skill_id: str | None = None
    architecture: str | None = None
    source: str | None = None
    user_input: str | None = None


class RestrictedExecutor:
    def __init__(self, allowed_tools: list[str] | None = None) -> None:
        self._allowed = {str(t) for t in (allowed_tools or []) if str(t).strip()}

    def list_allowed(self) -> list[str]:
        return sorted(self._allowed)

    def execute(
        self,
        tool_name: str,
        payload: dict[str, Any],
        *,
        handler: Callable[[str, dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        if self._allowed and tool_name not in self._allowed:
            raise PermissionError(f"tool not allowed: {tool_name}")
        return handler(tool_name, payload)
