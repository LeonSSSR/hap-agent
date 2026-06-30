import { history } from '@umijs/max';
import { getAgentActionDefinition, type AgentActionDefinition, type AgentPageActionType } from './AgentActionRegistry';
import { AGENT_DEMO_TIMING, demoPause } from './agentDemoTiming';
import type { AgentMicroStepEvent } from './agentDemoStepTypes';
import {
  currentPathname,
  delay,
  needsRouteNavigation,
  resolveNavigateRoute,
  ROUTE_SETTLE_MS,
  waitForRouteSettled,
} from './agentPageRoute';

export type AgentExecuteOptions = {
  onMicroStep?: (event: AgentMicroStepEvent) => void;
};

export type AgentPageActionStep = {
  id?: string;
  title?: string;
  description?: string;
  step_type?: string;
  action_type?: string;
  page_action?: string;
  ui_action_id?: string;
  uiActionId?: string;
  selector?: string;
  route?: string;
  navigate_route?: string;
  route_params?: Record<string, string | undefined>;
  value?: string;
};

export type AgentPageActionResult = {
  success: boolean;
  actionId?: string;
  message: string;
  error?: string;
  element?: HTMLElement | null;
  ok: boolean;
  uiActionId?: string;
};

const STYLE_ID = 'agent-page-controller-style';
const CORNERS_ROOT_ID = 'agent-page-controller-highlight-corners';
const HIGHLIGHT_CLASS = 'agent-page-controller-highlight-outline';
const TARGET_ATTR = 'data-agent-highlight-active';
const DEFAULT_WAIT_TIMEOUT_MS = 8000;
/** 超过此面积用角标描边，避免整块 div 被上层 fixed 层盖住表格等内容 */
const LARGE_TARGET_AREA_PX = 320 * 100;
const CORNER_ARM_PX = 22;
const CORNER_THICK_PX = 3;
const CORNER_OUTSET_PX = 4;

let highlightTarget: HTMLElement | null = null;
let detachCornerListeners: (() => void) | null = null;

