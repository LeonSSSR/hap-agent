/** 演示慢速：微步骤之间的停顿（毫秒） */
export const AGENT_DEMO_TIMING = {
  /** 高亮保持，让用户看清目标控件 */
  highlightHoldMs: 720,
  /** 高亮完成后、点击/填入前 */
  beforeActMs: 480,
  /** 点击/填入完成后 */
  afterActionMs: 420,
  /** 路由跳转额外等待 */
  navigateSettleMs: 520,
} as const;

export function demoPause(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
