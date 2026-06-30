export const STORAGE_EXPANDED_KEY = 'hap-agent-panel-expanded';
export const HAP_AGENT_OPEN_EVENT = 'hap-agent:open';
export const HAP_AGENT_CLOSE_EVENT = 'hap-agent:close';

export function openHapAgentPanel(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_EXPANDED_KEY, '1');
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new CustomEvent(HAP_AGENT_OPEN_EVENT));
}

export function closeHapAgentPanel(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_EXPANDED_KEY, '0');
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new CustomEvent(HAP_AGENT_CLOSE_EVENT));
}

export function readHapAgentPanelExpanded(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    const raw = window.localStorage.getItem(STORAGE_EXPANDED_KEY);
    if (raw === '1') return true;
    if (raw === '0') return false;
  } catch {
    /* ignore */
  }
  return false;
}
