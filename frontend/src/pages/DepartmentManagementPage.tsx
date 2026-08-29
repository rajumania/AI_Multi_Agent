import React, { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, Building2, CheckCircle2, KeyRound, LockKeyhole, Mail, Pencil, RefreshCw, ShieldCheck, UserPlus, Users } from 'lucide-react';
import { DEPARTMENTS, DEPARTMENT_LABELS, DepartmentCode, ROLE_DEPARTMENT, ROLE_DEPARTMENT_HEAD } from '../auth/roles';
import { api, OrganizationDepartment, OrganizationDepartmentAccount, OrganizationUser } from '../services/api';

export const DEPARTMENT_ACCOUNT_ROLES = [
  { value: ROLE_DEPARTMENT, label: 'Department Staff' },
  { value: ROLE_DEPARTMENT_HEAD, label: 'Department Head' },
] as const;

export interface DepartmentAccountFormValues { fullName: string; email: string; department: string; role: typeof ROLE_DEPARTMENT | typeof ROLE_DEPARTMENT_HEAD; password: string; confirmPassword: string; }
export interface CreatedDepartmentAccount { full_name: string; email: string; department: string; role: string; }
export const initialDepartmentAccountForm: DepartmentAccountFormValues = { fullName: '', email: '', department: DEPARTMENTS[0], role: ROLE_DEPARTMENT, password: '', confirmPassword: '' };

export function validateDepartmentAccountForm(values: DepartmentAccountFormValues): string | null {
  if (!values.fullName.trim()) return 'Full name is required.';
  if (!values.email.trim()) return 'Email is required.';
  if (!/^\S+@\S+\.\S+$/.test(values.email.trim())) return 'Enter a valid email address.';
  if (!values.department.trim()) return 'Select a department.';
  if (!DEPARTMENT_ACCOUNT_ROLES.some((item) => item.value === values.role)) return 'Select a valid department role.';
  if (!values.password) return 'Password is required.';
  if (values.password !== values.confirmPassword) return 'Passwords do not match.';
  return null;
}

export function safeCreatedDepartmentAccount(result: Record<string, unknown>, values: DepartmentAccountFormValues): CreatedDepartmentAccount {
  return { full_name: values.fullName.trim(), email: String(result.email || values.email.trim()), department: String(result.department || values.department), role: String(result.role || values.role) };
}

const labelFor = (code: string) => DEPARTMENT_LABELS[code as DepartmentCode] || code;
const cardStyle: React.CSSProperties = { background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: '1rem' };

