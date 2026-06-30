import type { AgentQuickPreset } from './agentPresets';
import type { HapPageContextLite } from './agentPresets';
import type { AgentCapabilitiesPayload, AgentHapOperation, AgentMcpTool } from './agentCapabilitiesView';
import {
  PRESET_PANEL_TAGLINE,
  type PresetScenario,
  buildModeSummary,
  buildRecommendedPresets,
  scenariosForModule,
} from './agentPresetCatalog';

export type PresetPanelModel = {
  tagline: string;
  modeSummary: string | null;
  recommended: AgentQuickPreset[];
  scenarios: PresetScenario[];
  pageName: string;
};

export function buildPresetPanelModel(
  ctx: HapPageContextLite,
  capabilities: AgentCapabilitiesPayload | null,
): PresetPanelModel {
  const operations = Array.isArray(capabilities?.hap_operations) ? capabilities.hap_operations : [];
  return {
    tagline: PRESET_PANEL_TAGLINE,
    modeSummary: buildModeSummary(capabilities),
    recommended: buildRecommendedPresets(ctx, operations),
    scenarios: scenariosForModule(ctx.moduleKey),
    pageName: ctx.pageName,
  };
}

export type CapabilityBrowseModel = {
  operationGroups: Array<{
    module: string;
    label: string;
    items: Array<AgentHapOperation & { displaySummary: string }>;
  }>;
  queryGroups: Array<{
    domain: string;
    label: string;
    items: Array<AgentMcpTool & { displayLabel: string; displaySummary: string }>;
  }>;
};