function ensureHighlightStyle() {
  if (typeof document === 'undefined' || document.getElementById(STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = `
    .${HIGHLIGHT_CLASS} {
      outline: 3px solid rgba(239, 68, 68, 0.95) !important;
      outline-offset: 4px !important;
    }
    #${CORNERS_ROOT_ID} {
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 10020;
      overflow: hidden;
    }
    #${CORNERS_ROOT_ID} .agent-hl-corner {
      position: fixed;
      width: ${CORNER_ARM_PX}px;
      height: ${CORNER_ARM_PX}px;
      box-sizing: border-box;
      border-color: rgba(239, 68, 68, 0.95);
      border-style: solid;
      border-width: 0;
    }
    #${CORNERS_ROOT_ID} .agent-hl-corner-tl {
      border-top-width: ${CORNER_THICK_PX}px;
      border-left-width: ${CORNER_THICK_PX}px;
      border-top-left-radius: 6px;
    }
    #${CORNERS_ROOT_ID} .agent-hl-corner-tr {
      border-top-width: ${CORNER_THICK_PX}px;
      border-right-width: ${CORNER_THICK_PX}px;
      border-top-right-radius: 6px;
    }
    #${CORNERS_ROOT_ID} .agent-hl-corner-bl {
      border-bottom-width: ${CORNER_THICK_PX}px;
      border-left-width: ${CORNER_THICK_PX}px;
      border-bottom-left-radius: 6px;
    }
    #${CORNERS_ROOT_ID} .agent-hl-corner-br {
      border-bottom-width: ${CORNER_THICK_PX}px;
      border-right-width: ${CORNER_THICK_PX}px;
      border-bottom-right-radius: 6px;
    }
  `;
  document.head.appendChild(style);
}

function elementArea(element: HTMLElement): number {
  const rect = element.getBoundingClientRect();
  return rect.width * rect.height;
}

/** 大容器优先收窄到内部按钮/可操作控件，避免整表被框住 */
export function pickHighlightTarget(root: HTMLElement): HTMLElement {
  const rootArea = elementArea(root);
  if (rootArea <= LARGE_TARGET_AREA_PX) return root;

  const actionId = root.getAttribute('data-agent-action-id');
  if (actionId) {
    const sameIdNodes = Array.from(
      root.querySelectorAll<HTMLElement>(`[data-agent-action-id="${CSS.escape(actionId)}"]`),
    );
    const smaller = sameIdNodes
      .filter((el) => el !== root)
      .map((el) => ({ el, area: elementArea(el) }))
      .filter((item) => item.area > 0 && item.area < rootArea * 0.9)
      .sort((a, b) => a.area - b.area);
    if (smaller.length > 0) return smaller[0].el;
  }

  const interactives = Array.from(
    root.querySelectorAll<HTMLElement>(
      'button:not([disabled]), .ant-btn:not(.ant-btn-disabled), a.ant-btn, [role="button"]:not([aria-disabled="true"])',
    ),
  );
  for (const el of interactives) {
    const area = elementArea(el);
    if (area > 0 && area < rootArea * 0.55) return el;
  }

  const compact = Array.from(
    root.querySelectorAll<HTMLElement>('input, textarea, .ant-input, .ant-select-selector'),
  );
  for (const el of compact) {
    const area = elementArea(el);
    if (area > 0 && area < rootArea * 0.4) return el;
  }

  return root;
}

function clearCornerHighlights() {
  const root = document.getElementById(CORNERS_ROOT_ID);
  root?.remove();
}

function positionCornerHighlights(element: HTMLElement) {
  if (typeof document === 'undefined') return;
  let root = document.getElementById(CORNERS_ROOT_ID);
  if (!root) {
    root = document.createElement('div');
    root.id = CORNERS_ROOT_ID;
    root.setAttribute('aria-hidden', 'true');
    ['tl', 'tr', 'bl', 'br'].forEach((key) => {
      const corner = document.createElement('div');
      corner.className = `agent-hl-corner agent-hl-corner-${key}`;
      root!.appendChild(corner);
    });
    document.body.appendChild(root);
  }

  const rect = element.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) {
    root.style.display = 'none';
    return;
  }
  root.style.display = 'block';

  const left = rect.left - CORNER_OUTSET_PX;
  const top = rect.top - CORNER_OUTSET_PX;
  const right = rect.right + CORNER_OUTSET_PX;
  const bottom = rect.bottom + CORNER_OUTSET_PX;

  const tl = root.querySelector('.agent-hl-corner-tl') as HTMLElement | null;
  const tr = root.querySelector('.agent-hl-corner-tr') as HTMLElement | null;
  const bl = root.querySelector('.agent-hl-corner-bl') as HTMLElement | null;
  const br = root.querySelector('.agent-hl-corner-br') as HTMLElement | null;

  if (tl) {
    tl.style.left = `${left}px`;
    tl.style.top = `${top}px`;
  }
  if (tr) {
    tr.style.left = `${right - CORNER_ARM_PX}px`;
    tr.style.top = `${top}px`;
  }
  if (bl) {
    bl.style.left = `${left}px`;
    bl.style.top = `${bottom - CORNER_ARM_PX}px`;
  }
  if (br) {
    br.style.left = `${right - CORNER_ARM_PX}px`;
    br.style.top = `${bottom - CORNER_ARM_PX}px`;
  }
}

function attachCornerListeners(element: HTMLElement) {
  detachCornerListeners?.();
  const update = () => positionCornerHighlights(element);
  window.addEventListener('scroll', update, true);
  window.addEventListener('resize', update);
  let ro: ResizeObserver | null = null;
  if (typeof ResizeObserver !== 'undefined') {
    ro = new ResizeObserver(update);
    ro.observe(element);
  }
  detachCornerListeners = () => {
    window.removeEventListener('scroll', update, true);
    window.removeEventListener('resize', update);
    ro?.disconnect();
    detachCornerListeners = null;
  };
}

function markHighlightTarget(element: HTMLElement | null) {
  if (typeof document === 'undefined') return;
  document.querySelectorAll(`[${TARGET_ATTR}="true"]`).forEach((node) => {
    node.removeAttribute(TARGET_ATTR);
  });
  if (element) {
    element.setAttribute(TARGET_ATTR, 'true');
  }
}

function clearOutlineHighlight() {
  document.querySelectorAll(`.${HIGHLIGHT_CLASS}`).forEach((node) => {
    node.classList.remove(HIGHLIGHT_CLASS);
  });
  document.querySelectorAll('.agent-page-controller-highlight').forEach((node) => {
    node.classList.remove('agent-page-controller-highlight');
  });
}

function applyHighlight(element: HTMLElement) {
  ensureHighlightStyle();
  const target = pickHighlightTarget(element);
  highlightTarget = target;
  markHighlightTarget(target);

  const useCorners = elementArea(target) > LARGE_TARGET_AREA_PX;
  clearOutlineHighlight();
  clearCornerHighlights();
  detachCornerListeners?.();

  if (useCorners) {
    positionCornerHighlights(target);
    attachCornerListeners(target);
  } else {
    target.classList.add(HIGHLIGHT_CLASS);
  }
}

function resolveAction(step: AgentPageActionStep): AgentActionDefinition | undefined {
  return getAgentActionDefinition(step.ui_action_id || step.uiActionId);
}

function resolveType(step: AgentPageActionStep, action?: AgentActionDefinition): AgentPageActionType | undefined {
  const explicitType = step.page_action || (step.action_type === 'page_action' ? undefined : step.action_type);
  return (explicitType as AgentPageActionType | undefined) || action?.type;
}

function isElementVisible(element: HTMLElement): boolean {
  if (element.hasAttribute('data-agent-page-root')) return true;
  const style = window.getComputedStyle(element);
  if (style.display === 'contents') return true;
  if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) {
    return false;
  }
  const rect = element.getBoundingClientRect();
  return rect.width > 0 || rect.height > 0;
}

