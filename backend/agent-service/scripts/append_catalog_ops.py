#!/usr/bin/env python3
"""向 platform_operations_catalog 批量追加子操作（前后端同步）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATHS = [
    ROOT / "agent-service" / "data" / "platform_operations_catalog.json",
    ROOT.parent / "frontend" / "src" / "components" / "AgentShell" / "platformOperationsCatalog.json",
]


def main() -> None:
    new_ops = json.loads(sys.stdin.read())
    if not isinstance(new_ops, list):
        raise SystemExit("stdin must be JSON array of operations")
    for path in PATHS:
        cat = json.loads(path.read_text(encoding="utf-8"))
        by_id = {o["ui_action_id"]: o for o in cat.get("operations", [])}
        added = 0
        for op in new_ops:
            uid = str(op.get("ui_action_id") or "").strip()
            if not uid or uid in by_id:
                continue
            cat.setdefault("operations", []).append(op)
            by_id[uid] = op
            added += 1
        path.write_text(json.dumps(cat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{path.name}: +{added}")


if __name__ == "__main__":
    main()
