#!/usr/bin/env node
/**
 * 校验 catalog 可执行子操作均在 AgentActionRegistry 中有真实 selector（无运行时兜底）。
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const catalogPath = path.join(root, 'src/components/AgentShell/platformOperationsCatalog.json');
const registryPath = path.join(root, 'src/components/AgentShell/AgentActionRegistry.ts');

const catalog = JSON.parse(fs.readFileSync(catalogPath, 'utf8'));
const registrySrc = fs.readFileSync(registryPath, 'utf8');

function extractConstObjectKeys(constName) {
  const marker = `const ${constName}`;
  const start = registrySrc.indexOf(marker);
  if (start < 0) return [];
  const blockStart = registrySrc.indexOf('{', start);
  let depth = 0;
  let end = blockStart;
  for (let i = blockStart; i < registrySrc.length; i += 1) {
    const ch = registrySrc[i];
    if (ch === '{') depth += 1;
    else if (ch === '}') {
      depth -= 1;
      if (depth === 0) {
        end = i + 1;
        break;
      }
    }
  }
  const block = registrySrc.slice(blockStart, end);
  return [...block.matchAll(/^\s+'([^']+)':\s*\{/gm)].map((m) => m[1]);
}

function defaultSelector(uiActionId, actionType) {
  if (actionType === 'fill') {
    return `[data-agent-action-id="${uiActionId}"] input, input[data-agent-action-id="${uiActionId}"], [data-agent-action-id="${uiActionId}"]`;
  }
  return `[data-agent-action-id="${uiActionId}"], [data-agent-page-root="${uiActionId}"]`;
}

const overrideKeys = new Set([
  ...extractConstObjectKeys('BUTTON_ACTION_OVERRIDES'),
  ...extractConstObjectKeys('WORKFLOW_AND_LINEAGE_ACTIONS'),
]);

const registryKeys = new Set();
for (const op of catalog.operations || []) {
  const uiActionId = op.ui_action_id;
  if (!uiActionId) continue;
  registryKeys.add(uiActionId);
  registryKeys.add(`${uiActionId}.open`);
}

for (const op of catalog.operations || []) {
  const uiActionId = op.ui_action_id;
  if (!uiActionId || uiActionId.endsWith('.open')) continue;
  const actionType = String(op.action_type || 'navigate').toLowerCase();
  if (actionType === 'navigate') continue;
  if (overrideKeys.has(uiActionId)) continue;
  registryKeys.add(uiActionId);
}

const executable = (catalog.operations || []).filter((op) => {
  const id = op.ui_action_id;
  if (!id || id.endsWith('.open')) return false;
  const actionType = String(op.action_type || 'navigate').toLowerCase();
  return actionType !== 'navigate';
});

const missing = executable.filter((op) => !registryKeys.has(op.ui_action_id));
const missingSelector = executable.filter((op) => {
  const id = op.ui_action_id;
  if (overrideKeys.has(id)) return false;
  const actionType = String(op.action_type || '').toLowerCase();
  const selector = defaultSelector(id, actionType);
  return !selector.includes('data-agent-action-id');
});

console.log(`executable child ops: ${executable.length}`);
console.log(`registry keys (derived): ${registryKeys.size}`);
console.log(`missing registry entry: ${missing.length}`);

if (missing.length) {
  console.log('\nMissing registry:');
  missing.slice(0, 40).forEach((op) => console.log(' -', op.ui_action_id, op.action_type, op.label));
  process.exit(1);
}
if (missingSelector.length) {
  console.log('\nMissing selector template:');
  missingSelector.forEach((op) => console.log(' -', op.ui_action_id));
  process.exit(1);
}
console.log('\nOK: all executable catalog ops resolve to explicit registry selectors.');
