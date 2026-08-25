// ---------------------------------------------------------------------------
// Real-time workflow state model (Phase 2 of the 3D command-center plan).
//
// PURE, DOM-FREE. This module turns the stream of REAL backend WebSocket events
// (the ones the backend now emits in Phase 1) into a normalized, per-incident
// agent-workflow state. It is the single source of truth the 3D command center
// (Phase 3+) and any other live view will RENDER — the UI reacts to this state;
// it never drives it. There are no timers, no synthetic progress, and no
// fabricated ordering here: every transition is caused by an actual backend
// event.
//
// Design rules honored:
//   * Backend is the source of truth. Each field is set only by a real event.
//   * Order-tolerant & idempotent: a completed/failed event stands on its own
//     even if the matching "started" was missed; re-delivery is harmless.
//   * Future-proof: an unknown agent key is still tracked (labeled from the
//     event) rather than dropped, so adding a backend node never breaks the UI.
//   * Only STRUCTURED output is stored (the backend already strips reasoning);
//     this module never invents or infers content the backend didn't send.
//   * Bounded memory: at most MAX_TRACKED_INCIDENTS are retained (oldest by
//     last activity are pruned) so a long-running command center can't grow
//     without limit.
// ---------------------------------------------------------------------------

import { LiveEvent } from '../types';

// The eight REAL LangGraph nodes, in pipeline order. Labels mirror the backend
// AGENT_META so ordering/labels are stable even before any event arrives. The
// backend also sends `agent_label` on every agent event, which takes precedence
// if present (keeps the two in sync without a hard dependency).
export const AGENT_ORDER = [
  'supervisor',
  'security',
  'medical',
  'transport',
  'communication',
  'fire',
  'facilities',
  'synthesizer',
] as const;

export type AgentKey = (typeof AGENT_ORDER)[number];

export const AGENT_LABELS: Record<AgentKey, string> = {
  supervisor: 'Incident Intelligence Agent',
  security: 'Security & Perimeter Agent',
  medical: 'Medical Response Agent',
  transport: 'Resource & Transport Agent',
  communication: 'Communication Agent',
  fire: 'Safety & Hazard Agent',
  facilities: 'Facilities & Infrastructure Agent',
  synthesizer: 'Response Planning Agent',
};

export type AgentRuntimeStatus = 'idle' | 'working' | 'completed' | 'failed';

export type WorkflowPhase =
  | 'idle'
  | 'assessment_in_progress'
  | 'assessed'
  | 'analyzing'
  | 'coordinating'
  | 'synthesizing'
  | 'planned'
  | 'awaiting_approval'
  | 'approved'
  | 'rejected'
  | 'dispatched'
  | 'resolved'
  | 'attention';

export interface AgentNodeState {
  key: string;
  label: string;
  status: AgentRuntimeStatus;
  message?: string;
  /** Structured, non-sensitive summary the backend attached on completion. */
  output?: Record<string, unknown>;
  error?: string;
  startedAt?: string;
  completedAt?: string;
}

export interface ApprovalState {
  required: boolean;
  status: 'pending' | 'approved' | 'rejected' | null;
  planId?: string;
  approvedBy?: string;
  message?: string;
}

export interface DispatchState {
  dispatched: boolean;
  resources: string[];
  location?: string;
  message?: string;
}

export interface DepartmentAssignmentState {
  assignmentId?: number;
  department: string;
  status: string;
  assignedResources: string[];
  actor?: string;
  lastUpdatedAt?: string;
}

export interface IncidentWorkflowState {
  incidentId: string;
  agents: Record<string, AgentNodeState>;
  approval: ApprovalState;
  dispatch: DispatchState;
  assignments?: Record<string, DepartmentAssignmentState>;
  resolved: boolean;
  closed: boolean;
  phase?: WorkflowPhase;
  providerStatus?: string;
  firstEventAt?: string;
  lastEventAt?: string;
}

export interface RealtimeWorkflowState {
  incidents: Record<string, IncidentWorkflowState>;
  /** The incident that most recently showed live activity (for focus/camera). */
  activeIncidentId: string | null;
  /** Total real events folded in — handy for debugging / test assertions. */
  eventCount: number;
}

