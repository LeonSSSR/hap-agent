from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_registry_root(path: Path | None = None) -> Path:
    return path or (Path(__file__).resolve().parent.parent / "mcp_tools.registry.yaml")


def collect_registry_tools(registry_path: Path, *, seen: set[str] | None = None) -> list[dict[str, Any]]:
    if seen is None:
        seen = set()
    key = str(registry_path.resolve())
    if key in seen or not registry_path.exists():
        return []
    seen.add(key)
    loaded = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        return []
    root = registry_path.parent
    tools: list[dict[str, Any]] = []
    for include in loaded.get("includes") or []:
        tools.extend(collect_registry_tools((root / str(include)).resolve(), seen=seen))
    for item in loaded.get("tools") or []:
        if isinstance(item, dict):
            tools.append(item)
    return tools


def load_registry_bundle(registry_path: Path | None = None) -> dict[str, Any]:
    path = load_registry_root(registry_path)
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(loaded, dict):
        loaded = {}
    return {**loaded, "tools": collect_registry_tools(path)}
