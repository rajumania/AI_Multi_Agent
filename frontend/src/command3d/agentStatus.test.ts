// ---------------------------------------------------------------------------
// Command Center 3D — pure logic tests (Phase 3).
//
// DOM-FREE and three-FREE: exercises the catalog integrity and the six-state
// derivation that turn REAL backend-driven realtime state into what the 3D
// scene and the AgentCards display. No timers, no rendering — this is the proof
// that the visual states are a faithful function of real events (Rules 12–16).
// ---------------------------------------------------------------------------

import { describe, it, expect } from 'vitest';
import { LiveEvent } from '../types';
import {
  AGENT_ORDER,
  getIncidentWorkflow,
  initialRealtimeState,
  reduceRealtime,
  type AgentNodeState,
  type IncidentWorkflowState,
  type RealtimeWorkflowState,
} from '../realtime/workflowReducer';
import { AGENT_CONNECTIONS, APPROVAL_AGENT_KEY, HUMAN_RESPONSE_TEAMS, VISUAL_AGENTS } from './agentCatalog';
import {
  STATUS_VISUALS,
  agentVisual,
  deriveAgentDisplayStatus,
  humanTeamVisual,
  workflowStarted,
  type DisplayStatus,
} from './agentStatus';

const HEX = /^#[0-9a-fA-F]{6}$/;
const ALL_STATUSES: DisplayStatus[] = ['IDLE', 'QUEUED', 'WORKING', 'COMPLETED', 'FAILED', 'WAITING_APPROVAL'];

// Build real state by folding real events, exactly as the app does at runtime.
let clock = 0;
function ev(event_name: string, extra: Record<string, unknown> = {}): LiveEvent {
  clock += 1;
  return {
    event_name,
    incident_id: 'INC-1',
    timestamp: new Date(1_700_000_000_000 + clock * 1000).toISOString(),
    ...extra,
  } as LiveEvent;
}
function fold(events: LiveEvent[]): RealtimeWorkflowState {
  return events.reduce((s, e) => reduceRealtime(s, e), initialRealtimeState());
}
function build(events: LiveEvent[]): IncidentWorkflowState {
  const inc = getIncidentWorkflow(fold(events), 'INC-1');
  if (!inc) throw new Error('expected incident INC-1 to exist');
  return inc;
}

// A fresh incident with every agent idle and no approval/dispatch — the only way
// to reach the "exists but not started" state (real events always start it).
function freshIdleIncident(): IncidentWorkflowState {
  const idle = (key: string): AgentNodeState => ({ key, label: key, status: 'idle' });
  return {
    incidentId: 'INC-IDLE',
    agents: { supervisor: idle('supervisor'), medical: idle('medical'), synthesizer: idle('synthesizer') },
    approval: { required: false, status: null },
    dispatch: { dispatched: false, resources: [] },
    resolved: false,
    closed: false,
  };
}

describe('command3d catalog integrity', () => {
  it('declares exactly the five required visual agents with unique, real backend keys', () => {
    expect(VISUAL_AGENTS).toHaveLength(5);
    const keys = VISUAL_AGENTS.map((a) => a.key);
    expect(new Set(keys).size).toBe(keys.length); // unique
    for (const key of keys) {
      expect(AGENT_ORDER).toContain(key); // every key is a real LangGraph node
    }
  });

  it('maps to the five headline agents from the specification', () => {
    const titles = VISUAL_AGENTS.map((a) => a.title).sort();
    expect(titles).toEqual(
      ['Incident Intelligence', 'Medical Response', 'Resource Allocation', 'Response Planning', 'Safety / Hazard'].sort(),
    );
  });

  it('gives every agent a hex accent, a subtitle, and a 3-tuple position', () => {
    for (const a of VISUAL_AGENTS) {
      expect(a.accent).toMatch(HEX);
      expect(a.subtitle.length).toBeGreaterThan(0);
      expect(a.position).toHaveLength(3);
      for (const c of a.position) expect(typeof c).toBe('number');
    }
  });

  it('binds the approval gate to a real catalog agent', () => {
    expect(APPROVAL_AGENT_KEY).toBe('synthesizer');
    expect(VISUAL_AGENTS.map((a) => a.key)).toContain(APPROVAL_AGENT_KEY);
  });

  it('only connects agents that exist in the catalog', () => {
    const keys = new Set<string>(VISUAL_AGENTS.map((a) => a.key));
    for (const [from, to] of AGENT_CONNECTIONS) {
      expect(keys.has(from)).toBe(true);
      expect(keys.has(to)).toBe(true);
    }
  });
});

describe('STATUS_VISUALS mapping', () => {
  it('defines all six display states with self-consistent, valid descriptors', () => {
    for (const status of ALL_STATUSES) {
      const v = STATUS_VISUALS[status];
      expect(v).toBeDefined();
      expect(v.status).toBe(status);
      expect(v.color).toMatch(HEX);
      expect(typeof v.glow).toBe('number');
      expect(typeof v.pulse).toBe('boolean');
      expect(v.label.length).toBeGreaterThan(0);
    }
  });

  it('animates a pulse only for the genuinely live states', () => {
    const pulsing = ALL_STATUSES.filter((s) => STATUS_VISUALS[s].pulse).sort();
    expect(pulsing).toEqual(['WAITING_APPROVAL', 'WORKING'].sort());
  });
});

