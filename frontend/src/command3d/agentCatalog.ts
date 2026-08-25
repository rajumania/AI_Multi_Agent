// ---------------------------------------------------------------------------
// Command Center 3D — visual agent catalog (Phase 3).
//
// PURE, DOM-FREE, three-free. Declares the FIVE required visual agents and binds
// each to a REAL backend LangGraph node key, so every node in the 3D scene is
// driven by actual agent lifecycle events (Phase 1) via the Phase 2 realtime
// state — never by a timer or a script.
//
//   Incident Intelligence  -> supervisor    (classifies the incident)
//   Medical Response       -> medical        (triage + ambulances)
//   Safety / Hazard        -> fire           (hazard containment)
//   Resource Allocation    -> transport      (resources + logistics)
//   Response Planning      -> synthesizer    (final plan; human approval gate)
//
// The backend also runs security / communication / facilities nodes; those stay
// tracked in the realtime state and can be surfaced in a later phase. Phase 3
// visualizes the five headline agents from the master specification.
// ---------------------------------------------------------------------------

import type { AgentKey } from '../realtime/workflowReducer';

export interface VisualAgent {
  /** Real backend node key — this is what ties the node to live events. */
  key: AgentKey;
  /** Required display name from the specification. */
  title: string;
  subtitle: string;
  /** Persistent identity color (the node's ring + the card accent). */
  accent: string;
  /** Layout position in the 3D scene (world units, y-up). */
  position: [number, number, number];
}

// Ordered top -> middle row -> bottom to read as a supervisor -> responders ->
// planner pipeline once the camera orbits the constellation.
export const VISUAL_AGENTS: readonly VisualAgent[] = [
  {
    key: 'supervisor',
    title: 'Incident Intelligence',
    subtitle: 'Classifies type, severity & location',
    accent: '#38bdf8',
    position: [0, 2.1, 0],
  },
  {
    key: 'medical',
    title: 'Medical Response',
    subtitle: 'Triage & ambulance staging',
    accent: '#2dd4bf',
    position: [-2.5, 0.3, 0.5],
  },
  {
    key: 'fire',
    title: 'Safety / Hazard',
    subtitle: 'Hazard containment & safety',
    accent: '#fb923c',
    position: [0, 0.4, 1.05],
  },
  {
    key: 'transport',
    title: 'Resource Allocation',
    subtitle: 'Resources, vehicles & logistics',
    accent: '#c084fc',
    position: [2.5, 0.3, 0.5],
  },
  {
    key: 'synthesizer',
    title: 'Response Planning',
    subtitle: 'Synthesizes the plan for approval',
    accent: '#818cf8',
    position: [0, -2.0, 0],
  },
] as const;

// The agent whose node reflects the human approval gate (its plan awaits
// sign-off). Kept here so the status logic and the scene agree on one key.
export const APPROVAL_AGENT_KEY: AgentKey = 'synthesizer';

// Connections drawn between nodes: supervisor fans out to the three responders,
// and each responder converges on the response-planning node. Expressed as
// pairs of catalog keys; the scene resolves them to positions.
export const AGENT_CONNECTIONS: ReadonlyArray<readonly [AgentKey, AgentKey]> = [
  ['supervisor', 'medical'],
  ['supervisor', 'fire'],
  ['supervisor', 'transport'],
  ['medical', 'synthesizer'],
  ['fire', 'synthesizer'],
  ['transport', 'synthesizer'],
];

export interface HumanResponseTeam {
  key: string;
  department: string;
  title: string;
  subtitle: string;
  accent: string;
  position: [number, number, number];
}

// These are the six departments in backend/services/departments.py. They are
// response-team nodes, deliberately separate from the AI-agent catalog.
export const HUMAN_RESPONSE_TEAMS: readonly HumanResponseTeam[] = [
  { key: 'human_medical', department: 'MEDICAL', title: 'Medical Response Team', subtitle: 'Human department response', accent: '#34d399', position: [-3.8, 1.35, 0.2] },
  { key: 'human_security', department: 'SECURITY', title: 'Security Response Team', subtitle: 'Human department response', accent: '#60a5fa', position: [-1.3, -2.7, 1.1] },
  { key: 'human_transport', department: 'TRANSPORT', title: 'Transport Response Team', subtitle: 'Human department response', accent: '#22d3ee', position: [3.8, 1.35, 0.2] },
  { key: 'human_communication', department: 'COMMUNICATION', title: 'Communications Team', subtitle: 'Human department response', accent: '#c084fc', position: [1.3, -2.7, 1.1] },
  { key: 'human_fire', department: 'FIRE', title: 'Fire & Safety Team', subtitle: 'Human department response', accent: '#fb923c', position: [-3.8, -0.9, 1.1] },
  { key: 'human_facilities', department: 'FACILITIES', title: 'Facilities Team', subtitle: 'Human department response', accent: '#2dd4bf', position: [3.8, -0.9, 1.1] },
] as const;

export const HUMAN_CONNECTIONS: ReadonlyArray<readonly [string, string]> = HUMAN_RESPONSE_TEAMS.map((team) => ['synthesizer', team.key] as const);
