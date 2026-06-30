#!/usr/bin/env node
/** 一键校验 Agent 页面操作：锚点 + Registry + 菜单覆盖（禁止兜底假数据）。 */
import { spawnSync } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const scripts = [
  'verify-agent-page-anchors.mjs',
  'verify-agent-registry.mjs',
  'audit-agent-page-coverage.mjs',
];

for (const script of scripts) {
  const scriptPath = path.join(__dirname, script);
  console.log(`\n>>> ${script}`);
  const result = spawnSync(process.execPath, [scriptPath], { stdio: 'inherit' });
  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
}
console.log('\nOK: Agent executable ops are fully anchored and registered (no fallback).');
