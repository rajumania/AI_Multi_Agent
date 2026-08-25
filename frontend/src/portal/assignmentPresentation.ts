import { DepartmentAssignmentStatus } from '../types';

export type DepartmentAssignmentAction = 'accept' | 'decline' | 'team-assigned' | 'en-route' | 'on-scene' | 'completed';

export function assignmentActions(status: string): DepartmentAssignmentAction[] {
  switch (status.toUpperCase() as DepartmentAssignmentStatus) {
    case 'NOTIFIED': return ['accept', 'decline'];
    case 'ACCEPTED': return ['team-assigned'];
    case 'TEAM_ASSIGNED': return ['en-route'];
    case 'EN_ROUTE': return ['on-scene'];
    case 'ON_SCENE': return ['completed'];
    default: return [];
  }
}

export function assignmentStatusLabel(status: string): string {
  return status.replace(/_/g, ' ').toUpperCase();
}
