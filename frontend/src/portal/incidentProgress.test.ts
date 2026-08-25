import { describe, it, expect } from 'vitest';
import { citizenProgress } from './incidentProgress';

const states = (status: string) => citizenProgress(status).phases.map((p) => p.state);

describe('citizenProgress', () => {
  it('starts at "reported" with the first phase active', () => {
    const p = citizenProgress('reported');
    expect(states('reported')).toEqual(['active', 'todo', 'todo', 'todo', 'todo']);
    expect(p.headline).toMatch(/received/i);
    expect(p.resolved).toBe(false);
    expect(p.onHold).toBe(false);
  });

  it('advances through assessment and planning', () => {
    expect(states('classified')).toEqual(['done', 'active', 'todo', 'todo', 'todo']);
    expect(states('response_planning')).toEqual(['done', 'done', 'active', 'todo', 'todo']);
    expect(states('awaiting_approval')).toEqual(['done', 'done', 'active', 'todo', 'todo']);
  });

  it('marks dispatch/monitoring as the fourth phase', () => {
    expect(states('dispatched')).toEqual(['done', 'done', 'done', 'active', 'todo']);
    expect(states('monitoring')).toEqual(['done', 'done', 'done', 'active', 'todo']);
  });

  it('marks every phase done when resolved or closed', () => {
    expect(states('resolved')).toEqual(['done', 'done', 'done', 'done', 'done']);
    expect(states('closed')).toEqual(['done', 'done', 'done', 'done', 'done']);
    expect(citizenProgress('resolved').resolved).toBe(true);
    expect(citizenProgress('closed').headline).toMatch(/verified/i);
  });

  it('treats rejected/cancelled/failed as a neutral on-hold state', () => {
    for (const s of ['rejected', 'cancelled', 'action_failed']) {
      const p = citizenProgress(s);
      expect(p.onHold).toBe(true);
      expect(p.resolved).toBe(false);
      expect(p.headline).toMatch(/hold|reviewing/i);
    }
  });

  it('is case-insensitive and tolerates unknown/empty status', () => {
    expect(states('RESOLVED')).toEqual(['done', 'done', 'done', 'done', 'done']);
    // unknown status falls back to the assessment phase, never crashes
    expect(citizenProgress('something_new').phases).toHaveLength(5);
    expect(citizenProgress(undefined).phases).toHaveLength(5);
    expect(citizenProgress(null).phases).toHaveLength(5);
  });

  it('never emits agent names or internal reasoning in labels', () => {
    const labels = citizenProgress('response_planning').phases.map((p) => p.label.toLowerCase());
    for (const l of labels) {
      expect(l).not.toMatch(/agent|langgraph|supervisor|confidence|resource|tool/);
    }
  });
});
