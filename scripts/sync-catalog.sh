#!/usr/bin/env bash
# 将 catalog/ 同步到 backend 与 frontend agent-ui（单一权威源）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/catalog/platform_operations_catalog.json"
DST_BE="$ROOT/backend/agent-service/data/platform_operations_catalog.json"
DST_FE="$ROOT/frontend/packages/agent-ui/src/components/AgentShell/platformOperationsCatalog.json"

if [[ ! -f "$SRC" ]]; then
  echo "missing $SRC" >&2
  exit 1
fi
mkdir -p "$(dirname "$DST_BE")" "$(dirname "$DST_FE")"
cp "$SRC" "$DST_BE"
cp "$SRC" "$DST_FE"
echo "Synced catalog -> backend + frontend ($(wc -c < "$SRC") bytes)"
