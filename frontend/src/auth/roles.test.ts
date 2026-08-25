import { describe, it, expect } from 'vitest';
import {
  AuthUser,
  DEPARTMENTS,
  normalizeDepartment,
  departmentLabel,
  isPrivileged,
  isDepartmentRole,
  isCitizen,
  homePathFor,
  canAccessDepartmentPortal,
  canAccessCitizenPortal,
  canAccessCommandCenter,
  roleDisplayName,
  displayName,
} from './roles';

const operator: AuthUser = { role: 'operator', username: 'admin', full_name: 'Campus Operator' };
const admin: AuthUser = { role: 'admin', username: 'root', full_name: 'Site Admin' };
const citizen: AuthUser = { role: 'user', id: 'u1', full_name: 'Asha Student', email: 'a@vignan.ac.in' };
const security: AuthUser = { role: 'department', department: 'SECURITY', full_name: 'Guard One' };
const medicalHead: AuthUser = { role: 'department_head', department: 'medical', full_name: 'Dr. Rao' };

describe('normalizeDepartment', () => {
  it('canonicalizes case and whitespace', () => {
    expect(normalizeDepartment(' security ')).toBe('SECURITY');
    expect(normalizeDepartment('Medical')).toBe('MEDICAL');
  });
  it('rejects unknown / non-string values', () => {
    expect(normalizeDepartment('POLICE')).toBeNull();
    expect(normalizeDepartment(null)).toBeNull();
    expect(normalizeDepartment(42 as unknown)).toBeNull();
  });
  it('accepts every canonical department', () => {
    for (const d of DEPARTMENTS) expect(normalizeDepartment(d)).toBe(d);
  });
});

describe('departmentLabel', () => {
  it('maps codes to human labels', () => {
    expect(departmentLabel('FIRE')).toBe('Fire & Safety');
    expect(departmentLabel('transport')).toBe('Transport & Logistics');
  });
});

describe('role predicates', () => {
  it('classifies privileged roles', () => {
    expect(isPrivileged(operator)).toBe(true);
    expect(isPrivileged(admin)).toBe(true);
    expect(isPrivileged(citizen)).toBe(false);
    expect(isPrivileged(security)).toBe(false);
    expect(isPrivileged(null)).toBe(false);
  });
  it('classifies department roles', () => {
    expect(isDepartmentRole(security)).toBe(true);
    expect(isDepartmentRole(medicalHead)).toBe(true);
    expect(isDepartmentRole(operator)).toBe(false);
    expect(isDepartmentRole(citizen)).toBe(false);
  });
  it('classifies citizens', () => {
    expect(isCitizen(citizen)).toBe(true);
    expect(isCitizen({ role: 'student' })).toBe(true);
    expect(isCitizen(operator)).toBe(false);
    expect(isCitizen(security)).toBe(false);
  });
});

describe('homePathFor (ROLE -> PORTAL mapping)', () => {
  it('routes each role to its portal', () => {
    expect(homePathFor(operator)).toBe('/command');
    expect(homePathFor(admin)).toBe('/command');
    expect(homePathFor(citizen)).toBe('/portal');
    expect(homePathFor({ role: 'student' })).toBe('/portal');
    expect(homePathFor(security)).toBe('/dept/SECURITY');
    expect(homePathFor(medicalHead)).toBe('/dept/MEDICAL');
  });
  it('sends unknown / anonymous to login', () => {
    expect(homePathFor(null)).toBe('/login');
    expect(homePathFor({ role: 'department', department: 'nope' })).toBe('/login');
    expect(homePathFor({ role: 'martian' })).toBe('/login');
  });
});

describe('canAccessDepartmentPortal (cross-department isolation)', () => {
  it('lets a department into ONLY its own portal', () => {
    expect(canAccessDepartmentPortal(security, 'SECURITY')).toBe(true);
    expect(canAccessDepartmentPortal(security, 'MEDICAL')).toBe(false);
    expect(canAccessDepartmentPortal(security, 'TRANSPORT')).toBe(false);
    expect(canAccessDepartmentPortal(medicalHead, 'MEDICAL')).toBe(true);
    expect(canAccessDepartmentPortal(medicalHead, 'SECURITY')).toBe(false);
  });
  it('blocks citizens from every department portal', () => {
    for (const d of DEPARTMENTS) expect(canAccessDepartmentPortal(citizen, d)).toBe(false);
    expect(canAccessDepartmentPortal(null, 'SECURITY')).toBe(false);
  });
  it('allows privileged operators into any department portal', () => {
    for (const d of DEPARTMENTS) expect(canAccessDepartmentPortal(operator, d)).toBe(true);
  });
  it('rejects an invalid department target outright', () => {
    expect(canAccessDepartmentPortal(operator, 'POLICE')).toBe(false);
  });
});

describe('portal access guards', () => {
  it('citizen portal is citizens-only', () => {
    expect(canAccessCitizenPortal(citizen)).toBe(true);
    expect(canAccessCitizenPortal(operator)).toBe(false);
    expect(canAccessCitizenPortal(security)).toBe(false);
  });
  it('command center is privileged-only', () => {
    expect(canAccessCommandCenter(operator)).toBe(true);
    expect(canAccessCommandCenter(admin)).toBe(true);
    expect(canAccessCommandCenter(citizen)).toBe(false);
    expect(canAccessCommandCenter(security)).toBe(false);
  });
});

describe('display helpers', () => {
  it('produces a friendly role name', () => {
    expect(roleDisplayName(operator)).toBe('Safety Operations');
    expect(roleDisplayName(admin)).toBe('Administrator');
    expect(roleDisplayName(citizen)).toBe('Campus Member');
    expect(roleDisplayName(security)).toBe('Campus Security Staff');
    expect(roleDisplayName(medicalHead)).toBe('Medical & Health Lead');
    expect(roleDisplayName(null)).toBe('Guest');
  });
  it('prefers full_name, then username/email', () => {
    expect(displayName(citizen)).toBe('Asha Student');
    expect(displayName({ role: 'user', email: 'x@y.z' })).toBe('x@y.z');
    expect(displayName(null)).toBe('Guest');
  });
});