export const MAX_TRACKED_INCIDENTS = 25;

// Events that carry no real incident context and must never create workflow
// state. (System heartbeats and the vehicle telemetry channel.)
const NON_INCIDENT_IDS = new Set(['system', 'live_telemetry', '']);

export function initialRealtimeState(): RealtimeWorkflowState {
  return { incidents: {}, activeIncidentId: null, eventCount: 0 };
}

function freshAgents(): Record<string, AgentNodeState> {
  const agents: Record<string, AgentNodeState> = {};
  for (const key of AGENT_ORDER) {
    agents[key] = { key, label: AGENT_LABELS[key], status: 'idle' };
  }
  return agents;
}

function freshIncident(incidentId: string): IncidentWorkflowState {
  return {
    incidentId,
    agents: freshAgents(),
    approval: { required: false, status: null },
    dispatch: { dispatched: false, resources: [] },
    assignments: {},
    resolved: false,
    closed: false,
    phase: 'idle',
  };
}

function coerceOutput(value: unknown): Record<string, unknown> | undefined {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return undefined;
}

function coerceResources(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((v) => String(v));
  return [];
}

// Derive the human-facing workflow phase purely from accumulated signals, so it
// is correct regardless of the order events arrived in. Ordered from the latest
// stage to the earliest; the first match wins.
export function derivePhase(incident: IncidentWorkflowState): WorkflowPhase {
  if (incident.resolved || incident.closed) return 'resolved';
  if (incident.dispatch.dispatched) return 'dispatched';
  if (incident.approval.status === 'approved') return 'approved';
  if (incident.approval.status === 'rejected') return 'rejected';

  const anyFailed = Object.values(incident.agents).some((a) => a.status === 'failed');
  if (anyFailed) return 'attention';

  if (incident.approval.required || incident.approval.status === 'pending') {
    return 'awaiting_approval';
  }

  const synthesizer = incident.agents.synthesizer;
  if (synthesizer && synthesizer.status === 'completed') return 'planned';
  if (synthesizer && synthesizer.status === 'working') return 'synthesizing';

  const supervisor = incident.agents.supervisor;
  if (supervisor && supervisor.status === 'working') return 'analyzing';

  const anyActivity = Object.values(incident.agents).some((a) => a.status !== 'idle');
  if (anyActivity) return 'coordinating';

  return 'idle';
}

// Real completion fraction across the known pipeline nodes (0..1). This is a
// truthful progress signal — it counts nodes the backend actually finished, not
// elapsed time — suitable for a progress ring in the 3D view.
export function workflowProgress(incident: IncidentWorkflowState): number {
  const known = AGENT_ORDER.map((k) => incident.agents[k]).filter(Boolean);
  if (known.length === 0) return 0;
  const done = known.filter((a) => a.status === 'completed').length;
  return done / known.length;
}

// Agents in canonical pipeline order, followed by any unknown/extra agents the
// backend may introduce later (kept visible rather than dropped).
export function orderedAgents(incident: IncidentWorkflowState): AgentNodeState[] {
  const ordered: AgentNodeState[] = [];
  for (const key of AGENT_ORDER) {
    if (incident.agents[key]) ordered.push(incident.agents[key]);
  }
  const known = new Set<string>(AGENT_ORDER);
  for (const [key, agent] of Object.entries(incident.agents)) {
    if (!known.has(key)) ordered.push(agent);
  }
  return ordered;
}

export function getIncidentWorkflow(
  state: RealtimeWorkflowState,
  incidentId: string | null | undefined,
): IncidentWorkflowState | undefined {
  if (!incidentId) return undefined;
  return state.incidents[incidentId];
}

export function getActiveWorkflow(
  state: RealtimeWorkflowState,
): IncidentWorkflowState | undefined {
  return getIncidentWorkflow(state, state.activeIncidentId);
}