function getElement(selector?: string): HTMLElement | null {
  if (!selector || typeof document === 'undefined') return null;
  const nodes = document.querySelectorAll(selector);
  for (const node of nodes) {
    if (node instanceof HTMLElement && isElementVisible(node)) return node;
  }
  return null;
}

function pageRootSelector(actionId?: string): string | undefined {
  const id = String(actionId || '').trim();
  if (!id) return undefined;
  const escaped = CSS.escape(id);
  return `[data-agent-page-root="${escaped}"], [data-agent-action-id="${escaped}"]`;
}

function buildResult(
  success: boolean,
  actionId: string | undefined,
  message: string,
  options?: { error?: string; element?: HTMLElement | null },
): AgentPageActionResult {
  return {
    success,
    ok: success,
    actionId,
    uiActionId: actionId,
    message,
    error: options?.error,
    element: options?.element,
  };
}

function setNativeValue(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const prototype = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const descriptor = Object.getOwnPropertyDescriptor(prototype, 'value');
  descriptor?.set?.call(element, value);
  element.dispatchEvent(new Event('input', { bubbles: true }));
  element.dispatchEvent(new Event('change', { bubbles: true }));
  element.dispatchEvent(new FocusEvent('blur', { bubbles: true }));
}

const SELECT_VALUE_ALIASES: Record<string, string> = {
  txt: 'text',
  text: 'text',
  文本: 'text',
  tabular: 'tabular',
  table: 'tabular',
  表格: 'tabular',
  image: 'image',
  图像: 'image',
  audio: 'audio',
  音频: 'audio',
  video: 'video',
  视频: 'video',
};

function normalizeSelectValue(value: string): string {
  const raw = String(value || '').trim();
  if (!raw) return '';
  const lower = raw.toLowerCase();
  return SELECT_VALUE_ALIASES[lower] || SELECT_VALUE_ALIASES[raw] || lower;
}

const SELECT_LABEL_TO_VALUE: Record<string, string> = {
  图像: 'image',
  文本: 'text',
  表格: 'tabular',
  音频: 'audio',
  视频: 'video',
};

function isDropdownVisible(dropdown: HTMLElement): boolean {
  if (dropdown.classList.contains('ant-select-dropdown-hidden')) return false;
  const style = window.getComputedStyle(dropdown);
  if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) {
    return false;
  }
  const rect = dropdown.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

function collectVisibleSelectDropdowns(scope: ParentNode): HTMLElement[] {
  return [...scope.querySelectorAll<HTMLElement>('.ant-select-dropdown')].filter(isDropdownVisible);
}

function selectOptionMatchesOption(option: HTMLElement, target: string): boolean {
  if (!target) return false;
  const optionValue = String(
    option.getAttribute('data-value') ||
      option.getAttribute('title') ||
      option.dataset?.value ||
      '',
  )
    .trim()
    .toLowerCase();
  const label = String(option.textContent || '').trim();
  const labelLower = label.toLowerCase();
  const labelValue = SELECT_LABEL_TO_VALUE[label] || SELECT_VALUE_ALIASES[labelLower] || '';

  if (optionValue === target || labelLower === target || labelValue === target) return true;
  if (labelLower.includes(target) || target.includes(labelLower)) return true;
  if (labelValue && labelValue === target) return true;
  if (target.length > 2 && labelLower.includes(target.slice(0, 2))) return true;
  return false;
}

