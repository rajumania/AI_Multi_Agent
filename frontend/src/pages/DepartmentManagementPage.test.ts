import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  canAccessDepartmentManagement,
  DEPARTMENTS,
  ROLE_ADMIN,
  ROLE_DEPARTMENT,
  ROLE_DEPARTMENT_HEAD,
  ROLE_OPERATOR,
} from '../auth/roles';
import {
  api,
  clearAuthToken,
  setAuthToken,
} from '../services/api';
import {
  DEPARTMENT_ACCOUNT_ROLES,
  DepartmentAccountFormValues,
  initialDepartmentAccountForm,
  safeCreatedDepartmentAccount,
  validateDepartmentAccountForm,
} from './DepartmentManagementPage';

const validValues: DepartmentAccountFormValues = {
  ...initialDepartmentAccountForm,
  fullName: 'Medical Operations Lead',
  email: 'medical-ops@example.com',
  password: 'secure-password',
  confirmPassword: 'secure-password',
};

describe('Department Management authorization and form rules', () => {
  it('allows only admin and operator principals', () => {
    expect(canAccessDepartmentManagement({ role: ROLE_ADMIN })).toBe(true);
    expect(canAccessDepartmentManagement({ role: ROLE_OPERATOR })).toBe(true);
    expect(canAccessDepartmentManagement({ role: 'user' })).toBe(false);
    expect(canAccessDepartmentManagement({ role: ROLE_DEPARTMENT, department: 'MEDICAL' })).toBe(false);
    expect(canAccessDepartmentManagement(null)).toBe(false);
  });

  it('uses every backend-supported department and role', () => {
    expect(DEPARTMENTS).toEqual(['SECURITY', 'MEDICAL', 'TRANSPORT', 'COMMUNICATION', 'FIRE', 'FACILITIES']);
    expect(DEPARTMENT_ACCOUNT_ROLES.map((item) => item.value)).toEqual([ROLE_DEPARTMENT, ROLE_DEPARTMENT_HEAD]);
  });

  it('rejects missing fields, invalid email, and password mismatch', () => {
    expect(validateDepartmentAccountForm(initialDepartmentAccountForm)).toBe('Full name is required.');
    expect(validateDepartmentAccountForm({ ...validValues, email: 'not-an-email' })).toBe('Enter a valid email address.');
    expect(validateDepartmentAccountForm({ ...validValues, confirmPassword: 'different' })).toBe('Passwords do not match.');
    expect(validateDepartmentAccountForm(validValues)).toBeNull();
  });

  it('keeps successful account metadata free of passwords', () => {
    const result = safeCreatedDepartmentAccount(
      { email: validValues.email, department: validValues.department, role: validValues.role, password: 'must-not-leak' },
      validValues,
    );
    expect(result).toEqual({
      full_name: validValues.fullName,
      email: validValues.email,
      department: validValues.department,
      role: validValues.role,
    });
    expect('password' in result).toBe(false);
  });
});

describe('Department registration API client', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    const values = new Map<string, string>();
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    });
    vi.stubGlobal('fetch', fetchMock);
    setAuthToken('operator-token');
    fetchMock.mockReset();
  });

  afterEach(() => {
    clearAuthToken();
    vi.unstubAllGlobals();
  });

  it('calls the existing protected registration endpoint with the operator token', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'success', email: validValues.email, department: 'MEDICAL', role: ROLE_DEPARTMENT }),
    });

    await api.registerDepartment({
      email: validValues.email,
      password: validValues.password,
      department: 'MEDICAL',
      full_name: validValues.fullName,
      role: ROLE_DEPARTMENT,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/auth/department/register',
      expect.objectContaining({ method: 'POST' }),
    );
    const request = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = request.headers as Headers;
    expect(headers.get('Authorization')).toBe('Bearer operator-token');
    expect(JSON.parse(String(request.body))).toMatchObject({
      email: validValues.email,
      department: 'MEDICAL',
      role: ROLE_DEPARTMENT,
    });
  });

  it('surfaces backend duplicate-email errors', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: 'Email already registered.' }),
    });

    await expect(api.registerDepartment({
      email: validValues.email,
      password: validValues.password,
      department: 'MEDICAL',
      full_name: validValues.fullName,
      role: ROLE_DEPARTMENT,
    })).rejects.toThrow('Email already registered.');
  });

  it('reports unauthorized session errors clearly', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 401, json: async () => ({}) });

    await expect(api.registerDepartment({
      email: validValues.email,
      password: validValues.password,
      department: 'MEDICAL',
      full_name: validValues.fullName,
      role: ROLE_DEPARTMENT_HEAD,
    })).rejects.toThrow('operator session is no longer valid');
  });
});
