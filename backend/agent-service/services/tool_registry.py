"""MCP tool registry loaded from mcp/tools/*.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from services.mcp_alias_registry import alias_to_canonical as _alias_map, load_alias_entries
from services.mcp_registry_loader import collect_registry_tools, load_registry_root


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}
        self._load_file_registry()

    def _ingest_registry_tools(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            if not isinstance(item, dict):
                continue
            tool_name = str(item.get("tool_name") or item.get("name") or "").strip()
            if not tool_name:
                continue
            normalized = self.normalize_tool_metadata(tool_name, item)
            normalized.setdefault("title", tool_name)
            policy = "read_only" if normalized.get("risk_level") == "low" else "append_only"
            normalized.setdefault("append_only_policy", policy)
            normalized.setdefault(
                "provider",
                {"mock": True, "real": normalized.get("source") == "platform"},
            )
            self._tools[tool_name] = normalized

    def _load_file_registry(self) -> None:
        registry_path = load_registry_root()
        self._ingest_registry_tools(collect_registry_tools(registry_path))
        for entry in load_alias_entries():
            alias = str(entry.get("alias") or "").strip()
            canonical = str(entry.get("canonical") or alias).strip()
            if alias and canonical in self._tools and alias not in self._tools:
                self._tools[alias] = self._tools[canonical].copy()
                self._tools[alias]["tool_name"] = alias
                self._tools[alias]["alias_of"] = canonical

    def list(self) -> list[str]:
        return sorted(self._tools.keys())

    def get(self, tool_name: str) -> dict[str, Any] | None:
        tool = self._tools.get(tool_name)
        return tool.copy() if tool else None

    def normalize_tool_metadata(self, tool_name: str, metadata: dict[str, Any] | None) -> dict[str, Any]:
        normalized = dict(metadata or {})
        normalized.setdefault("tool_name", tool_name)
        normalized.setdefault("source", "platform")
        normalized.setdefault("risk_level", "low")
        normalized.setdefault("permission_scope", [])
        normalized.setdefault("description", "")
        normalized.setdefault("resource_type", "api")
        normalized.setdefault("input_schema", {"type": "object"})
        normalized.setdefault("output_schema", {"type": "object"})
        return normalized

    def register(self, tool_name: str, metadata: dict[str, Any]) -> None:
        self._tools[tool_name] = metadata.copy()

    def is_allowed(self, tool_name: str) -> bool:
        return tool_name in self._tools

    def resolve_name(self, tool_name: str) -> str:
        return _alias_map().get(tool_name, tool_name)


tool_registry = ToolRegistry()