describe('workflowStarted', () => {
  it('is false with no incident and false for a fresh all-idle incident', () => {
    expect(workflowStarted(undefined)).toBe(false);
    expect(workflowStarted(freshIdleIncident())).toBe(false);
  });

  it('is true as soon as any real signal exists', () => {
    expect(workflowStarted(build([ev('agent_started', { agent: 'supervisor' })]))).toBe(true);
    expect(workflowStarted(build([ev('approval_required', { plan_id: 'P1' })]))).toBe(true);
    expect(workflowStarted(build([ev('dispatch_started', { dispatched_resources: ['amb-1'] })]))).toBe(true);
    expect(workflowStarted(build([ev('incident_resolved')]))).toBe(true);
  });
});

describe('deriveAgentDisplayStatus — the six visual states', () => {
  it('IDLE when there is no incident, or the incident exists but has not started', () => {
    expect(deriveAgentDisplayStatus(undefined, 'medical')).toBe('IDLE');
    expect(deriveAgentDisplayStatus(freshIdleIncident(), 'medical')).toBe('IDLE');
  });

  it('QUEUED for an idle agent once the workflow has started elsewhere', () => {
    const inc = build([ev('agent_started', { agent: 'supervisor' })]);
    expect(deriveAgentDisplayStatus(inc, 'medical')).toBe('QUEUED');
  });

  it('WORKING / COMPLETED / FAILED follow the real agent status', () => {
    expect(deriveAgentDisplayStatus(build([ev('agent_started', { agent: 'medical' })]), 'medical')).toBe('WORKING');
    expect(deriveAgentDisplayStatus(build([ev('agent_completed', { agent: 'medical' })]), 'medical')).toBe('COMPLETED');
    expect(deriveAgentDisplayStatus(build([ev('agent_failed', { agent: 'medical' })]), 'medical')).toBe('FAILED');
  });

  it('WAITING_APPROVAL overrides the planner while approval is pending', () => {
    const inc = build([
      ev('agent_completed', { agent: 'synthesizer' }),
      ev('approval_required', { plan_id: 'P1' }),
    ]);
    expect(deriveAgentDisplayStatus(inc, APPROVAL_AGENT_KEY)).toBe('WAITING_APPROVAL');
  });

  it('does NOT hijack a non-approval agent when approval is pending', () => {
    const inc = build([
      ev('agent_completed', { agent: 'medical' }),
      ev('approval_required', { plan_id: 'P1' }),
    ]);
    expect(deriveAgentDisplayStatus(inc, 'medical')).toBe('COMPLETED');
  });

  it('clears WAITING_APPROVAL once the decision is made', () => {
    const inc = build([
      ev('agent_completed', { agent: 'synthesizer' }),
      ev('approval_required', { plan_id: 'P1' }),
      ev('approval_approved', { plan_id: 'P1', approved_by: 'commander' }),
    ]);
    // Approval is no longer pending, so the planner falls back to its real status.
    expect(deriveAgentDisplayStatus(inc, APPROVAL_AGENT_KEY)).toBe('COMPLETED');
  });
});

describe('agentVisual', () => {
  it('returns the visual descriptor matching the derived status', () => {
    const working = agentVisual(build([ev('agent_started', { agent: 'medical' })]), 'medical');
    expect(working.status).toBe('WORKING');
    expect(working).toEqual(STATUS_VISUALS.WORKING);

    const idle = agentVisual(undefined, 'medical');
    expect(idle).toEqual(STATUS_VISUALS.IDLE);
  });
});

describe('humanTeamVisual', () => {
  it('declares separate human-response nodes for every operational department', () => {
    expect(HUMAN_RESPONSE_TEAMS.map((team) => team.department)).toEqual([
      'MEDICAL', 'SECURITY', 'TRANSPORT', 'COMMUNICATION', 'FIRE', 'FACILITIES',
    ]);
    expect(new Set(HUMAN_RESPONSE_TEAMS.map((team) => team.key)).size).toBe(HUMAN_RESPONSE_TEAMS.length);
  });

  it('keeps backend assignment states semantically distinct', () => {
    expect(humanTeamVisual('NOTIFIED', '#ffffff').label).toBe('Notified');
    expect(humanTeamVisual('ACCEPTED', '#ffffff').label).toBe('Accepted');
    expect(humanTeamVisual('TEAM_ASSIGNED', '#ffffff').label).toBe('Team Assigned');
    expect(humanTeamVisual('TEAM_ASSIGNED', '#ffffff').status).toBe('WORKING');
    expect(humanTeamVisual('EN_ROUTE', '#ffffff').label).toBe('En Route');
    expect(humanTeamVisual('ON_SCENE', '#ffffff').label).toBe('On Scene');
    expect(humanTeamVisual('COMPLETED', '#ffffff').status).toBe('COMPLETED');
    expect(humanTeamVisual('DECLINED', '#ffffff').status).toBe('FAILED');
  });
});
