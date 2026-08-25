import { ReactElement } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { AuthUser, homePathFor } from './roles';

// ---------------------------------------------------------------------------
// ProtectedRoute — the client-side route guard (Increment 2, requirement #6).
//
// Behavior:
//   * While the session is still being validated -> show a lightweight loader
//     (prevents a flash of the login page for an already-authenticated user).
//   * No authenticated user -> redirect to /login (remembering where they came
//     from). This is also what an expired token lands on (AuthContext clears the
//     user, which re-renders this guard).
//   * Authenticated but not permitted for this route (`allow` predicate fails)
//     -> redirect to the user's OWN home portal, never the forbidden one. e.g. a
//     Security user hitting /portal or a citizen hitting /command is bounced to
//     their own portal. Department cross-access is additionally checked in the
//     department route wrapper.
//
// This is defense-in-depth for navigation only — the backend independently
// scopes all incident data by the verified token (see backend/api/incidents.py).
// ---------------------------------------------------------------------------

export function FullScreenMessage({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div
      style={{
        minHeight: '70vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '0.75rem',
        color: '#94a3b8',
        fontFamily: 'Inter, sans-serif',
      }}
    >
      <div
        className="spin"
        style={{
          width: '34px',
          height: '34px',
          border: '3px solid #334155',
          borderTopColor: '#6366f1',
          borderRadius: '50%',
        }}
      />
      <div style={{ fontWeight: 700, color: '#e2e8f0' }}>{title}</div>
      {subtitle && <div style={{ fontSize: '0.8rem' }}>{subtitle}</div>}
    </div>
  );
}

interface ProtectedRouteProps {
  children: ReactElement;
  /** Optional predicate the authenticated user must satisfy for this route. */
  allow?: (user: AuthUser | null) => boolean;
}

export function ProtectedRoute({ children, allow }: ProtectedRouteProps) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <FullScreenMessage title="Verifying your session…" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (allow && !allow(user)) return <Navigate to={homePathFor(user)} replace />;
  return children;
}
