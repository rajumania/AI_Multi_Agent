import { describe, it, expect } from 'vitest';
import { LiveEvent } from '../types';
import {
  AGENT_ORDER,
  MAX_TRACKED_INCIDENTS,
  RealtimeWorkflowState,
  derivePhase,
  getActiveWorkflow,
  initialRealtimeState,
  orderedAgents,
  reduceRealtime,
  workflowProgress,
} from './workflowReducer';

// Small event factory. `timestamp` defaults to a monotonic-ish stamp so pruning
// order is deterministic in the tests that need it.
let clock = 0;
function ev(event_name: string, incident_id: string, extra: Record<string, unknown> = {}): LiveEvent {
  clock += 1;
  return {
    event_name,
    incident_id,
    timestamp: new Date(1_700_000_000_000 + clock * 1000).toISOString(),
    ...extra,
  } as LiveEvent;
}

function fold(events: LiveEvent[], start?: RealtimeWorkflowState): RealtimeWorkflowState {
  return events.reduce((s, e) => reduceRealtime(s, e), start ?? initialRealtimeState());
}

describe('reduceRealtime — irrelevant / malformed events', () => {
  it('returns the SAME state for system, telemetry, and unknown-channel events', () => {
    const s0 = initialRealtimeState();
    expect(reduceRealtime(s0, ev('agent_started', 'system', { agent: 'medical' }))).toBe(s0);
    expect(reduceRealtime(s0, ev('agent_started', 'live_telemetry', { agent: 'medical' }))).toBe(s0);
    expect(reduceRealtime(s0, ev('gps_updated', 'INC-1'))).toBe(s0);
    expect(reduceRealtime(s0, ev('vehicle_location_updated', 'INC-1'))).toBe(s0);
    // missing name / incident id
    expect(reduceRealtime(s0, { event_name: '', incident_id: 'INC-1', timestamp: 'x' } as LiveEvent)).toBe(s0);
    expect(reduceRealtime(s0, { event_name: 'agent_started', timestamp: 'x' } as LiveEvent)).toBe(s0);
  });
});

describe('reduceRealtime — agent lifecycle', () => {
  it('marks an agent working on agent_started and focuses the incident', () => {
    const s = fold([ev('agent_started', 'INC-1', { agent: 'supervisor', message: 'Analyzing...' })]);
    const inc = s.incidents['INC-1'];
    expect(inc.agents.supervisor.status).toBe('working');
    expect(inc.agents.supervisor.message).toBe('Analyzing...');
    expect(inc.agents.supervisor.startedAt).toBeTruthy();
    expect(s.activeIncidentId).toBe('INC-1');
    expect(getActiveWorkflow(s)?.incidentId).toBe('INC-1');
    expect(derivePhase(inc)).toBe('analyzing');
  });

  it('stores STRUCTURED output on agent_completed', () => {
    const s = fold([
      ev('agent_started', 'INC-1', { agent: 'medical' }),
      ev('agent_completed', 'INC-1', {
        agent: 'medical',
        agent_label: 'Medical Response Agent',
        output: { actions_count: 2, recommended_ambulances: 2, matched_resources: 1 },
      }),
    ]);
    const medical = s.incidents['INC-1'].agents.medical;
    expect(medical.status).toBe('completed');
    expect(medical.output).toEqual({ actions_count: 2, recommended_ambulances: 2, matched_resources: 1 });
    expect(medical.completedAt).toBeTruthy();
  });

  it('is order-tolerant: a completed event without a prior started still completes', () => {
    const s = fold([ev('agent_completed', 'INC-1', { agent: 'fire', output: { risk_level: 'high' } })]);
    expect(s.incidents['INC-1'].agents.fire.status).toBe('completed');
    expect(s.incidents['INC-1'].agents.fire.output).toEqual({ risk_level: 'high' });
  });

  it('records failures with the error message and surfaces an attention phase', () => {
    const s = fold([
      ev('agent_started', 'INC-1', { agent: 'security' }),
      ev('agent_failed', 'INC-1', { agent: 'security', error: 'node blew up' }),
    ]);
    const security = s.incidents['INC-1'].agents.security;
    expect(security.status).toBe('failed');
    expect(security.error).toBe('node blew up');
    expect(derivePhase(s.incidents['INC-1'])).toBe('attention');
  });

  it('tracks an unknown agent key using its event label instead of dropping it', () => {
    const s = fold([ev('agent_started', 'INC-1', { agent: 'weather', agent_label: 'Weather Agent' })]);
    expect(s.incidents['INC-1'].agents.weather.label).toBe('Weather Agent');
    // Unknown agents still appear (after the canonical eight) in ordered output.
    const labels = orderedAgents(s.incidents['INC-1']).map((a) => a.label);
    expect(labels[labels.length - 1]).toBe('Weather Agent');
  });

  it('lets a later approval decision take precedence over the planned stage', () => {
    const s = fold([
      ev('agent_completed', 'INC-1', { agent: 'synthesizer' }),
      ev('approval_required', 'INC-1', { plan_id: 'PLAN-1' }),
      ev('approval_approved', 'INC-1', { plan_id: 'PLAN-1', approved_by: 'Cmdr' }),
    ]);
    expect(derivePhase(s.incidents['INC-1'])).toBe('approved');
  });
});

