import React, { FormEvent, useState } from 'react';
import {
  AlertCircle,
  Building2,
  CheckCircle2,
  KeyRound,
  LockKeyhole,
  Mail,
  ShieldCheck,
  UserPlus,
} from 'lucide-react';

import {
  DEPARTMENTS,
  DEPARTMENT_LABELS,
  DepartmentCode,
  ROLE_DEPARTMENT,
  ROLE_DEPARTMENT_HEAD,
} from '../auth/roles';
import { api, DepartmentRegistrationPayload } from '../services/api';

export const DEPARTMENT_ACCOUNT_ROLES = [
  { value: ROLE_DEPARTMENT, label: 'Department Staff' },
  { value: ROLE_DEPARTMENT_HEAD, label: 'Department Head' },
] as const;

export interface DepartmentAccountFormValues {
  fullName: string;
  email: string;
  department: DepartmentCode;
  role: typeof ROLE_DEPARTMENT | typeof ROLE_DEPARTMENT_HEAD;
  password: string;
  confirmPassword: string;
}

export interface CreatedDepartmentAccount {
  full_name: string;
  email: string;
  department: string;
  role: string;
}

export const initialDepartmentAccountForm: DepartmentAccountFormValues = {
  fullName: '',
  email: '',
  department: DEPARTMENTS[0],
  role: ROLE_DEPARTMENT,
  password: '',
  confirmPassword: '',
};

export function validateDepartmentAccountForm(values: DepartmentAccountFormValues): string | null {
  if (!values.fullName.trim()) return 'Full name is required.';
  if (!values.email.trim()) return 'Email is required.';
  if (!/^\S+@\S+\.\S+$/.test(values.email.trim())) return 'Enter a valid email address.';
  if (!DEPARTMENTS.includes(values.department)) return 'Select a supported department.';
  if (!DEPARTMENT_ACCOUNT_ROLES.some((item) => item.value === values.role)) return 'Select a valid department role.';
  if (!values.password) return 'Password is required.';
  if (values.password !== values.confirmPassword) return 'Passwords do not match.';
  return null;
}

export function safeCreatedDepartmentAccount(
  result: Record<string, unknown>,
  values: DepartmentAccountFormValues,
): CreatedDepartmentAccount {
  return {
    full_name: values.fullName.trim(),
    email: String(result.email || values.email.trim()),
    department: String(result.department || values.department),
    role: String(result.role || values.role),
  };
}

function roleLabel(role: string): string {
  return DEPARTMENT_ACCOUNT_ROLES.find((item) => item.value === role)?.label || role;
}

