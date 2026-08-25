import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Shield,
  Lock,
  User,
  Mail,
  Phone,
  Building,
  Sparkles,
  AlertCircle,
  UserPlus,
} from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { TeamGenAIShowcase } from '../components/TeamGenAIShowcase';
import {
  AuthUser,
  DEPARTMENTS,
  DEPARTMENT_LABELS,
  DepartmentCode,
  homePathFor,
} from '../auth/roles';

type Mode = 'operator' | 'member' | 'department';

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '0.65rem 0.75rem 0.65rem 2.25rem',
  background: '#0f172a',
  border: '1px solid #334155',
  borderRadius: '8px',
  color: '#ffffff',
  fontSize: '0.875rem',
  outline: 'none',
  transition: 'border-color 0.15s ease',
};

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '0.75rem',
  fontWeight: 600,
  color: '#94a3b8',
  marginBottom: '0.4rem',
  textTransform: 'uppercase',
};

const iconWrapStyle: React.CSSProperties = {
  position: 'absolute',
  left: '0.75rem',
  top: '50%',
  transform: 'translateY(-50%)',
  color: '#64748b',
  display: 'flex',
  alignItems: 'center',
};

function Field({
  label,
  icon,
  children,
}: {
  label: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      <div style={{ position: 'relative' }}>
        <div style={iconWrapStyle}>{icon}</div>
        {children}
      </div>
    </div>
  );
}

const focusOn = (e: React.FocusEvent<HTMLInputElement | HTMLSelectElement>) =>
  (e.target.style.borderColor = '#6366f1');
const focusOff = (e: React.FocusEvent<HTMLInputElement | HTMLSelectElement>) =>
  (e.target.style.borderColor = '#334155');

/**
 * Multi-mode login page (Increment 2). Authenticates against the EXISTING
 * backend auth APIs via AuthContext — there is no fake frontend-only auth. On
 * success the caller is routed to the portal that matches their server-verified
 * role (homePathFor).
 */
