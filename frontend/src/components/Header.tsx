import React from 'react';
import { ShieldAlert, RefreshCw } from 'lucide-react';
import { HealthResponse } from '../types';

interface HeaderProps {
  health: HealthResponse | null;
  loading: boolean;
  onRefresh: () => void;
}

export const Header: React.FC<HeaderProps> = ({ health, loading, onRefresh }) => {
  const isHealthy = health?.status === 'healthy';
  const isDegraded = health?.status === 'degraded';

  return (
    <header className="app-header">
      <div className="brand-section">
        <div className="brand-logo-icon">
          <ShieldAlert size={24} />
        </div>
        <div className="brand-text">
          <h1>CAMPUSFLOW AI</h1>
          <div className="brand-subtitle">Emergency Intelligence Center</div>
        </div>
      </div>

      <div className="header-status-group">
        <div className="operational-mode-badge">
          OPERATIONAL READINESS: LEVEL 1 (STANDBY)
        </div>

        <div
          className={`status-badge ${
            loading
              ? 'connecting'
              : isHealthy
              ? 'healthy'
              : isDegraded
              ? 'degraded'
              : 'error'
          }`}
          title={
            health
              ? `Backend Service: ${health.service} (${health.environment})\nDatabase: ${health.database}\nSeeded Resources: ${health.seeded_resources}`
              : 'Connecting to CampusFlow Backend...'
          }
        >
          <span className="pulse-dot"></span>
          <span>
            {loading
              ? 'Connecting...'
              : isHealthy
              ? `System Online (DB: ${health?.database})`
              : isDegraded
              ? 'Degraded'
              : 'Backend Offline'}
          </span>
        </div>

        <button
          className="btn btn-outline"
          onClick={onRefresh}
          title="Refresh system status"
          style={{ padding: '0.35rem 0.65rem' }}
        >
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
        </button>
      </div>
    </header>
  );
};
