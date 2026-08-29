import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, LogOut } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { displayName, roleDisplayName, departmentLabel } from '../auth/roles';
import { NotificationBell } from './NotificationBell';

// ---------------------------------------------------------------------------
// PortalHeader — identity indicator for the citizen & department portals.
//
// Intentionally minimal: it shows the AITAM brand, the required identity
// indicator (Name, Role, Department) and a Logout button — and NOTHING about
// internal system state (no AI-agents / LangGraph / MCP service board that the
// operator Header shows). This keeps internal reasoning out of citizen/dept view.
// ---------------------------------------------------------------------------

interface PortalHeaderProps {
  /** Short portal name shown next to the brand, e.g. "Community Portal". */
  subtitle: string;
  /** Accent color for the portal badge. */
  accent?: string;
  /** Optional badge text (e.g. the department label). */
  badge?: string;
  /** Incremented by the portal's existing event socket when notifications arrive. */
  notificationRefreshKey?: number;
}

export const PortalHeader: React.FC<PortalHeaderProps> = ({ subtitle, accent = '#6366f1', badge, notificationRefreshKey = 0 }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const dept = departmentLabel(user?.department);

  return (
    <header
      className="portal-header"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0.9rem 1.5rem',
        background: 'rgba(15, 23, 42, 0.95)',
        borderBottom: '1px solid #1e293b',
        color: '#e2e8f0',
        fontFamily: 'Inter, sans-serif',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <div
          style={{
            display: 'inline-flex',
            background: `linear-gradient(135deg, ${accent} 0%, #0ea5e9 100%)`,
            padding: '0.5rem',
            borderRadius: '10px',
          }}
        >
          <Shield size={20} color="#ffffff" />
        </div>
        <div>
          <div style={{ fontSize: '0.95rem', fontWeight: 800, letterSpacing: '-0.02em', lineHeight: 1.1 }}>
            AITAM DISASTER RESPONSE AI
          </div>
          <div style={{ fontSize: '0.72rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span>{subtitle}</span>
            {badge && (
              <span
                style={{
                  fontSize: '0.62rem',
                  fontWeight: 700,
                  padding: '0.1rem 0.45rem',
                  borderRadius: '999px',
                  background: 'rgba(99, 102, 241, 0.18)',
                  border: '1px solid rgba(99, 102, 241, 0.4)',
                  color: '#a5b4fc',
                  textTransform: 'uppercase',
                }}
              >
                {badge}
              </span>
            )}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
        <NotificationBell refreshKey={notificationRefreshKey} />
        <div style={{ textAlign: 'right', lineHeight: 1.25 }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#ffffff' }}>{displayName(user)}</div>
          <div style={{ fontSize: '0.62rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>
            {roleDisplayName(user)}
            {dept ? ` • ${dept}` : ''}
          </div>
        </div>
        <button
          onClick={handleLogout}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem',
            fontSize: '0.72rem',
            fontWeight: 600,
            padding: '0.4rem 0.7rem',
            color: '#f87171',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            background: 'transparent',
            borderRadius: '6px',
            cursor: 'pointer',
          }}
        >
          <LogOut size={14} />
          <span>Sign Out</span>
        </button>
      </div>
    </header>
  );
};