export const LoginPage: React.FC = () => {
  const {
    loginOperator,
    loginCitizen,
    registerCitizen,
    loginDepartment,
    sessionExpired,
    clearSessionExpired,
  } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState<Mode>('operator');
  const [memberMode, setMemberMode] = useState<'login' | 'register'>('login');

  // operator
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  // member (citizen)
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [fullName, setFullName] = useState('');
  // department
  const [deptEmail, setDeptEmail] = useState('');
  const [deptPassword, setDeptPassword] = useState('');
  const [department, setDepartment] = useState<DepartmentCode>('SECURITY');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const finish = (user: AuthUser) => navigate(homePathFor(user), { replace: true });

  const switchMode = (next: Mode) => {
    setMode(next);
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    clearSessionExpired();
    setLoading(true);
    try {
      let user: AuthUser;
      if (mode === 'operator') {
        if (!username || !password) throw new Error('Enter your username and password.');
        user = await loginOperator(username.trim(), password);
      } else if (mode === 'member') {
        if (!email || !phone) {
          throw new Error(
            memberMode === 'register'
              ? 'Enter your email and phone to register.'
              : 'Enter your registered email and phone.',
          );
        }
        user =
          memberMode === 'register'
            ? await registerCitizen(email.trim(), phone.trim(), fullName.trim() || undefined)
            : await loginCitizen(email.trim(), phone.trim());
      } else {
        if (!deptEmail || !deptPassword) {
          throw new Error('Enter your department email and password.');
        }
        user = await loginDepartment(deptEmail.trim(), deptPassword, department);
      }
      finish(user);
    } catch (err: any) {
      setError(err?.message || 'Sign in failed. Please check your details and try again.');
    } finally {
      setLoading(false);
    }
  };

  const tabs: { key: Mode; label: string }[] = [
    { key: 'operator', label: 'Operator' },
    { key: 'member', label: 'Campus Member' },
    { key: 'department', label: 'Department' },
  ];

  const submitLabel =
    mode === 'operator'
      ? 'SIGN IN TO COMMAND CENTER'
      : mode === 'department'
        ? 'SIGN IN TO DEPARTMENT PORTAL'
        : memberMode === 'register'
          ? 'REGISTER & ENTER PORTAL'
          : 'SIGN IN TO MY PORTAL';

  return (
    <div
      className="login-page-shell"
      style={{
        position: 'relative',
        overflow: 'hidden',
        background: '#050b18',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        padding: '1rem',
        fontFamily: 'Inter, sans-serif',
      }}
    >
      <div
        style={{
          position: 'absolute',
          width: '400px',
          height: '400px',
          background: 'rgba(99, 102, 241, 0.1)',
          filter: 'blur(100px)',
          borderRadius: '50%',
          top: '10%',
          left: '15%',
          pointerEvents: 'none',
        }}
      />
      <div
        style={{
          position: 'absolute',
          width: '400px',
          height: '400px',
          background: 'rgba(14, 165, 233, 0.1)',
          filter: 'blur(100px)',
          borderRadius: '50%',
          bottom: '10%',
          right: '15%',
          pointerEvents: 'none',
        }}
      />

      <TeamGenAIShowcase />

      <div
        className="login-card"
        style={{
          position: 'relative',
          background: 'rgba(30, 41, 59, 0.7)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '16px',
          padding: '2.5rem',
          width: '100%',
          maxWidth: '460px',
          boxShadow: '0 20px 40px rgba(0, 0, 0, 0.3)',
          color: '#ffffff',
          zIndex: 10,
        }}
      >
        {/* Header/Logo */}
        <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          <div
            style={{
              display: 'inline-flex',
              background: 'linear-gradient(135deg, #6366f1 0%, #0ea5e9 100%)',
              padding: '0.75rem',
              borderRadius: '12px',
              boxShadow: '0 8px 16px rgba(99, 102, 241, 0.3)',
              marginBottom: '1rem',
            }}
          >
            <Shield size={32} color="#ffffff" />
          </div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 800, margin: 0, letterSpacing: '-0.025em' }}>
            CAMPUSFLOW AI
          </h2>
          <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginTop: '0.35rem' }}>
            Vignan University Emergency Response
          </p>
        </div>

        {/* Mode tabs */}
        <div
          style={{
            display: 'flex',
            gap: '0.35rem',
            background: '#0f172a',
            border: '1px solid #334155',
            borderRadius: '10px',
            padding: '0.25rem',
            marginBottom: '1.5rem',
          }}
        >
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => switchMode(tab.key)}
              style={{
                flex: 1,
                padding: '0.5rem 0.25rem',
                background: mode === tab.key ? 'linear-gradient(135deg, #6366f1 0%, #0ea5e9 100%)' : 'transparent',
                border: 'none',
                borderRadius: '8px',
                color: mode === tab.key ? '#ffffff' : '#94a3b8',
                fontSize: '0.75rem',
                fontWeight: 700,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Session-expired notice */}
        {sessionExpired && !error && (
          <div
            style={{
              background: 'rgba(234, 179, 8, 0.1)',
              border: '1px solid #eab308',
              borderRadius: '8px',
              padding: '0.75rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontSize: '0.8rem',
              color: '#facc15',
              marginBottom: '1.25rem',
            }}
          >
            <AlertCircle size={16} />
            <span>Your session expired. Please sign in again.</span>
          </div>
        )}

        {/* Error */}
        {error && (
          <div
            style={{
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid #ef4444',
              borderRadius: '8px',
              padding: '0.75rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              fontSize: '0.8rem',
              color: '#f87171',
              marginBottom: '1.25rem',
            }}
          >
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
          {mode === 'operator' && (
            <>
              <Field label="Username" icon={<User size={16} />}>
                <input
                  type="text"
                  placeholder="Enter username"
                  style={inputStyle}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  onFocus={focusOn}
                  onBlur={focusOff}
                />
              </Field>
              <Field label="Password" icon={<Lock size={16} />}>
                <input
                  type="password"
                  placeholder="••••••••"
                  style={inputStyle}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onFocus={focusOn}
                  onBlur={focusOff}
                />
              </Field>
            </>
          )}

          {mode === 'member' && (
            <>
              {memberMode === 'register' && (
                <Field label="Full Name (optional)" icon={<User size={16} />}>
                  <input
                    type="text"
                    placeholder="e.g. Asha Kumari"
                    style={inputStyle}
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    onFocus={focusOn}
                    onBlur={focusOff}
                  />
                </Field>
              )}
              <Field label="Email" icon={<Mail size={16} />}>
                <input
                  type="email"
                  placeholder="you@vignan.ac.in"
                  style={inputStyle}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onFocus={focusOn}
                  onBlur={focusOff}
                />
              </Field>
              <Field label="Phone" icon={<Phone size={16} />}>
                <input
                  type="tel"
                  placeholder="10-digit mobile number"
                  style={inputStyle}
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  onFocus={focusOn}
                  onBlur={focusOff}
                />
              </Field>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '-0.35rem' }}>
                {memberMode === 'login' ? (
                  <>
                    New here?{' '}
                    <span
                      onClick={() => {
                        setMemberMode('register');
                        setError(null);
                      }}
                      style={{ color: '#38bdf8', fontWeight: 600, cursor: 'pointer', textDecoration: 'underline' }}
                    >
                      Register with email + phone
                    </span>
                  </>
                ) : (
                  <>
                    Already registered?{' '}
                    <span
                      onClick={() => {
                        setMemberMode('login');
                        setError(null);
                      }}
                      style={{ color: '#38bdf8', fontWeight: 600, cursor: 'pointer', textDecoration: 'underline' }}
                    >
                      Sign in instead
                    </span>
                  </>
                )}
              </div>
            </>
          )}

          {mode === 'department' && (
            <>
              <Field label="Department" icon={<Building size={16} />}>
                <select
                  style={{ ...inputStyle, appearance: 'none' as const }}
                  value={department}
                  onChange={(e) => setDepartment(e.target.value as DepartmentCode)}
                  onFocus={focusOn}
                  onBlur={focusOff}
                >
                  {DEPARTMENTS.map((code) => (
                    <option key={code} value={code}>
                      {DEPARTMENT_LABELS[code]}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Department Email" icon={<Mail size={16} />}>
                <input
                  type="email"
                  placeholder="security@vignan.ac.in"
                  style={inputStyle}
                  value={deptEmail}
                  onChange={(e) => setDeptEmail(e.target.value)}
                  onFocus={focusOn}
                  onBlur={focusOff}
                />
              </Field>
              <Field label="Password" icon={<Lock size={16} />}>
                <input
                  type="password"
                  placeholder="••••••••"
                  style={inputStyle}
                  value={deptPassword}
                  onChange={(e) => setDeptPassword(e.target.value)}
                  onFocus={focusOn}
                  onBlur={focusOff}
                />
              </Field>
            </>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '0.75rem',
              background: 'linear-gradient(135deg, #6366f1 0%, #0ea5e9 100%)',
              border: 'none',
              borderRadius: '8px',
              color: '#ffffff',
              fontSize: '0.875rem',
              fontWeight: 700,
              cursor: loading ? 'not-allowed' : 'pointer',
              boxShadow: '0 4px 12px rgba(99, 102, 241, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.4rem',
              transition: 'opacity 0.15s ease',
              marginTop: '0.25rem',
            }}
            onMouseOver={(e) => (e.currentTarget.style.opacity = '0.9')}
            onMouseOut={(e) => (e.currentTarget.style.opacity = '1')}
          >
            {loading ? (
              <span>Authenticating…</span>
            ) : (
              <>
                {mode === 'member' && memberMode === 'register' ? <UserPlus size={16} /> : <Sparkles size={16} />}
                <span>{submitLabel}</span>
              </>
            )}
          </button>
        </form>

        {/* Operator account creation link (existing signup flow) */}
        {mode === 'operator' && (
          <div style={{ textAlign: 'center', marginTop: '1.25rem', fontSize: '0.8rem', color: '#94a3b8' }}>
            Need a staff account?{' '}
            <span
              onClick={() => navigate('/signup')}
              style={{ color: '#38bdf8', fontWeight: 600, cursor: 'pointer', textDecoration: 'underline' }}
            >
              Create an Account
            </span>
          </div>
        )}

        {/* Local demo credentials */}
        <div
          style={{
            marginTop: '1.5rem',
            paddingTop: '1rem',
            borderTop: '1px solid rgba(255,255,255,0.06)',
            fontSize: '0.72rem',
            color: '#64748b',
            textAlign: 'center',
            lineHeight: 1.7,
          }}
        >
          {mode === 'operator' && (
            <>💡 Operator: <strong>admin</strong> / <strong>password123</strong></>
          )}
          {mode === 'member' && (
            <>💡 Campus member: <strong>student@vignan.ac.in</strong> / <strong>9000000000</strong></>
          )}
          {mode === 'department' && (
            <>💡 Department: <strong>{department.toLowerCase()}@vignan.ac.in</strong> / <strong>password123</strong></>
          )}
        </div>
      </div>
    </div>
  );
};
