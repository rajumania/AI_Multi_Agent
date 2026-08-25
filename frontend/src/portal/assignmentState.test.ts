import { describe, expect, it } from 'vitest';
import { assignmentActions, assignmentStatusLabel } from './assignmentPresentation';
import { recentNotifications, unreadNotificationCount } from './notificationPresentation';
import { humanTeamVisual } from '../command3d/agentStatus';
import { initialRealtimeState, reduceRealtime } from '../realtime/workflowReducer';
import { NotificationItem } from '../types';

const event = (event_name: string, status: string, timestamp = '2026-08-24T10:00:00Z') => ({
  event_name,
  incident_id: 'INC-P6',
  department: 'MEDICAL',
  assignment_id: 7,
  status,
  assigned_resources: status === 'TEAM_ASSIGNED' ? ['AMB-001'] : [],
  timestamp,
});

describe('department assignment presentation and realtime state', () => {
  it('renders the human lifecycle actions without inventing intermediate actions', () => {
    expect(assignmentActions('NOTIFIED')).toEqual(['accept', 'decline']);
    expect(assignmentActions('ACCEPTED')).toEqual(['team-assigned']);
    expect(assignmentActions('TEAM_ASSIGNED')).toEqual(['en-route']);
    expect(assignmentActions('EN_ROUTE')).toEqual(['on-scene']);
    expect(assignmentActions('ON_SCENE')).toEqual(['completed']);
    expect(assignmentActions('COMPLETED')).toEqual([]);
  });

  it('uses backend assignment events as the source of status transitions', () => {
    let state = initialRealtimeState();
    state = reduceRealtime(state, event('department_notified', 'NOTIFIED'));
    state = reduceRealtime(state, event('dept_assignment_accepted', 'ACCEPTED'));
    state = reduceRealtime(state, event('dept_team_assigned', 'TEAM_ASSIGNED'));
    expect(state.incidents['INC-P6'].assignments?.MEDICAL.status).toBe('TEAM_ASSIGNED');
    expect(state.incidents['INC-P6'].assignments?.MEDICAL.assignedResources).toEqual(['AMB-001']);
  });

  it('keeps department statuses independent in the operator response panel state', () => {
    let state = initialRealtimeState();
    state = reduceRealtime(state, { ...event('dept_assignment_accepted', 'ACCEPTED'), department: 'MEDICAL' });
    state = reduceRealtime(state, { ...event('dept_on_scene', 'ON_SCENE'), department: 'SECURITY' });
    expect(state.incidents['INC-P6'].assignments?.MEDICAL.status).toBe('ACCEPTED');
    expect(state.incidents['INC-P6'].assignments?.SECURITY.status).toBe('ON_SCENE');
  });

  it('maps human 3D nodes to real assignment states', () => {
    expect(humanTeamVisual('NOTIFIED', '#34d399').label).toBe('Notified');
    expect(humanTeamVisual('EN_ROUTE', '#34d399').label).toBe('En Route');
    expect(humanTeamVisual('ON_SCENE', '#34d399').label).toBe('On Scene');
    expect(humanTeamVisual('DECLINED', '#34d399').status).toBe('FAILED');
  });

  it('formats operator-facing assignment statuses', () => {
    expect(assignmentStatusLabel('TEAM_ASSIGNED')).toBe('TEAM ASSIGNED');
  });

  it('renders notification count and recent ordering from backend rows', () => {
    const rows: NotificationItem[] = [
      { id: 1, recipient_type: 'department', department: 'MEDICAL', title: 'old', message: '', level: 'info', read: 0, created_at: '2026-08-23T10:00:00Z' },
      { id: 2, recipient_type: 'department', department: 'MEDICAL', title: 'new', message: '', level: 'info', read: 1, created_at: '2026-08-24T10:00:00Z' },
    ];
    expect(unreadNotificationCount(rows)).toBe(1);
    expect(recentNotifications(rows, 1)[0].id).toBe(2);
  });
});