describe('reduceRealtime — full pipeline + progress', () => {
  it('runs all eight agents to completion (progress = 1, phase = planned)', () => {
    const events: LiveEvent[] = [];
    for (const agent of AGENT_ORDER) {
      events.push(ev('agent_started', 'INC-1', { agent }));
      events.push(ev('agent_completed', 'INC-1', { agent, output: { ok: true } }));
    }
    const s = fold(events);
    const inc = s.incidents['INC-1'];
    expect(AGENT_ORDER.every((k) => inc.agents[k].status === 'completed')).toBe(true);
    expect(workflowProgress(inc)).toBe(1);
    expect(derivePhase(inc)).toBe('planned');
    expect(s.eventCount).toBe(AGENT_ORDER.length * 2);
  });

  it('reports a partial, truthful progress fraction mid-run', () => {
    const s = fold([
      ev('agent_completed', 'INC-1', { agent: 'supervisor' }),
      ev('agent_completed', 'INC-1', { agent: 'security' }),
      ev('agent_started', 'INC-1', { agent: 'medical' }),
    ]);
    // 2 of 8 completed.
    expect(workflowProgress(s.incidents['INC-1'])).toBeCloseTo(2 / 8, 5);
    expect(derivePhase(s.incidents['INC-1'])).toBe('coordinating');
  });
});

describe('reduceRealtime — approval + dispatch + lifecycle', () => {
  it('updates only the department named by a lifecycle event', () => {
    const s = fold([
      ev('department_notified', 'INC-ISO', { assignment_id: 1, department: 'SECURITY', status: 'NOTIFIED' }),
      ev('department_notified', 'INC-ISO', { assignment_id: 2, department: 'MEDICAL', status: 'NOTIFIED' }),
      ev('department_notified', 'INC-ISO', { assignment_id: 3, department: 'TRANSPORT', status: 'NOTIFIED' }),
      ev('dept_assignment_completed', 'INC-ISO', { assignment_id: 1, department: 'SECURITY', status: 'COMPLETED' }),
    ]);
    expect(s.incidents['INC-ISO'].assignments?.SECURITY?.status).toBe('COMPLETED');
    expect(s.incidents['INC-ISO'].assignments?.MEDICAL?.status).toBe('NOTIFIED');
    expect(s.incidents['INC-ISO'].assignments?.TRANSPORT?.status).toBe('NOTIFIED');
  });

  it('awaits approval on approval_required', () => {
    const s = fold([ev('approval_required', 'INC-1', { plan_id: 'PLAN-1', message: 'Needs sign-off' })]);
    const inc = s.incidents['INC-1'];
    expect(inc.approval.required).toBe(true);
    expect(inc.approval.status).toBe('pending');
    expect(inc.approval.planId).toBe('PLAN-1');
    expect(derivePhase(inc)).toBe('awaiting_approval');
  });

  it('treats the legacy approval_granted alias the same as approval_approved', () => {
    const granted = fold([ev('approval_granted', 'INC-1', { plan_id: 'PLAN-1' })]);
    const approved = fold([ev('approval_approved', 'INC-2', { plan_id: 'PLAN-2', approved_by: 'Cmdr' })]);
    expect(derivePhase(granted.incidents['INC-1'])).toBe('approved');
    expect(derivePhase(approved.incidents['INC-2'])).toBe('approved');
    expect(approved.incidents['INC-2'].approval.approvedBy).toBe('Cmdr');
  });

  it('marks rejection', () => {
    const s = fold([
      ev('approval_required', 'INC-1', { plan_id: 'PLAN-1' }),
      ev('approval_rejected', 'INC-1', { plan_id: 'PLAN-1' }),
    ]);
    expect(s.incidents['INC-1'].approval.status).toBe('rejected');
    expect(derivePhase(s.incidents['INC-1'])).toBe('rejected');
  });

  it('captures dispatch from response_dispatched (and from the existing dispatch_started)', () => {
    const canonical = fold([
      ev('response_dispatched', 'INC-1', { dispatched_resources: ['AMB-01', 'SEC-02'], location: 'Science Block' }),
    ]);
    expect(canonical.incidents['INC-1'].dispatch.dispatched).toBe(true);
    expect(canonical.incidents['INC-1'].dispatch.resources).toEqual(['AMB-01', 'SEC-02']);
    expect(canonical.incidents['INC-1'].dispatch.location).toBe('Science Block');
    expect(derivePhase(canonical.incidents['INC-1'])).toBe('dispatched');

    const legacy = fold([ev('dispatch_started', 'INC-2', { dispatched_resources: ['AMB-09'] })]);
    expect(legacy.incidents['INC-2'].dispatch.dispatched).toBe(true);
    expect(derivePhase(legacy.incidents['INC-2'])).toBe('dispatched');
  });

  it('phase reaches resolved on incident_resolved / incident_closed regardless of prior stage', () => {
    const resolved = fold([
      ev('response_dispatched', 'INC-1', { dispatched_resources: ['AMB-01'] }),
      ev('incident_resolved', 'INC-1'),
    ]);
    expect(derivePhase(resolved.incidents['INC-1'])).toBe('resolved');
    const closed = fold([ev('incident_closed', 'INC-2')]);
    expect(derivePhase(closed.incidents['INC-2'])).toBe('resolved');
  });

  it('derivePhase prefers the latest stage (dispatched > approved > awaiting)', () => {
    const s = fold([
      ev('approval_required', 'INC-1', { plan_id: 'PLAN-1' }),
      ev('approval_approved', 'INC-1', { plan_id: 'PLAN-1' }),
      ev('response_dispatched', 'INC-1', { dispatched_resources: ['AMB-01'] }),
    ]);
    expect(derivePhase(s.incidents['INC-1'])).toBe('dispatched');
  });
});