async function waitForSelectDropdowns(selectRoot: HTMLElement, timeoutMs = 1600): Promise<HTMLElement[]> {
  const scopedRoot =
    selectRoot.closest('.ant-modal-content') ||
    selectRoot.closest('.ant-drawer-content') ||
    selectRoot.parentElement ||
    document.body;
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const scoped = collectVisibleSelectDropdowns(scopedRoot);
    if (scoped.length) return scoped;
    const global = collectVisibleSelectDropdowns(document.body);
    if (global.length) return global;
    await delay(80);
  }
  return [];
}

function openAntSelectTrigger(trigger: HTMLElement): void {
  trigger.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
  trigger.click();
  if (typeof trigger.focus === 'function') trigger.focus();
}

async function pickSelectOption(dropdowns: HTMLElement[], target: string): Promise<boolean> {
  for (const dropdown of dropdowns) {
    const options = dropdown.querySelectorAll<HTMLElement>('.ant-select-item-option');
    for (const option of options) {
      if (!selectOptionMatchesOption(option, target)) continue;
      option.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
      option.click();
      await delay(80);
      return true;
    }
  }
  return false;
}

async function fillAntSelect(element: HTMLElement, value: string): Promise<boolean> {
  const selectRoot =
    (element.closest('.ant-select') as HTMLElement | null) ||
    (element.classList.contains('ant-select') ? element : null);
  if (!selectRoot) return false;

  const trigger =
    (selectRoot.querySelector('.ant-select-selector') as HTMLElement | null) ||
    (selectRoot.querySelector('[role="combobox"]') as HTMLElement | null) ||
    selectRoot;
  const target = normalizeSelectValue(value);
  if (!target) return false;

  for (let attempt = 0; attempt < 4; attempt += 1) {
    openAntSelectTrigger(trigger);
    const dropdowns = await waitForSelectDropdowns(selectRoot);
    if (dropdowns.length && (await pickSelectOption(dropdowns, target))) {
      return true;
    }
    await delay(100);
  }
  return false;
}

async function waitForActionReady(
  actionId: string | undefined,
  action: AgentActionDefinition | undefined,
  navigateTarget: string,
  options?: { waitSelector?: string },
): Promise<AgentPageActionResult | null> {
  const settled = await waitForRouteSettled(navigateTarget, DEFAULT_WAIT_TIMEOUT_MS);
  if (!settled) {
    return buildResult(false, actionId, `页面跳转超时：${navigateTarget}`, { error: 'route_navigation_timeout' });
  }

  await delay(ROUTE_SETTLE_MS);

  const selector = options?.waitSelector ?? action?.selector;
  if (selector) {
    const readyElement = await AgentPageController.waitForElement(selector, DEFAULT_WAIT_TIMEOUT_MS);
    if (!readyElement) {
      return buildResult(false, actionId, `页面已跳转，但等待目标元素超时：${selector}`, {
        error: 'page_ready_timeout',
      });
    }
    return null;
  }

  const rootSelector = pageRootSelector(actionId);
  if (rootSelector) {
    const root = await AgentPageController.waitForElement(rootSelector, DEFAULT_WAIT_TIMEOUT_MS);
    if (!root) {
      return buildResult(false, actionId, `页面已跳转，但等待页面根节点超时：${rootSelector}`, {
        error: 'page_ready_timeout',
      });
    }
  }

  return null;
}

async function ensureRouteReady(
  step: AgentPageActionStep,
  action: AgentActionDefinition | undefined,
  actionId: string | undefined,
): Promise<AgentPageActionResult | null> {
  const catalogRoute = step.route || action?.route;
  const navigateTarget = resolveNavigateRoute(catalogRoute, step.navigate_route, step.route_params);
  if (!navigateTarget) {
    if (action?.selector) {
      await delay(ROUTE_SETTLE_MS);
      const readyElement = await AgentPageController.waitForElement(action.selector, DEFAULT_WAIT_TIMEOUT_MS);
      if (!readyElement) {
        return buildResult(false, actionId, `当前页面等待目标元素超时：${action.selector}`, {
          error: 'page_ready_timeout',
        });
      }
    }
    return null;
  }

  if (needsRouteNavigation(currentPathname(), navigateTarget)) {
    history.push(navigateTarget);
    return waitForActionReady(actionId, action, navigateTarget);
  }

  if (action?.selector) {
    await delay(ROUTE_SETTLE_MS);
    const readyElement = await AgentPageController.waitForElement(action.selector, DEFAULT_WAIT_TIMEOUT_MS);
    if (!readyElement) {
      return buildResult(false, actionId, `当前页面等待目标元素超时：${action.selector}`, {
        error: 'page_ready_timeout',
      });
    }
  }
  return null;
}

