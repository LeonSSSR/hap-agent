/** Route matching and pre-navigation helpers for Agent page actions. */

const POST_NAV_SETTLE_MS = 280;

/** Dynamic detail routes → list/entry routes when :id param is absent (matches Umi routes). */
const ROUTE_LIST_FALLBACKS: Record<string, string> = {
  '/data-governance/datasets/edit/:id': '/data-governance/datasets',
  '/data-processing/labeling/projects/:id': '/data-processing/labeling?tab=projects',
  '/data-governance/annotation/projects/:id': '/data-processing/labeling?tab=projects',
};

const ROUTE_NO_AUTO_NAV = new Set(['/data-governance/projects/:id']);

export type RouteParams = Record<string, string | undefined>;

export function normalizePath(path: string): string {
  const base = String(path || '').split('?')[0].replace(/\/+$/, '');
  return base || '/';
}

function normalizeRouteParams(params?: RouteParams): Record<string, string> {
  if (!params) return {};
  const normalized: Record<string, string> = {};
  for (const [key, value] of Object.entries(params)) {
    const token = String(key || '').trim();
    const text = String(value || '').trim();
    if (token && text) normalized[token] = text;
  }
  return normalized;
}

/** Substitute :param segments; return concrete path or list fallback. */
export function applyRouteParams(route: string, params?: RouteParams): string {
  const raw = String(route || '').trim();
  if (!raw) return '';

  const [pathOnly, query = ''] = raw.split('?');
  let resolved = pathOnly;
  const routeParams = normalizeRouteParams(params);
  for (const [key, value] of Object.entries(routeParams)) {
    resolved = resolved.replace(`:${key}`, encodeURIComponent(value));
  }
  if (!resolved.includes(':')) {
    return query ? `${resolved}?${query}` : resolved;
  }
  if (ROUTE_NO_AUTO_NAV.has(pathOnly)) return '';

  let fallback = ROUTE_LIST_FALLBACKS[pathOnly];
  if (!fallback) {
    const prefix = pathOnly.split('/:')[0];
    for (const [pattern, target] of Object.entries(ROUTE_LIST_FALLBACKS)) {
      if (pattern.startsWith(prefix) || prefix.startsWith(pattern.split('/:')[0])) {
        fallback = target;
        break;
      }
    }
  }
  return fallback || '';
}

/** Whether current pathname matches a catalog route (supports :param segments). */
export function routePatternMatches(pathname: string, route: string): boolean {
  const current = normalizePath(pathname);
  const pattern = normalizePath(route.split('?')[0]);
  if (!pattern) return true;

  const patternParts = pattern.split('/').filter(Boolean);
  const pathParts = current.split('/').filter(Boolean);

  if (route.includes(':')) {
    if (patternParts.length !== pathParts.length) return false;
    for (let i = 0; i < patternParts.length; i += 1) {
      const segment = patternParts[i];
      if (segment.startsWith(':')) continue;
      if (segment !== pathParts[i]) return false;
    }
    return true;
  }

  if (current === pattern) return true;
  if (pathParts.length >= patternParts.length) {
    for (let i = 0; i < patternParts.length; i += 1) {
      if (patternParts[i] !== pathParts[i]) return false;
    }
    return true;
  }
  return false;
}

/** Static or param-expanded route for pre-navigation (uses backend hint when valid). */
export function resolveNavigateRoute(
  rawRoute?: string,
  navigateRouteHint?: string,
  params?: RouteParams,
): string | undefined {
  const hint = String(navigateRouteHint || '').trim();
  if (hint) {
    const hinted = applyRouteParams(hint, params);
    if (hinted && !hinted.includes(':')) return hinted;
  }

  const raw = String(rawRoute || '').trim();
  if (!raw) return hint ? applyRouteParams(hint, params) || undefined : undefined;
  const resolved = applyRouteParams(raw, params);
  return resolved || undefined;
}

export function currentPathname(): string {
  if (typeof window === 'undefined') return '/';
  return normalizePath(window.location.pathname || '/');
}

function parseRouteParts(route: string): { path: string; query: URLSearchParams } {
  const raw = String(route || '').trim();
  const [pathOnly, query = ''] = raw.split('?');
  return { path: normalizePath(pathOnly), query: new URLSearchParams(query) };
}

function queryParamsMatch(expected: URLSearchParams, actual: URLSearchParams): boolean {
  for (const [key, value] of expected.entries()) {
    if (actual.get(key) !== value) return false;
  }
  return true;
}

export function needsRouteNavigation(pathname: string, targetRoute?: string): boolean {
  const route = String(targetRoute || '').trim();
  if (!route) return false;
  const target = parseRouteParts(route);
  if (!routePatternMatches(pathname, target.path)) return true;
  if (typeof window === 'undefined') return false;
  const actualQuery = new URLSearchParams(window.location.search || '');
  return !queryParamsMatch(target.query, actualQuery);
}

export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

/** Wait until SPA pathname (and optional query) matches target route (after history.push). */
export async function waitForRouteSettled(targetRoute: string, timeoutMs = 5000): Promise<boolean> {
  const route = String(targetRoute || '').trim();
  if (!route) return true;
  const target = parseRouteParts(route);

  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (needsRouteNavigation(currentPathname(), route)) {
      await delay(50);
      continue;
    }
    return true;
  }
  return !needsRouteNavigation(currentPathname(), route);
}

export const ROUTE_SETTLE_MS = POST_NAV_SETTLE_MS;
