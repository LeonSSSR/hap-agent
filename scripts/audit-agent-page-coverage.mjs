#!/usr/bin/env node
/**
 * 逐页审计：菜单路由 ↔ catalog 页面级 ↔ 子操作 ↔ 源码锚点
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const catalogPath = path.join(root, 'src/components/AgentShell/platformOperationsCatalog.json');
const umircPath = path.join(root, '.umirc.ts');

const MENU_ROUTES = [
  '/home', '/dashboard', '/lineage', '/data-map',
  '/data-governance/sources', '/data-governance/sync', '/data-governance/datasets',
  '/data-governance/schedule', '/data-governance/service', '/data-governance/sofelink',
  '/data-governance/kafka', '/data-governance/kafka/overview', '/data-governance/kafka/topics',
  '/data-governance/kafka/topics-new', '/data-governance/kafka/consumer-groups',
  '/data-governance/kafka/messages', '/data-governance/kafka/cluster', '/data-governance/kafka/alerts',
  '/data-governance/kafka/governance', '/data-governance/kafka/audit', '/data-governance/kafka/workbench',
  '/data-governance/kafka/settings', '/data-governance/kafka/offset-reset',
  '/data-processing/navigation', '/data-processing/labeling', '/data-processing/transform',
  '/data-processing/augmentation', '/data-processing/quality', '/data-processing/cleaning',
  '/data-processing/exploration',
  '/data-processing/feature/processing', '/data-processing/feature/registry',
  '/data-processing/feature/monitor', '/data-processing/feature/drift-alert',
  '/data-processing/feature/statistics', '/data-processing/split',
  '/model-dev/notebooks', '/model-dev/pipelines/workspace', '/model-dev/pipelines/runs',
  '/model-dev/pipelines/components', '/model-dev/pipelines/templates', '/model-dev/pipelines/recurring',
  '/model-dev/training', '/model-dev/katib', '/model-dev/algorithms', '/model-dev/collaboration',
  '/model-app/model-versions', '/model-app/evaluation', '/model-app/service-publish',
  '/model-app/service-deploy', '/model-app/service-invoke', '/model-app/service-monitor',
  '/model-app/cicd', '/model-app/infer-logs', '/model-app/feature-drift',
  '/system/users', '/system/security', '/system/audit', '/system/config', '/system/notification',
  '/super-admin/tenants', '/env/image', '/env/storage', '/env/monitor',
];

const catalog = JSON.parse(fs.readFileSync(catalogPath, 'utf8'));
const ops = catalog.operations;

function walk(dir, acc = []) {
  if (!fs.existsSync(dir)) return acc;
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    if (fs.statSync(full).isDirectory()) walk(full, acc);
    else if (/\.(tsx|ts|jsx|js)$/.test(name)) acc.push(full);
  }
  return acc;
}

const sourceFiles = [
  ...walk(path.join(root, 'src/pages')),
  ...walk(path.join(root, 'src/components/AgentShell')),
];
const sourceBlob = sourceFiles.map((f) => fs.readFileSync(f, 'utf8')).join('\n');

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

function hasAnchor(id) {
  const direct = [
    `data-agent-action-id="${id}"`,
    `'data-agent-action-id': '${id}'`,
    `"data-agent-action-id": "${id}"`,
    `agentActionId: '${id}'`,
    `agentActionId: "${id}"`,
    `buttonProps: { 'data-agent-action-id': '${id}' }`,
  ];
  if (direct.some((p) => sourceBlob.includes(p))) return true;
  if (
    (sourceBlob.includes(`'${id}'`) || sourceBlob.includes(`"${id}"`))
    && sourceBlob.includes('data-agent-action-id')
  ) {
    for (const file of sourceFiles) {
      const text = fs.readFileSync(file, 'utf8');
      if (!text.includes('data-agent-action-id')) continue;
      if (text.includes(`'${id}'`) || text.includes(`"${id}"`)) return true;
    }
  }
  for (const { prefix, markers } of DYNAMIC_ANCHOR_PREFIXES) {
    if (id.startsWith(prefix) || id === prefix) {
      if (markers.some((m) => sourceBlob.includes(m))) return true;
    }
  }
  return false;
}

const pages = ops.filter((o) => !o.parent_ui_action_id);
const childrenByParent = {};
for (const o of ops) {
  const p = o.parent_ui_action_id;
  if (!p) continue;
  (childrenByParent[p] ||= []).push(o);
}

// 与 platformOperationsMap.byRoutePath 一致：同路由取 catalog 中首次出现的页面级条目
const routeToPage = {};
const routeCollisions = {};
for (const p of pages) {
  const r = String(p.route || '').split('?')[0].trim();
  if (!r) continue;
  if (routeToPage[r]) {
    (routeCollisions[r] ||= [routeToPage[r].ui_action_id]).push(p.ui_action_id);
    continue;
  }
  routeToPage[r] = p;
}

const report = [];

for (const route of MENU_ROUTES) {
  const page = routeToPage[route];
  if (!page) {
    report.push({ route, status: 'FAIL', issue: '无 catalog 页面级条目' });
    continue;
  }
  const children = (childrenByParent[page.ui_action_id] || []).map((c) => ({
    id: c.ui_action_id,
    label: c.label,
    type: c.action_type,
    anchored: hasAnchor(c.ui_action_id),
  }));
  const missing = children.filter((c) => !c.anchored);
  let status = 'OK';
  if (missing.length) status = 'PARTIAL';
  else if (!children.length) status = 'WARN_NO_CHILD';

  report.push({
    route,
    pageId: page.ui_action_id,
    pageLabel: page.label,
    pageNavigate: true,
    runtimeRootAnchor: `PlatformAgentPageRoot → data-agent-page-root="${page.ui_action_id}"`,
    childCount: children.length,
    children,
    missingIds: missing.map((m) => m.id),
    status,
  });
}

const extraPages = pages.filter((p) => !MENU_ROUTES.includes(String(p.route || '').split('?')[0]));
for (const page of extraPages) {
  const route = String(page.route || '').split('?')[0];
  const children = (childrenByParent[page.ui_action_id] || []).map((c) => ({
    id: c.ui_action_id,
    label: c.label,
    type: c.action_type,
    anchored: hasAnchor(c.ui_action_id),
  }));
  const missing = children.filter((c) => !c.anchored);
  report.push({
    route,
    pageId: page.ui_action_id,
    pageLabel: page.label,
    note: '非菜单页（Agent 扩展能力）',
    childCount: children.length,
    children,
    missingIds: missing.map((m) => m.id),
    status: missing.length ? 'PARTIAL' : 'OK_EXTRA',
  });
}

const menuReport = report.filter((r) => MENU_ROUTES.includes(r.route));
const summary = {
  catalogVersion: catalog.version,
  totalOps: ops.length,
  menuPages: MENU_ROUTES.length,
  ok: menuReport.filter((r) => r.status === 'OK').length,
  partial: menuReport.filter((r) => r.status === 'PARTIAL').length,
  fail: menuReport.filter((r) => r.status === 'FAIL').length,
  warnNoChild: menuReport.filter((r) => r.status === 'WARN_NO_CHILD').length,
  extraPages: extraPages.length,
  totalChildOps: ops.filter((o) => o.parent_ui_action_id).length,
  anchoredChildOps: ops.filter((o) => o.parent_ui_action_id && hasAnchor(o.ui_action_id)).length,
};

const globalAgentPage = pages.find((p) => p.ui_action_id === 'agent.workflow');
const globalAgentChildren = globalAgentPage
  ? (childrenByParent[globalAgentPage.ui_action_id] || []).map((c) => c.ui_action_id)
  : [];

const out = { summary, routeCollisions, globalAgentPanel: globalAgentPage, pages: report };
const outPath = path.join(root, 'scripts/.agent-page-coverage-audit.json');
fs.writeFileSync(outPath, JSON.stringify(out, null, 2));

console.log('=== Agent 逐页覆盖审计 ===');
console.log(`catalog v${summary.catalogVersion} | 总操作 ${summary.totalOps} | 子操作 ${summary.totalChildOps}`);
console.log(`菜单页 ${summary.menuPages}: 全覆盖 ${summary.ok} | 部分缺失 ${summary.partial} | 无条目 ${summary.fail} | 无子操作 ${summary.warnNoChild}`);
console.log(`子操作锚点: ${summary.anchoredChildOps}/${summary.totalChildOps}`);
console.log('');

for (const row of menuReport) {
  const icon = row.status === 'OK' ? '✓' : row.status === 'PARTIAL' ? '△' : '✗';
  const childBrief = row.children?.map((c) => `${c.id}(${c.type[0]})`).join(', ') || '-';
  console.log(`${icon} ${row.route}`);
  console.log(`   页: ${row.pageId} — ${row.pageLabel} | 子操作 ${row.childCount}`);
  if (row.missingIds?.length) console.log(`   缺锚点: ${row.missingIds.join(', ')}`);
  else console.log(`   子操作: ${childBrief}`);
}

if (globalAgentPage) {
  console.log('\n--- 全局 Agent 面板（任意页面可用）---');
  console.log(`✓ ${globalAgentPage.route} | ${globalAgentPage.ui_action_id} | 子操作 ${globalAgentChildren.length}`);
  console.log(`   ${globalAgentChildren.join(', ')}`);
}
if (Object.keys(routeCollisions).length) {
  console.log('\n--- 路由冲突（运行时取 catalog 首条）---');
  for (const [r, ids] of Object.entries(routeCollisions)) {
    console.log(`   ${r}: ${ids.join(' → ')}`);
  }
}
if (extraPages.length) {
  console.log('\n--- 非菜单扩展页 ---');
  for (const row of report.filter((r) => r.note)) {
    console.log(`✓ ${row.route} | ${row.pageId} | 子操作 ${row.childCount}`);
  }
}

if (summary.partial || summary.fail || summary.warnNoChild) {
  process.exit(1);
}
console.log('\n全部菜单页 Agent 操作能力已全覆盖。');
