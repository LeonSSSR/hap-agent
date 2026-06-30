from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def _aliases_path() -> Path:
    return Path(__file__).resolve().parent.parent / "mcp_tool_aliases.registry.yaml"


@lru_cache(maxsize=1)
def load_alias_entries() -> list[dict[str, Any]]:
    path = _aliases_path()
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = data.get("aliases")
    return [item for item in entries if isinstance(item, dict)] if isinstance(entries, list) else []


@lru_cache(maxsize=1)
def alias_to_canonical() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in load_alias_entries():
        alias = str(item.get("alias") or "").strip()
        canonical = str(item.get("canonical") or alias).strip()
        if alias:
            mapping[alias] = canonical
    return mapping


@lru_cache(maxsize=1)
def canonical_to_aliases() -> dict[str, set[str]]:
    reverse: dict[str, set[str]] = {}
    for alias, canonical in alias_to_canonical().items():
        if alias == canonical:
            continue
        reverse.setdefault(canonical, set()).add(alias)
    return reverse


def resolve_canonical_tool_name(tool_name: str) -> str:
    return alias_to_canonical().get(tool_name, tool_name)


def alias_names_for_canonical(canonical: str) -> set[str]:
    return set(canonical_to_aliases().get(canonical, set()))


def skill_allows_tool(tool_name: str, allowed_tools: set[str]) -> bool:
    if not allowed_tools:
        return True
    if tool_name in allowed_tools:
        return True
    canonical = resolve_canonical_tool_name(tool_name)
    if canonical in allowed_tools:
        return True
    for allowed in allowed_tools:
        if resolve_canonical_tool_name(allowed) == canonical:
            return True
    aliases = alias_names_for_canonical(canonical)
    return bool(aliases.intersection(allowed_tools))