function isElementDisabled(element: HTMLElement): boolean {
  if (element instanceof HTMLButtonElement || element instanceof HTMLInputElement) return element.disabled;
  if (element.getAttribute('disabled') != null) return true;
  if (element.getAttribute('aria-disabled') === 'true') return true;
  return element.classList.contains('ant-btn-disabled') || element.classList.contains('disabled');
}

const LINEAGE_CREATE_MODAL_ACTIONS = new Set([
  'lineage.project.create.panel',
  'lineage.project.name.fill',
  'lineage.project.datatype.select',
  'lineage.project.description.fill',
  'lineage.project.submit',
  'lineage.project.cancel',
]);

async function ensureLineageCreateModalOpen(actionId?: string): Promise<void> {
  if (!actionId || !LINEAGE_CREATE_MODAL_ACTIONS.has(actionId)) return;
  if (getElement('[data-agent-action-id="lineage.project.create.panel"]')) return;
  const openBtn = getElement('[data-agent-action-id="lineage.project.create"]');
  if (!openBtn) return;
  openBtn.click();
  await delay(500);
}

function emitMicroStep(
  options: AgentExecuteOptions | undefined,
  index: number,
  total: number,
  label: string,
  phase: AgentMicroStepEvent['phase'],
) {
  options?.onMicroStep?.({ phase, label, index, total });
}

async function demoHighlightElement(element: HTMLElement) {
  const target = pickHighlightTarget(element);
  target.scrollIntoView({ behavior: 'smooth', block: 'center' });
  applyHighlight(element);
  await demoPause(AGENT_DEMO_TIMING.highlightHoldMs);
}

function resolveActionSelector(
  step: AgentPageActionStep,
  action: AgentActionDefinition | undefined,
  actionId: string | undefined,
): string | undefined {
  const projectId = step.route_params?.id;
  if (projectId && actionId === 'lineage.project.select') {
    return `[data-agent-action-id="lineage.project.select.${CSS.escape(String(projectId))}"]`;
  }
  return step.selector || action?.selector;
}

