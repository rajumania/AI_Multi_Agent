// ---------------------------------------------------------------------------
// Command Center 3D — agent display status & visual mapping (Phase 3).
//
// PURE, DOM-FREE, three-free. Turns the REAL Phase 2 realtime state into the six
// visual states the specification requires:
//
//   IDLE              nothing has started for this incident yet
//   QUEUED            the workflow is running but this agent hasn't (its turn is
//                     pending) — derived from real activity, never a timer
//   WORKING           a real agent_started/agent_progress event is live
//   COMPLETED         a real agent_completed event arrived
//   FAILED            a real agent_failed event arrived
//   WAITING_APPROVAL  the plan is generated and the real human approval gate is
//                     pending (approval_required, not yet decided)
//
// Every transition is caused by an actual backend event captured in Phase 2.
// There are no timers here and nothing is inferred that the backend didn't send.
// ---------------------------------------------------------------------------

import type { AgentRuntimeStatus, IncidentWorkflowState } from '../realtime/workflowReducer';
import { APPROVAL_AGENT_KEY } from './agentCatalog';

export type DisplayStatus =
  | 'IDLE'
  | 'QUEUED'
  | 'WORKING'
  | 'COMPLETED'
  | 'FAILED'
  | 'WAITING_APPROVAL';

export interface StatusVisual {
  status: DisplayStatus;
  /** Short human label for the card badge. */
  label: string;
  /** Node/badge color (hex). */
  color: string;
  /** Baseline emissive intensity for the 3D node. */
  glow: number;
  /** Whether the 3D node should animate a pulse (only for genuinely live states). */
  pulse: boolean;
  /** One-line description used in the card / legend. */
  description: string;
}

export const STATUS_VISUALS: Record<DisplayStatus, StatusVisual> = {
  IDLE: {
    status: 'IDLE',
    label: 'Idle',
    color: '#64748b',
    glow: 0.05,
    pulse: false,
    description: 'Standing by',
  },
  QUEUED: {
    status: 'QUEUED',
    label: 'Queued',
    color: '#f59e0b',
    glow: 0.28,
    pulse: false,
    description: 'Waiting its turn in the pipeline',
  },
  WORKING: {
    status: 'WORKING',
    label: 'Working',
    color: '#38bdf8',
    glow: 0.9,
    pulse: true,
    description: 'Actively processing',
  },
  COMPLETED: {
    status: 'COMPLETED',
    label: 'Completed',
    color: '#22c55e',
    glow: 0.55,
    pulse: false,
    description: 'Finished — output ready',
  },
  FAILED: {
    status: 'FAILED',
    label: 'Failed',
    color: '#ef4444',
    glow: 0.75,
    pulse: false,
    description: 'Needs attention',
  },
  WAITING_APPROVAL: {
    status: 'WAITING_APPROVAL',
    label: 'Awaiting Approval',
    color: '#a855f7',
    glow: 0.7,
    pulse: true,
    description: 'Plan ready — awaiting human authorization',
  },
};

/**
 * Has the workflow started for this incident? True as soon as any real signal
 * exists — an agent left idle, an approval was requested, a dispatch happened,
 * or the incident was resolved/closed. Used to distinguish IDLE from QUEUED.
 */
export function workflowStarted(incident: IncidentWorkflowState | undefined): boolean {
  if (!incident) return false;
  const anyAgentActive = Object.values(incident.agents).some((a) => a.status !== 'idle');
  return (
    anyAgentActive ||
    incident.approval.required ||
    incident.dispatch.dispatched ||
    incident.resolved ||
    incident.closed
  );
}

/**
 * Derive one of the six visual states for a specific agent from the real
 * realtime state. The only override is the human approval gate: once the plan
 * requires approval and it is still pending, the response-planning agent shows
 * WAITING_APPROVAL (its work is done but authorization is not).
 */
export function deriveAgentDisplayStatus(
  incident: IncidentWorkflowState | undefined,
  key: string,
): DisplayStatus {
  const status: AgentRuntimeStatus = incident?.agents[key]?.status ?? 'idle';

  if (
    key === APPROVAL_AGENT_KEY &&
    incident &&
    incident.approval.required &&
    incident.approval.status === 'pending'
  ) {
    return 'WAITING_APPROVAL';
  }

  if (status === 'working') return 'WORKING';
  if (status === 'completed') return 'COMPLETED';
  if (status === 'failed') return 'FAILED';

  // status === 'idle'
  return workflowStarted(incident) ? 'QUEUED' : 'IDLE';
}

/** Convenience: the full visual descriptor for an agent in one call. */
export function agentVisual(
  incident: IncidentWorkflowState | undefined,
  key: string,
): StatusVisual {
  return STATUS_VISUALS[deriveAgentDisplayStatus(incident, key)];
}

/** Map a real backend department assignment to a presentation-only visual. */
export function humanTeamVisual(status: string | undefined, accent: string): StatusVisual {
  const normalized = (status || 'NOTIFIED').toUpperCase();
  if (normalized === 'DECLINED') return { ...STATUS_VISUALS.FAILED, color: '#ef4444', label: 'Declined', description: 'Department declined assignment' };
  if (normalized === 'COMPLETED') return { ...STATUS_VISUALS.COMPLETED, color: accent, label: 'Completed', description: 'Human response completed' };
  if (normalized === 'ON_SCENE') return { ...STATUS_VISUALS.WORKING, color: '#facc15', label: 'On Scene', description: 'Human team is on scene' };
  if (normalized === 'EN_ROUTE') return { ...STATUS_VISUALS.WORKING, color: '#22d3ee', label: 'En Route', description: 'Human team marked en route' };
  if (normalized === 'TEAM_ASSIGNED') return { ...STATUS_VISUALS.WORKING, color: accent, label: 'Team Assigned', description: 'Team/resources assigned' };
  if (normalized === 'ACCEPTED') return { ...STATUS_VISUALS.WORKING, color: accent, label: 'Accepted', description: 'Department accepted assignment' };
  return { ...STATUS_VISUALS.QUEUED, color: '#f59e0b', label: 'Notified', description: 'Awaiting department response' };
}