describe('reduceRealtime — end-to-end scenario', () => {
  it('progresses idle → analyzing → coordinating → planned → awaiting → approved → dispatched → resolved', () => {
    const phases: string[] = [];
    let s = initialRealtimeState();
    const step = (e: LiveEvent) => {
      s = reduceRealtime(s, e);
      phases.push(derivePhase(s.incidents['INC-1']));
    };

    step(ev('agent_started', 'INC-1', { agent: 'supervisor' })); // analyzing
    step(ev('agent_completed', 'INC-1', { agent: 'supervisor', output: { severity: 'high' } })); // coordinating
    step(ev('agent_started', 'INC-1', { agent: 'medical' })); // coordinating
    step(ev('agent_completed', 'INC-1', { agent: 'medical' })); // coordinating
    step(ev('agent_started', 'INC-1', { agent: 'synthesizer' })); // synthesizing
    step(ev('agent_completed', 'INC-1', { agent: 'synthesizer' })); // planned
    step(ev('approval_required', 'INC-1', { plan_id: 'PLAN-1' })); // awaiting_approval
    step(ev('approval_approved', 'INC-1', { plan_id: 'PLAN-1', approved_by: 'Cmdr' })); // approved
    step(ev('response_dispatched', 'INC-1', { dispatched_resources: ['AMB-01'] })); // dispatched
    step(ev('incident_resolved', 'INC-1')); // resolved

    expect(phases).toEqual([
      'analyzing',
      'coordinating',
      'coordinating',
      'coordinating',
      'synthesizing',
      'planned',
      'awaiting_approval',
      'approved',
      'dispatched',
      'resolved',
    ]);
  });
});

describe('reduceRealtime — robustness', () => {
  it('is idempotent when the same completed event is re-delivered', () => {
    const e = ev('agent_completed', 'INC-1', { agent: 'medical', output: { recommended_ambulances: 2 } });
    const once = reduceRealtime(initialRealtimeState(), e);
    const twice = reduceRealtime(once, e);
    expect(twice.incidents['INC-1'].agents.medical.status).toBe('completed');
    expect(twice.incidents['INC-1'].agents.medical.output).toEqual({ recommended_ambulances: 2 });
  });

  it('caps the number of tracked incidents (prunes least-recently-active)', () => {
    let s = initialRealtimeState();
    const total = MAX_TRACKED_INCIDENTS + 5;
    for (let i = 0; i < total; i += 1) {
      s = reduceRealtime(s, ev('agent_started', `INC-${i}`, { agent: 'supervisor' }));
    }
    expect(Object.keys(s.incidents).length).toBe(MAX_TRACKED_INCIDENTS);
    // The five oldest incidents were pruned; the most recent remain.
    expect(s.incidents['INC-0']).toBeUndefined();
    expect(s.incidents[`INC-${total - 1}`]).toBeDefined();
  });

  it('orderedAgents returns the canonical pipeline order for a fresh incident', () => {
    const s = fold([ev('agent_started', 'INC-1', { agent: 'supervisor' })]);
    expect(orderedAgents(s.incidents['INC-1']).map((a) => a.key)).toEqual([...AGENT_ORDER]);
  });

  it('coerces non-object output and non-array resources safely', () => {
    const s = fold([
      ev('agent_completed', 'INC-1', { agent: 'medical', output: 'not-an-object' }),
      ev('response_dispatched', 'INC-1', { dispatched_resources: 'not-an-array' }),
    ]);
    expect(s.incidents['INC-1'].agents.medical.output).toBeUndefined();
    expect(s.incidents['INC-1'].dispatch.resources).toEqual([]);
    expect(s.incidents['INC-1'].dispatch.dispatched).toBe(true);
  });
});