export const AgentPageController = {
  clearHighlight() {
    if (typeof document === 'undefined') return;
    detachCornerListeners?.();
    highlightTarget = null;
    markHighlightTarget(null);
    clearOutlineHighlight();
    clearCornerHighlights();
  },

  /** 外描边/四角标高亮：不覆盖目标区域内部像素，框内内容始终可见 */
  highlightElement(element: HTMLElement) {
    this.clearHighlight();
    applyHighlight(element);
  },

  async highlightStep(
    step: AgentPageActionStep,
    options?: AgentExecuteOptions,
  ): Promise<AgentPageActionResult> {
    const action = resolveAction(step);
    const actionId = step.ui_action_id || step.uiActionId || action?.uiActionId;
    const selector = resolveActionSelector(step, action, actionId);

    if (!selector) {
      return buildResult(false, actionId, '当前步骤没有可高亮的目标元素', { error: 'missing_selector' });
    }

    const navErr = await (async () => {
      emitMicroStep(options, 0, 3, '准备页面', 'start');
      const err = await ensureRouteReady(step, action, actionId);
      emitMicroStep(options, 0, 3, '准备页面', 'complete');
      return err;
    })();
    if (navErr) return navErr;
    await demoPause(AGENT_DEMO_TIMING.beforeActMs);

    emitMicroStep(options, 1, 3, '定位控件', 'start');
    const element = await this.waitForElement(selector, DEFAULT_WAIT_TIMEOUT_MS);
    emitMicroStep(options, 1, 3, '定位控件', 'complete');
    if (!element) {
      return buildResult(false, actionId, `未找到页面元素：${selector}`, { error: 'element_not_found' });
    }
    await demoPause(AGENT_DEMO_TIMING.beforeActMs);

    emitMicroStep(options, 2, 3, '高亮目标', 'start');
    this.clearHighlight();
    await demoHighlightElement(element);
    const target = pickHighlightTarget(element);
    const pinned = target;
    window.setTimeout(() => {
      if (highlightTarget === pinned && elementArea(pinned) > LARGE_TARGET_AREA_PX) {
        positionCornerHighlights(pinned);
      }
    }, 350);
    emitMicroStep(options, 2, 3, '高亮目标', 'complete');

    return buildResult(true, actionId, '已高亮当前执行步骤', { element: target });
  },

  async runSteps(
    steps: AgentPageActionStep[],
    options?: AgentExecuteOptions,
  ): Promise<AgentPageActionResult[]> {
    const results: AgentPageActionResult[] = [];
    for (const step of steps) {
      if (step.step_type === 'page_action' || step.action_type === 'page_action' || step.page_action) {
        results.push(await this.execute(step, options));
      } else {
        results.push(await this.highlightStep(step, options));
      }
    }
    return results;
  },

  async runQueryWorkflow(target: { query?: string; route?: string; inputSelector?: string; submitSelector?: string; resultSelector?: string }): Promise<AgentPageActionResult[]> {
    const steps: AgentPageActionStep[] = [
      { ui_action_id: 'query.navigate', page_action: 'navigate', route: target.route || '/query', title: '跳转查询页面' },
      { ui_action_id: 'query.input', step_type: 'highlight', selector: target.inputSelector, title: '高亮查询输入框' },
      { ui_action_id: 'query.fillInput', page_action: 'fill', selector: target.inputSelector, value: target.query || '', title: '填入查询条件' },
      { ui_action_id: 'query.submitButton', step_type: 'highlight', selector: target.submitSelector, title: '高亮查询按钮' },
      { ui_action_id: 'query.clickSubmit', page_action: 'click', selector: target.submitSelector, title: '点击查询按钮' },
      { ui_action_id: 'query.result.area', step_type: 'highlight', selector: target.resultSelector, title: '高亮查询结果区域' },
    ];
    return this.runSteps(steps);
  },

  waitForElement(selector?: string, timeoutMs = DEFAULT_WAIT_TIMEOUT_MS): Promise<HTMLElement | null> {
    if (!selector || typeof document === 'undefined') return Promise.resolve(null);
    const existing = getElement(selector);
    if (existing) return Promise.resolve(existing);

    return new Promise((resolve) => {
      const startedAt = Date.now();
      let timer: number | undefined;
      const observer = new MutationObserver(() => {
        const el = getElement(selector);
        if (el) {
          if (timer) window.clearTimeout(timer);
          observer.disconnect();
          resolve(el);
        } else if (Date.now() - startedAt >= timeoutMs) {
          observer.disconnect();
          resolve(null);
        }
      });

      observer.observe(document.body, { childList: true, subtree: true });
      timer = window.setTimeout(() => {
        observer.disconnect();
        resolve(getElement(selector));
      }, timeoutMs);
    });
  },

  async execute(step: AgentPageActionStep, options?: AgentExecuteOptions): Promise<AgentPageActionResult> {
    const action = resolveAction(step);
    const actionId = step.ui_action_id || step.uiActionId || action?.uiActionId;
    await ensureLineageCreateModalOpen(actionId);
    const type = resolveType(step, action);
    const selector = resolveActionSelector(step, action, actionId);
    const route = step.route || action?.route;
    const value = step.value ?? action?.value ?? '';

    if (!type) {
      return buildResult(false, actionId, '未识别页面动作类型', { error: 'unknown_action_type' });
    }

    if (type === 'clearHighlight') {
      this.clearHighlight();
      return buildResult(true, actionId, '已清除高亮');
    }

    if (type === 'navigate') {
      const navigateTarget = resolveNavigateRoute(route, step.navigate_route, step.route_params) || route;
      if (!navigateTarget) return buildResult(false, actionId, '缺少跳转路由', { error: 'missing_route' });

      emitMicroStep(options, 0, 2, '跳转页面', 'start');
      this.clearHighlight();
      if (needsRouteNavigation(currentPathname(), navigateTarget)) {
        history.push(navigateTarget);
      }
      const readyErr = await waitForActionReady(actionId, undefined, navigateTarget, {
        waitSelector: pageRootSelector(actionId),
      });
      if (readyErr) return readyErr;
      await demoPause(AGENT_DEMO_TIMING.navigateSettleMs);
      emitMicroStep(options, 0, 2, '跳转页面', 'complete');

      const rootSelector = pageRootSelector(actionId);
      if (rootSelector) {
        const root = await this.waitForElement(rootSelector, DEFAULT_WAIT_TIMEOUT_MS);
        if (root) {
          emitMicroStep(options, 1, 2, '高亮页面区域', 'start');
          await demoHighlightElement(root);
          emitMicroStep(options, 1, 2, '高亮页面区域', 'complete');
        }
      }

      return buildResult(true, actionId, `已跳转到 ${navigateTarget}`);
    }

    emitMicroStep(options, 0, 4, '准备页面', 'start');
    const navErr = await ensureRouteReady(step, action, actionId);
    emitMicroStep(options, 0, 4, '准备页面', 'complete');
    if (navErr) return navErr;
    await demoPause(AGENT_DEMO_TIMING.beforeActMs);

    emitMicroStep(options, 1, 4, '定位控件', 'start');
    const element = await this.waitForElement(selector, DEFAULT_WAIT_TIMEOUT_MS);
    emitMicroStep(options, 1, 4, '定位控件', 'complete');
    if (!element) {
      return buildResult(false, actionId, `未找到页面元素：${selector || actionId || '-'}`, {
        error: 'element_not_found',
      });
    }
    await demoPause(AGENT_DEMO_TIMING.beforeActMs);

    if (type === 'scrollIntoView') {
      emitMicroStep(options, 2, 3, '滚动到目标', 'start');
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      await demoPause(AGENT_DEMO_TIMING.highlightHoldMs);
      emitMicroStep(options, 2, 3, '滚动到目标', 'complete');
      return buildResult(true, actionId, '已滚动到目标元素', { element });
    }

    if (type === 'highlight') {
      emitMicroStep(options, 2, 3, '高亮目标', 'start');
      this.clearHighlight();
      await demoHighlightElement(element);
      emitMicroStep(options, 2, 3, '高亮目标', 'complete');
      const target = pickHighlightTarget(element);
      return buildResult(true, actionId, '已高亮目标元素', { element: target });
    }

    emitMicroStep(options, 2, 4, '高亮目标', 'start');
    this.clearHighlight();
    await demoHighlightElement(element);
    emitMicroStep(options, 2, 4, '高亮目标', 'complete');
    await demoPause(AGENT_DEMO_TIMING.beforeActMs);

    if (type === 'fill') {
      emitMicroStep(options, 3, 4, '填入内容', 'start');
      const selectRoot =
        element.closest('.ant-select') ||
        element.querySelector('.ant-select') ||
        (element.classList.contains('ant-select') ? element : null);
      if (selectRoot instanceof HTMLElement && step.value) {
        const selected = await fillAntSelect(element, value);
        await demoPause(AGENT_DEMO_TIMING.afterActionMs);
        emitMicroStep(options, 3, 4, '填入内容', 'complete');
        if (selected) {
          return buildResult(true, actionId, `已选择：${value}`, { element });
        }
        return buildResult(false, actionId, `未找到下拉选项：${value}`, { error: 'select_option_not_found', element });
      }
      const input = element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement
        ? element
        : element.querySelector('input, textarea');
      if (!(input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement)) {
        emitMicroStep(options, 3, 4, '填入内容', 'complete');
        return buildResult(false, actionId, '目标元素不是可输入控件', { error: 'not_input_element', element });
      }
      input.focus();
      setNativeValue(input, value);
      input.blur();
      await demoPause(AGENT_DEMO_TIMING.afterActionMs);
      emitMicroStep(options, 3, 4, '填入内容', 'complete');
      return buildResult(true, actionId, `已填入：${value}`, { element: input });
    }

    if (type === 'click') {
      emitMicroStep(options, 3, 4, '执行点击', 'start');
      if (isElementDisabled(element)) {
        emitMicroStep(options, 3, 4, '执行点击', 'complete');
        return buildResult(false, actionId, '目标按钮处于禁用状态，未执行点击', {
          error: 'button_disabled',
          element,
        });
      }
      element.click();
      await demoPause(AGENT_DEMO_TIMING.afterActionMs);
      emitMicroStep(options, 3, 4, '执行点击', 'complete');
      return buildResult(true, actionId, '已点击目标元素', { element });
    }

    return buildResult(false, actionId, `暂不支持页面动作：${type}`, { error: 'unsupported_action_type' });
  },
};
