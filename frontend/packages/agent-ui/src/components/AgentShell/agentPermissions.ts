/** Agent 确认栏权限判断（与后端 risk_level 对齐）。 */

const ADMIN_ROLE_CODES = new Set([
  'admin',
  'super_admin',
  'superadmin',
  'tenant_admin',
  'system',
]);

function normalizeRoleSet(roles: string[] = []): Set<string> {
  return new Set(roles.map((role) => String(role).trim().toLowerCase()).filter(Boolean));
}

function hasAdminOrApproverRole(roleSet: Set<string>): boolean {
  if (roleSet.has('approver')) return true;
  for (const role of roleSet) {
    if (ADMIN_ROLE_CODES.has(role)) return true;
  }
  return false;
}

export function canConfirmAgenticTool(
  riskLevel: string,
  permissions: string[] = [],
  roles: string[] = [],
): boolean {
  const risk = String(riskLevel || 'low').toLowerCase();
  const roleSet = normalizeRoleSet(roles);
  const permSet = new Set(permissions.map((p) => String(p).trim()).filter(Boolean));
  if (risk === 'high') {
    return (
      hasAdminOrApproverRole(roleSet)
      || permSet.has('model.publish.approve')
      || permSet.has('inference.deploy.write')
      || permSet.has('ml.lifecycle.execute')
    );
  }
  if (risk === 'medium') {
    return (
      hasAdminOrApproverRole(roleSet)
      || permSet.has('ml.lifecycle.execute')
      || permSet.size > 0
    );
  }
  return true;
}

export function agentConfirmDeniedHint(riskLevel: string): string {
  const risk = String(riskLevel || 'low').toLowerCase();
  if (risk === 'high') {
    return '当前账号无高风险操作审批权限，请拒绝或联系管理员。';
  }
  if (risk === 'medium') {
    return '当前账号无中风险操作确认权限，请拒绝或联系管理员。';
  }
  return '当前账号无执行权限。';
}
