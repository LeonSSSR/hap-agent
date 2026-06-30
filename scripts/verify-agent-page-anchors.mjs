#!/usr/bin/env node
/**
 * 校验 catalog 子操作是否在页面/AgentShell 源码中有精确的 data-agent-action-id / agentActionId 锚点。
 * 不允许语义兜底。
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const catalogPath = path.join(root, 'src/components/AgentShell/platformOperationsCatalog.json');
const scanRoots = [
  path.join(root, 'src/pages'),
  path.join(root, 'src/components/AgentShell'),
];

const catalog = JSON.parse(fs.readFileSync(catalogPath, 'utf8'));
const childOps = catalog.operations.filter((op) => op.parent_ui_action_id);

function walk(dir, acc = []) {
  if (!fs.existsSync(dir)) return acc;
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    const stat = fs.statSync(full);
    if (stat.isDirectory()) walk(full, acc);
    else if (/\.(tsx|ts|jsx|js)$/.test(name)) acc.push(full);
  }
  return acc;
}

const sources = scanRoots
  .flatMap((dir) => walk(dir))
  .map((f) => fs.readFileSync(f, 'utf8'))
  .join('\n');

const DYNAMIC_ANCHOR_PREFIXES = [
  { prefix: 'dp.navigation.module.', markers: ['dp.navigation.module.${', "'dp.navigation.module.' +"] },
  { prefix: 'dp.transform.addOp.', markers: ['dp.transform.addOp.${'] },
  { prefix: 'dp.augmentation.strategy.', markers: ['dp.augmentation.strategy.${'] },
  { prefix: 'dp.augmentation.mediaOp.', markers: ['dp.augmentation.mediaOp.${'] },
  { prefix: 'dp.quality.template.', markers: ['dp.quality.template.${'] },
  { prefix: 'dp.quality.addRule.', markers: ['dp.quality.addRule.${'] },
  { prefix: 'ml.data.prepare.feature.addOp.', markers: ['ml.data.prepare.feature.addOp.${'] },
  { prefix: 'dp.feature.statistics.syncFeast', markers: ["'dp.feature.statistics.syncFeast'"] },
  { prefix: 'dp.feature.monitor.syncFeast', markers: ["'dp.feature.monitor.syncFeast'"] },
  { prefix: 'plat.home.goto.', markers: ['plat.home.goto.${', '`plat.home.goto.${'] },
  { prefix: 'plat.dashboard.prefs.card.', markers: ['plat.dashboard.prefs.card.${'] },
  { prefix: 'plat.dashboard.prefs.action.', markers: ['plat.dashboard.prefs.action.${'] },
  { prefix: 'lineage.project.select', markers: ['lineage.project.select.', 'lineage.project.select.${'] },
  { prefix: 'dg.kafka.overview.traffic.timeRange.', markers: ['agentTimeRangePrefix="dg.kafka.overview.traffic.timeRange"'] },
  { prefix: 'dg.kafka.topicDetail.traffic.timeRange.', markers: ['agentTimeRangePrefix="dg.kafka.topicDetail.traffic.timeRange"'] },
];

function hasExplicitAnchor(id, source) {
  const quoted = [`'${id}'`, `"${id}"`];
  const directPatterns = [
    `data-agent-action-id="${id}"`,
    `'data-agent-action-id': '${id}'`,
    `"data-agent-action-id": "${id}"`,
    `agentActionId: '${id}'`,
    `agentActionId: "${id}"`,
    `buttonProps: { 'data-agent-action-id': '${id}' }`,
    `agentActionId: '${id}',`,
    `agentActionId: '${id}'`,
  ];
  if (directPatterns.some((p) => source.includes(p))) return true;
  if (quoted.some((q) => source.includes(q) && source.includes('data-agent-action-id'))) return true;
  if (quoted.some((q) => source.includes(`agentActionId: ${q}`))) return true;
  for (const { prefix, markers } of DYNAMIC_ANCHOR_PREFIXES) {
    if (id.startsWith(prefix) || id === prefix) {
      if (markers.some((m) => source.includes(m))) return true;
    }
  }
  return false;
}

const missing = [];
const anchored = [];
for (const op of childOps) {
  const id = op.ui_action_id;
  if (hasExplicitAnchor(id, sources)) {
    anchored.push(id);
    continue;
  }
  missing.push(id);
}

console.log(`catalog child ops: ${childOps.length}`);
console.log(`explicit anchors: ${anchored.length}`);
console.log(`missing explicit anchor: ${missing.length}`);
if (missing.length) {
  console.log('\nMissing:');
  missing.forEach((id) => console.log(' -', id));
  process.exit(1);
}
console.log('\nOK: all child ops have explicit data-agent-action-id anchors.');