export const DepartmentManagementPage: React.FC = () => {
  const [departments, setDepartments] = useState<OrganizationDepartment[]>([]);
  const [accounts, setAccounts] = useState<OrganizationDepartmentAccount[]>([]);
  const [users, setUsers] = useState<OrganizationUser[]>([]);
  const [selectedCode, setSelectedCode] = useState('MEDICAL');
  const [values, setValues] = useState<DepartmentAccountFormValues>({ ...initialDepartmentAccountForm, department: 'MEDICAL' });
  const [newDepartment, setNewDepartment] = useState({ code: '', name: '', department_type: '', description: '' });
  const [edit, setEdit] = useState({ name: '', department_type: '', description: '' });
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const selected = useMemo(() => departments.find((item) => item.code === selectedCode) || departments[0], [departments, selectedCode]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [overview, orgUsers] = await Promise.all([api.getOrganizationOverview(), api.getOrganizationUsers()]);
      const rows = overview.departments || [];
      setDepartments(rows); setUsers(orgUsers || []);
      const next = rows.find((item) => item.code === selectedCode) || rows[0];
      if (next) {
        setSelectedCode(next.code);
        setEdit({ name: next.name, department_type: next.department_type, description: next.description || '' });
        setAccounts(await api.getOrganizationAccounts(next.code));
      }
      setError(null);
    } catch (requestError: unknown) { setError(requestError instanceof Error ? requestError.message : 'Organization data could not be loaded.'); }
    finally { setLoading(false); }
  }, [selectedCode]);
  useEffect(() => { void load(); }, [load]);

  const selectDepartment = async (code: string) => {
    setSelectedCode(code); setValues((current) => ({ ...current, department: code })); const row = departments.find((item) => item.code === code);
    if (row) { setEdit({ name: row.name, department_type: row.department_type, description: row.description || '' }); try { setAccounts(await api.getOrganizationAccounts(code)); } catch (requestError: unknown) { setError(requestError instanceof Error ? requestError.message : 'Account list failed.'); } }
  };
  const submitAccount = async (event: FormEvent) => {
    event.preventDefault(); const validationError = validateDepartmentAccountForm(values); if (validationError) { setError(validationError); return; }
    setSubmitting(true); setError(null); setNotice(null);
    try { await api.createOrganizationAccount(selectedCode, { email: values.email.trim().toLowerCase(), password: values.password, full_name: values.fullName.trim(), role: values.role }); setNotice(`Account created in ${labelFor(selectedCode)}. The password is not retained or displayed by AITAM.`); setValues({ ...initialDepartmentAccountForm, department: values.department }); setAccounts(await api.getOrganizationAccounts(selectedCode)); await load(); }
    catch (requestError: unknown) { setError(requestError instanceof Error ? requestError.message : 'Account creation failed.'); }
    finally { setSubmitting(false); }
  };
  const submitDepartment = async (event: FormEvent) => {
    event.preventDefault(); setSubmitting(true); setError(null); setNotice(null);
    try { await api.createOrganizationDepartment(newDepartment); setNewDepartment({ code: '', name: '', department_type: '', description: '' }); setNotice('Department created in the authoritative AITAM organization registry.'); await load(); }
    catch (requestError: unknown) { setError(requestError instanceof Error ? requestError.message : 'Department creation failed.'); }
    finally { setSubmitting(false); }
  };
  const saveDepartment = async () => { if (!selected) return; setSubmitting(true); setError(null); try { await api.updateOrganizationDepartment(selected.code, edit); setNotice('Department profile updated.'); await load(); } catch (requestError: unknown) { setError(requestError instanceof Error ? requestError.message : 'Department update failed.'); } finally { setSubmitting(false); } };
  const toggleDepartment = async () => { if (!selected) return; try { await api.updateOrganizationDepartment(selected.code, { status: selected.status === 'active' ? 'inactive' : 'active' }); setNotice(`Department ${selected.status === 'active' ? 'deactivated' : 'activated'}.`); await load(); } catch (requestError: unknown) { setError(requestError instanceof Error ? requestError.message : 'Department status update failed.'); } };
  const updateAccount = async (account: OrganizationDepartmentAccount, payload: { status?: 'active' | 'suspended'; password?: string }) => { try { await api.updateOrganizationAccount(account.id, payload); setNotice(`Account ${account.email} updated.`); setAccounts(await api.getOrganizationAccounts(selectedCode)); } catch (requestError: unknown) { setError(requestError instanceof Error ? requestError.message : 'Account update failed.'); } };
  const resetAccount = (account: OrganizationDepartmentAccount) => { const password = window.prompt(`Set a new password for ${account.email}. It will not be shown again.`); if (password) void updateAccount(account, { password }); };

  return <div className="app-content">
    <div className="dashboard-title-row"><div><h2>AITAM Organization Administration</h2><p>Authoritative department registry, staff access, operational scope, and status.</p></div><div className="panel-tag"><ShieldCheck size={14} /> ADMIN-ONLY CONTROL</div></div>
    {error && <div role="alert" className="alert-banner error"><AlertCircle size={16} /> {error}</div>}{notice && <div role="status" className="alert-banner success"><CheckCircle2 size={16} /> {notice}</div>}
    <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: '.75rem', marginBottom: '1rem' }}><div style={cardStyle}><small>ORGANIZATION</small><strong style={{ display: 'block', marginTop: '.3rem' }}>AITAM</strong><span>Active registry</span></div><div style={cardStyle}><small>DEPARTMENTS</small><strong style={{ display: 'block', marginTop: '.3rem' }}>{departments.length}</strong><span>{departments.filter((item) => item.status === 'active').length} active</span></div><div style={cardStyle}><small>STAFF ACCOUNTS</small><strong style={{ display: 'block', marginTop: '.3rem' }}>{departments.reduce((sum, item) => sum + item.account_count, 0)}</strong><span>Backend identities</span></div><div style={cardStyle}><small>LIVE OPERATIONS</small><strong style={{ display: 'block', marginTop: '.3rem' }}>{departments.reduce((sum, item) => sum + item.active_incidents, 0)}</strong><span>Routed active incidents</span></div></section>
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px,.9fr) minmax(0,2fr)', gap: '1rem', alignItems: 'start' }}>
      <section style={cardStyle}><div className="panel-header"><div className="panel-title"><Building2 size={18} color="#0284c7" /> Departments</div><button className="btn btn-sm btn-outline" onClick={() => void load()}><RefreshCw size={14} /></button></div>{loading ? <p>Loading registry…</p> : departments.map((item) => <button key={item.code} type="button" onClick={() => void selectDepartment(item.code)} style={{ width: '100%', textAlign: 'left', padding: '.75rem', marginTop: '.45rem', borderRadius: 9, border: `1px solid ${selectedCode === item.code ? '#0284c7' : '#e2e8f0'}`, background: selectedCode === item.code ? '#eff6ff' : '#fff', cursor: 'pointer' }}><strong>{item.name}</strong><span style={{ display: 'block', fontSize: '.68rem', color: '#64748b', marginTop: '.2rem' }}>{item.code} · {item.account_count} accounts · {item.active_incidents} active</span><span style={{ color: item.status === 'active' ? '#15803d' : '#b91c1c', fontSize: '.65rem', fontWeight: 800 }}>{item.status.toUpperCase()}</span></button>)}<form onSubmit={submitDepartment} style={{ borderTop: '1px solid #e2e8f0', marginTop: '1rem', paddingTop: '1rem' }}><strong style={{ fontSize: '.8rem' }}>Create department</strong><input className="form-input" style={{ marginTop: '.5rem' }} placeholder="Code e.g. WELFARE" value={newDepartment.code} onChange={(e) => setNewDepartment({ ...newDepartment, code: e.target.value })} required /><input className="form-input" style={{ marginTop: '.45rem' }} placeholder="Department name" value={newDepartment.name} onChange={(e) => setNewDepartment({ ...newDepartment, name: e.target.value })} required /><input className="form-input" style={{ marginTop: '.45rem' }} placeholder="Type" value={newDepartment.department_type} onChange={(e) => setNewDepartment({ ...newDepartment, department_type: e.target.value })} required /><button className="btn btn-primary" style={{ marginTop: '.55rem', width: '100%' }} disabled={submitting}><Building2 size={14} /> Create department</button></form></section>
      <div style={{ display: 'grid', gap: '1rem' }}>
        {selected && <section style={cardStyle}><div className="panel-header"><div><div className="panel-title"><Pencil size={17} color="#0284c7" /> {selected.name}</div><small>{selected.code} · {selected.department_type} · {selected.resource_count} scoped resources</small></div><button className="btn btn-sm btn-outline" onClick={() => void toggleDepartment()}>{selected.status === 'active' ? 'Deactivate' : 'Activate'}</button></div><div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: '.6rem' }}><input className="form-input" value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /><input className="form-input" value={edit.department_type} onChange={(e) => setEdit({ ...edit, department_type: e.target.value })} /><input className="form-input" value={edit.description} onChange={(e) => setEdit({ ...edit, description: e.target.value })} placeholder="Scope description" /></div><button className="btn btn-outline" style={{ marginTop: '.65rem' }} onClick={() => void saveDepartment()} disabled={submitting}>Save department profile</button></section>}
        <section style={cardStyle}><div className="panel-header"><div className="panel-title"><UserPlus size={18} color="#0284c7" /> Provision staff account</div><span className="panel-tag">HASHED SERVER-SIDE</span></div><form onSubmit={submitAccount}><div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: '.65rem' }}><label><span className="form-label"><Users size={13} /> Full name</span><input className="form-input" value={values.fullName} onChange={(e) => setValues({ ...values, fullName: e.target.value })} required /></label><label><span className="form-label"><Mail size={13} /> Email</span><input className="form-input" type="email" value={values.email} onChange={(e) => setValues({ ...values, email: e.target.value })} required /></label><label><span className="form-label"><Building2 size={13} /> Department</span><select className="form-select" value={selectedCode} onChange={(e) => void selectDepartment(e.target.value)}>{departments.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}</select></label><label><span className="form-label"><ShieldCheck size={13} /> Role</span><select className="form-select" value={values.role} onChange={(e) => setValues({ ...values, role: e.target.value as DepartmentAccountFormValues['role'] })}><option value={ROLE_DEPARTMENT}>Staff</option><option value={ROLE_DEPARTMENT_HEAD}>Head</option></select></label><label><span className="form-label"><LockKeyhole size={13} /> Password</span><input className="form-input" type="password" value={values.password} onChange={(e) => setValues({ ...values, password: e.target.value })} required /></label><label><span className="form-label"><KeyRound size={13} /> Confirm password</span><input className="form-input" type="password" value={values.confirmPassword} onChange={(e) => setValues({ ...values, confirmPassword: e.target.value })} required /></label></div><button className="btn btn-primary" style={{ marginTop: '.8rem' }} disabled={submitting}><UserPlus size={15} /> Create scoped account</button></form></section>
        <section style={cardStyle}><div className="panel-header"><div className="panel-title"><Users size={18} color="#0d9488" /> {labelFor(selectedCode)} accounts</div><span className="panel-tag">{accounts.length} RECORDS</span></div>{accounts.length === 0 ? <p>No staff account is assigned to this department.</p> : <div style={{ display: 'grid', gap: '.45rem' }}>{accounts.map((account) => <div key={account.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '.6rem', flexWrap: 'wrap', padding: '.65rem', border: '1px solid #e2e8f0', borderRadius: 8 }}><div><strong>{account.full_name || account.email}</strong><small style={{ display: 'block', color: '#64748b' }}>{account.email} · {account.role} · <span style={{ color: account.status === 'active' ? '#15803d' : '#b91c1c' }}>{account.status}</span></small></div><div style={{ display: 'flex', gap: '.35rem' }}><button className="btn btn-sm btn-outline" onClick={() => void updateAccount(account, { status: account.status === 'active' ? 'suspended' : 'active' })}>{account.status === 'active' ? 'Deactivate' : 'Activate'}</button><button className="btn btn-sm btn-outline" onClick={() => resetAccount(account)}>Reset password</button></div></div>)}</div>}</section>
        <section style={cardStyle}><div className="panel-header"><div className="panel-title"><Users size={18} color="#7c3aed" /> User department assignment</div><span className="panel-tag">AUTHORITY CONTROL</span></div><div style={{ display: 'grid', gap: '.45rem' }}>{users.filter((user) => user.role !== 'user').map((user) => <div key={user.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '.5rem', flexWrap: 'wrap', fontSize: '.78rem' }}><span><strong>{user.full_name || user.username}</strong><small style={{ display: 'block', color: '#64748b' }}>{user.username} · {user.role}</small></span><select className="form-select" style={{ width: 220 }} value={user.department || ''} onChange={(e) => api.assignOrganizationUser(user.id, e.target.value || null).then(() => load()).catch((requestError: unknown) => setError(requestError instanceof Error ? requestError.message : 'User assignment failed.'))}><option value="">No department</option>{departments.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}</select></div>)}</div></section>
      </div>
    </div>
    <p style={{ marginTop: '1rem', color: '#64748b', fontSize: '.72rem' }}>All management actions are persisted in campusflow.db and protected by the existing privileged authentication guard. Passwords and hashes never enter the response payload.</p>
  </div>;
};
