// ---------------------------------------------------------------------------
// Command Center 3D — current disaster-intelligence graph catalog.
//
// This is presentation metadata only. Every key below is an existing node in
// backend/graph/disaster_workflow.py or an existing specialist selected by
// backend/agents/disaster_intelligence.py. Lifecycle state still comes only
// from the existing backend WebSocket event stream.
// ---------------------------------------------------------------------------

import type { AgentKey } from '../realtime/workflowReducer';

export interface VisualAgent {
  /** Existing backend graph key used to join live lifecycle events. */
  key: AgentKey;
  title: string;
  subtitle: string;
  accent: string;
  position: [number, number, number];
}

// The first row is the supervisor, the second row is the conditional parallel
// specialist fan-out, and the lower rows are the sequential operational path.
// `situation_state` is a real graph merge stage; it has no agent lifecycle
// event, so its visual status remains truthful (idle/queued) rather than being
// presented as a fabricated completed agent.
export const VISUAL_AGENTS: readonly VisualAgent[] = [
  { key: 'supervisor', title: 'Supervisor / Incident Commander', subtitle: 'Selects the disaster-analysis path', accent: '#38bdf8', position: [0, 3.2, 0] },

  { key: 'disaster_analysis', title: 'Disaster Analysis Agent', subtitle: 'Classifies the event evidence', accent: '#60a5fa', position: [-5.5, 1.45, 0] },
  { key: 'weather_analysis', title: 'Weather Agent', subtitle: 'Reviews weather and freshness', accent: '#22d3ee', position: [-4.5, 1.45, 1] },
  { key: 'risk_prediction', title: 'Risk Prediction Agent', subtitle: 'Uses the deterministic risk result', accent: '#f97316', position: [-3.5, 1.45, 0] },
  { key: 'geo_vulnerability', title: 'Geo Vulnerability Agent', subtitle: 'Reviews terrain and exposure', accent: '#a78bfa', position: [-2.5, 1.45, 1] },
  { key: 'hydrology_environmental', title: 'Hydrology / Environment Agent', subtitle: 'Reviews rainfall and water signals', accent: '#14b8a6', position: [-1.5, 1.45, 0] },
  { key: 'medical_triage', title: 'Medical Triage Agent', subtitle: 'Assesses injuries and care needs', accent: '#f43f5e', position: [-0.5, 1.45, 1] },
  { key: 'search_rescue', title: 'Search & Rescue Agent', subtitle: 'Assesses rescue requirements', accent: '#facc15', position: [0.5, 1.45, 0] },
  { key: 'security_public_safety', title: 'Security / Public Safety Agent', subtitle: 'Reviews access and safety controls', accent: '#818cf8', position: [1.5, 1.45, 1] },
  { key: 'infrastructure', title: 'Infrastructure Agent', subtitle: 'Reviews infrastructure exposure', accent: '#fb7185', position: [2.5, 1.45, 0] },
  { key: 'shelter', title: 'Shelter Agent', subtitle: 'Reviews shelter readiness', accent: '#34d399', position: [3.5, 1.45, 1] },
  { key: 'hospital', title: 'Hospital Agent', subtitle: 'Reviews hospital capacity', accent: '#2dd4bf', position: [4.5, 1.45, 0] },
  { key: 'communication', title: 'Communication Agent', subtitle: 'Prepares community alerts', accent: '#c084fc', position: [5.5, 1.45, 1] },

  { key: 'situation_state', title: 'Situation State', subtitle: 'Merges specialist evidence', accent: '#94a3b8', position: [0, -0.25, 0] },
  { key: 'resource', title: 'Resource Coordination Agent', subtitle: 'Finds database-backed resources', accent: '#c084fc', position: [-3.6, -1.8, 0] },
  { key: 'rescue_priority', title: 'Rescue Priority Agent', subtitle: 'Ranks rescue requests', accent: '#f59e0b', position: [-1.8, -1.8, 1] },
  { key: 'routing', title: 'Routing Agent', subtitle: 'Selects safe local routes', accent: '#22d3ee', position: [0, -1.8, 0] },
  { key: 'response_planner', title: 'Response Planner Agent', subtitle: 'Builds the approval-gated plan', accent: '#818cf8', position: [1.8, -1.8, 1] },
  { key: 'approval_gate', title: 'Human Approval Gate', subtitle: 'Waits for authorized decisions', accent: '#a855f7', position: [3.6, -1.8, 0] },
  { key: 'monitoring', title: 'Monitoring Agent', subtitle: 'Watches sensors, routes and resources', accent: '#4ade80', position: [2.2, -3.25, 1] },
  { key: 'recovery', title: 'Recovery Agent', subtitle: 'Stands by for stabilization', accent: '#86efac', position: [0, -3.25, 0] },
] as const;

// The actual graph selects a subset of these specialist keys conditionally.
// The static links show that real fan-out; unselected nodes remain idle.
const PARALLEL_SPECIALISTS: readonly AgentKey[] = [
  'disaster_analysis',
  'weather_analysis',
  'risk_prediction',
  'geo_vulnerability',
  'hydrology_environmental',
  'medical_triage',
  'search_rescue',
  'security_public_safety',
  'infrastructure',
  'shelter',
  'hospital',
  'communication',
];

export const APPROVAL_AGENT_KEY: AgentKey = 'approval_gate';

export const AGENT_CONNECTIONS: ReadonlyArray<readonly [AgentKey, AgentKey]> = [
  ...PARALLEL_SPECIALISTS.map((key) => ['supervisor', key] as const),
  ...PARALLEL_SPECIALISTS.map((key) => [key, 'situation_state'] as const),
  ['situation_state', 'resource'],
  ['resource', 'rescue_priority'],
  ['rescue_priority', 'routing'],
  ['routing', 'response_planner'],
  ['response_planner', 'approval_gate'],
  ['approval_gate', 'monitoring'],
  ['monitoring', 'recovery'],
];