export const DepartmentManagementPage: React.FC = () => {
  const [values, setValues] = useState<DepartmentAccountFormValues>(initialDepartmentAccountForm);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdAccount, setCreatedAccount] = useState<CreatedDepartmentAccount | null>(null);

  const update = <K extends keyof DepartmentAccountFormValues>(key: K, value: DepartmentAccountFormValues[K]) => {
    setValues((current) => ({ ...current, [key]: value }));
    setError(null);
    setCreatedAccount(null);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const validationError = validateDepartmentAccountForm(values);
    if (validationError) {
      setError(validationError);
      setCreatedAccount(null);
      return;
    }

    const payload: DepartmentRegistrationPayload = {
      email: values.email.trim().toLowerCase(),
      password: values.password,
      department: values.department,
      full_name: values.fullName.trim(),
      role: values.role,
    };

    setSubmitting(true);
    setError(null);
    setCreatedAccount(null);
    try {
      const result = await api.registerDepartment(payload);
      setCreatedAccount(safeCreatedDepartmentAccount(result, values));
      setValues(initialDepartmentAccountForm);
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'Department account creation failed.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="app-content">
      <div className="dashboard-title-row">
        <div>
          <h2>Department Management</h2>
          <p>Manage specialized emergency response department accounts.</p>
        </div>
        <div className="panel-tag" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
          <ShieldCheck size={14} /> Privileged Access
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(260px, 1fr)', gap: '1.25rem', alignItems: 'start' }}>
        <section className="panel-card" aria-labelledby="create-department-account-heading">
          <div className="panel-header">
            <div className="panel-title" id="create-department-account-heading">
              <UserPlus size={18} color="#0284c7" />
              Create Department Account
            </div>
            <span className="panel-tag">Admin / Operator</span>
          </div>

          <form className="panel-body" onSubmit={handleSubmit} noValidate>
            {error && (
              <div role="alert" style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', padding: '0.75rem', marginBottom: '1rem', borderRadius: 'var(--radius-md)', color: '#b91c1c', background: '#fef2f2', border: '1px solid #fecaca', fontSize: '0.8125rem' }}>
                <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '0.05rem' }} />
                <span>{error}</span>
              </div>
            )}

            {createdAccount && (
              <div role="status" style={{ padding: '0.85rem', marginBottom: '1rem', borderRadius: 'var(--radius-md)', color: '#166534', background: '#f0fdf4', border: '1px solid #bbf7d0' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontWeight: 700, fontSize: '0.875rem', marginBottom: '0.55rem' }}>
                  <CheckCircle2 size={16} /> Department account created successfully.
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.35rem 1rem', fontSize: '0.78rem' }}>
                  <span><strong>Name:</strong> {createdAccount.full_name}</span>
                  <span><strong>Email:</strong> {createdAccount.email}</span>
                  <span><strong>Department:</strong> {DEPARTMENT_LABELS[createdAccount.department as DepartmentCode] || createdAccount.department}</span>
                  <span><strong>Role:</strong> {roleLabel(createdAccount.role)}</span>
                </div>
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
              <label>
                <span className="form-label"><UserPlus size={14} /> Full Name</span>
                <input className="form-input" type="text" autoComplete="name" value={values.fullName} onChange={(event) => update('fullName', event.target.value)} placeholder="e.g. Dr. K. S. Rao" />
              </label>
              <label>
                <span className="form-label"><Mail size={14} /> Email</span>
                <input className="form-input" type="email" autoComplete="email" value={values.email} onChange={(event) => update('email', event.target.value)} placeholder="department-admin@vignan.ac.in" />
              </label>
            </div>

            <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '1.1rem', marginBottom: '1.25rem' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>Department Assignment</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
                <label>
                  <span className="form-label"><Building2 size={14} /> Department</span>
                  <select className="form-select" value={values.department} onChange={(event) => update('department', event.target.value as DepartmentCode)}>
                    {DEPARTMENTS.map((department) => <option key={department} value={department}>{DEPARTMENT_LABELS[department]} ({department})</option>)}
                  </select>
                </label>
                <label>
                  <span className="form-label"><ShieldCheck size={14} /> Role</span>
                  <select className="form-select" value={values.role} onChange={(event) => update('role', event.target.value as DepartmentAccountFormValues['role'])}>
                    {DEPARTMENT_ACCOUNT_ROLES.map((role) => <option key={role.value} value={role.value}>{role.label} ({role.value})</option>)}
                  </select>
                </label>
              </div>
            </div>

            <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '1.1rem' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>Security</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
                <label>
                  <span className="form-label"><LockKeyhole size={14} /> Password</span>
                  <input className="form-input" type="password" autoComplete="new-password" value={values.password} onChange={(event) => update('password', event.target.value)} placeholder="Set an account password" />
                </label>
                <label>
                  <span className="form-label"><KeyRound size={14} /> Confirm Password</span>
                  <input className="form-input" type="password" autoComplete="new-password" value={values.confirmPassword} onChange={(event) => update('confirmPassword', event.target.value)} placeholder="Re-enter the password" />
                </label>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1.35rem' }}>
              <button className="btn btn-primary" type="submit" disabled={submitting}>
                <UserPlus size={16} />
                {submitting ? 'Creating Account...' : 'Create Department Account'}
              </button>
            </div>
          </form>
        </section>

        <aside className="panel-card">
          <div className="panel-header">
            <div className="panel-title"><ShieldCheck size={18} color="#0d9488" /> Account Provisioning</div>
          </div>
          <div className="panel-body" style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            <p style={{ marginTop: 0 }}>New accounts are created by the backend and assigned permanently to the selected department.</p>
            <p>The department user signs in from the existing Department Login flow. This screen does not display or retain the account password.</p>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.45rem', padding: '0.65rem', borderRadius: 'var(--radius-md)', background: '#f8fafc', border: '1px solid var(--border-subtle)', fontSize: '0.75rem' }}>
              <ShieldCheck size={15} color="#0284c7" style={{ flexShrink: 0, marginTop: '0.1rem' }} />
              <span>Department account listing is not shown because the existing backend exposes creation and login, but no safe account-list endpoint.</span>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
};