// Prune the least-recently-active incidents when over the cap. Pure: returns a
// new incidents map.
function pruneIncidents(
  incidents: Record<string, IncidentWorkflowState>,
): Record<string, IncidentWorkflowState> {
  const keys = Object.keys(incidents);
  if (keys.length <= MAX_TRACKED_INCIDENTS) return incidents;
  const sorted = keys.sort((a, b) => {
    const ta = incidents[a].lastEventAt || '';
    const tb = incidents[b].lastEventAt || '';
    return ta < tb ? -1 : ta > tb ? 1 : 0;
  });
  const drop = new Set(sorted.slice(0, keys.length - MAX_TRACKED_INCIDENTS));
  const next: Record<string, IncidentWorkflowState> = {};
  for (const key of keys) if (!drop.has(key)) next[key] = incidents[key];
  return next;
}

// The core reducer: fold one real backend event into the workflow state.
// Returns the SAME state object when an event is irrelevant, so React consumers
// using this via useReducer re-render only on meaningful change.
export function reduceRealtime(
  state: RealtimeWorkflowState,
  event: LiveEvent,
): RealtimeWorkflowState {
  const name = event?.event_name;
  const incidentId = event?.incident_id;
  if (!name || !incidentId || NON_INCIDENT_IDS.has(incidentId)) return state;

  // Only fold events that actually advance the agent workflow. Everything else
  // (map/telemetry/notification channels) is ignored by this model.
  const RELEVANT = new Set([
    'assessment_started',
    'incident_assessed',
    'assessment_failed',
    'response_plan_generated',
    'awaiting_human_authorization',
    'agent_started',
    'agent_progress',
    'agent_completed',
    'agent_failed',
    'approval_required',
    'approval_approved',
    'approval_granted', // legacy alias — treated as approved
    'approval_rejected',
    'response_dispatched',
    'dispatch_started', // existing event — also marks dispatch
    'incident_resolved',
    'incident_closed',
    'department_notified',
    'dept_assignment_accepted',
    'dept_assignment_declined',
    'dept_team_assigned',
    'dept_en_route',
    'dept_on_scene',
    'dept_assignment_completed',
  ]);
  if (!RELEVANT.has(name)) return state;

  const prev = state.incidents[incidentId] || freshIncident(incidentId);
  const incident: IncidentWorkflowState = {
    ...prev,
    agents: { ...prev.agents },
    approval: { ...prev.approval },
    dispatch: { ...prev.dispatch, resources: [...prev.dispatch.resources] },
    assignments: { ...(prev.assignments || {}) },
  };
  const ts = typeof event.timestamp === 'string' ? event.timestamp : undefined;
  if (ts) {
    if (!incident.firstEventAt) incident.firstEventAt = ts;
    incident.lastEventAt = ts;
  }

  let activeIncidentId = state.activeIncidentId;

  const touchAgent = (): AgentNodeState => {
    const key = typeof event.agent === 'string' && event.agent ? event.agent : 'unknown';
    const label =
      (typeof event.agent_label === 'string' && event.agent_label) ||
      AGENT_LABELS[key as AgentKey] ||
      key.replace(/_/g, ' ');
    const existing = incident.agents[key] || { key, label, status: 'idle' as AgentRuntimeStatus };
    const next: AgentNodeState = { ...existing, label };
    incident.agents[key] = next;
    return next;
  };

  switch (name) {
    case 'assessment_started':
      incident.phase = 'assessment_in_progress';
      incident.providerStatus = typeof event.ai_provider_status === 'string' ? event.ai_provider_status : undefined;
      activeIncidentId = incidentId;
      break;
    case 'incident_assessed':
      incident.phase = 'assessed';
      incident.providerStatus = typeof event.ai_provider_status === 'string' ? event.ai_provider_status : undefined;
      activeIncidentId = incidentId;
      break;
    case 'assessment_failed':
      incident.phase = 'attention';
      incident.providerStatus = typeof event.ai_provider_status === 'string' ? event.ai_provider_status : 'FAILED';
      activeIncidentId = incidentId;
      break;
    case 'response_plan_generated':
    case 'awaiting_human_authorization':
      incident.phase = 'awaiting_approval';
      if (typeof event.plan_id === 'string') incident.approval.planId = event.plan_id;
      incident.approval.required = true;
      incident.approval.status = 'pending';
      activeIncidentId = incidentId;
      break;
    case 'department_notified':
    case 'dept_assignment_accepted':
    case 'dept_assignment_declined':
    case 'dept_team_assigned':
    case 'dept_en_route':
    case 'dept_on_scene':
    case 'dept_assignment_completed': {
      const department = typeof event.department === 'string' ? event.department.toUpperCase() : '';
      if (!department) return state;
      const statusByEvent: Record<string, string> = {
        department_notified: 'NOTIFIED',
        dept_assignment_accepted: 'ACCEPTED',
        dept_assignment_declined: 'DECLINED',
        dept_team_assigned: 'TEAM_ASSIGNED',
        dept_en_route: 'EN_ROUTE',
        dept_on_scene: 'ON_SCENE',
        dept_assignment_completed: 'COMPLETED',
      };
      if (!incident.assignments) incident.assignments = {};
      incident.assignments[department] = {
        assignmentId: typeof event.assignment_id === 'number' ? event.assignment_id : undefined,
        department,
        status: typeof event.status === 'string' ? event.status : statusByEvent[name],
        assignedResources: coerceResources(event.assigned_resources),
        actor: typeof event.actor === 'string' ? event.actor : undefined,
        lastUpdatedAt: ts,
      };
      activeIncidentId = incidentId;
      break;
    }
    case 'agent_started':
    case 'agent_progress': {
      const agent = touchAgent();
      agent.status = 'working';
      if (typeof event.message === 'string') agent.message = event.message;
      if (ts && !agent.startedAt) agent.startedAt = ts;
      activeIncidentId = incidentId;
      break;
    }
    case 'agent_completed': {
      const agent = touchAgent();
      agent.status = 'completed';
      if (typeof event.message === 'string') agent.message = event.message;
      const output = coerceOutput(event.output);
      if (output) agent.output = output;
      if (ts) agent.completedAt = ts;
      activeIncidentId = incidentId;
      break;
    }
    case 'agent_failed': {
      const agent = touchAgent();
      agent.status = 'failed';
      if (typeof event.message === 'string') agent.message = event.message;
      if (typeof event.error === 'string') agent.error = event.error;
      if (ts) agent.completedAt = ts;
      activeIncidentId = incidentId;
      break;
    }
    case 'approval_required': {
      incident.approval.required = true;
      if (incident.approval.status === null) incident.approval.status = 'pending';
      if (typeof event.plan_id === 'string') incident.approval.planId = event.plan_id;
      if (typeof event.message === 'string') incident.approval.message = event.message;
      activeIncidentId = incidentId;
      break;
    }
    case 'approval_approved':
    case 'approval_granted': {
      incident.approval.status = 'approved';
      incident.approval.required = true;
      if (typeof event.plan_id === 'string') incident.approval.planId = event.plan_id;
      if (typeof event.approved_by === 'string') incident.approval.approvedBy = event.approved_by;
      activeIncidentId = incidentId;
      break;
    }
    case 'approval_rejected': {
      incident.approval.status = 'rejected';
      incident.approval.required = true;
      if (typeof event.plan_id === 'string') incident.approval.planId = event.plan_id;
      activeIncidentId = incidentId;
      break;
    }
    case 'response_dispatched':
    case 'dispatch_started': {
      incident.dispatch.dispatched = true;
      const resources = coerceResources(event.dispatched_resources);
      if (resources.length > 0) incident.dispatch.resources = resources;
      if (typeof event.location === 'string') incident.dispatch.location = event.location;
      if (typeof event.message === 'string') incident.dispatch.message = event.message;
      activeIncidentId = incidentId;
      break;
    }
    case 'incident_resolved': {
      incident.resolved = true;
      break;
    }
    case 'incident_closed': {
      incident.closed = true;
      break;
    }
    default:
      return state;
  }

  const incidents = pruneIncidents({ ...state.incidents, [incidentId]: incident });

  return {
    incidents,
    activeIncidentId,
    eventCount: state.eventCount + 1,
  };
}
