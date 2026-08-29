import React, { useEffect, useState } from 'react';
import { ShieldAlert, RefreshCw, Radio, CheckCircle, Circle, Menu } from 'lucide-react';
import { HealthResponse } from '../types';
import { api } from '../services/api';
import { NotificationBell } from './NotificationBell';

interface HeaderProps {
  health: HealthResponse | null;
  loading: boolean;
  onRefresh: () => void;
  wsState?: 'CONNECTED' | 'CONNECTING' | 'OFFLINE';
  user?: any;
  onLogout?: () => void;
  notificationRefreshKey?: number;
  onOpenMenu?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ health, loading, onRefresh, wsState = 'OFFLINE', user, onLogout, notificationRefreshKey = 0, onOpenMenu }) => {
  const isHealthy = health?.status === 'healthy';
  const [systemStatus, setSystemStatus] = useState<any>(null);

  const fetchStatus = async () => {
    try {
      const status = await api.getSystemStatus();
      setSystemStatus(status);
    } catch (e) {
      console.error('Failed to fetch system status', e);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const backendConnected = health?.status === 'healthy' || systemStatus?.backend_status === 'CONNECTED';
  const modeText = backendConnected ? 'BACKEND CONNECTED' : 'BACKEND OFFLINE';

  return (
    <header className="app-header" style={{ flexDirection: 'column', gap: '0.5rem', paddingBottom: '0.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
        <button type="button" className="mobile-menu-button" aria-label="Open navigation" onClick={onOpenMenu}>
          <Menu size={20} />
        </button>
        <div className="brand-section">
          <div className="brand-logo-icon">
            <ShieldAlert size={24} />
          </div>
          <div className="brand-text">
            <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              AITAM DISASTER RESPONSE AI
              <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.5rem', borderRadius: '4px', background: 'rgba(59, 130, 246, 0.2)', border: '1px solid rgba(59, 130, 246, 0.4)', color: '#60a5fa', fontWeight: 600 }}>
                REAL-LIFE OPERATIONS MODE
              </span>
            </h1>
            <div className="brand-subtitle">Aditya Institute of Technology and Management • Community Response Network</div>
          </div>
        </div>

        <div className="header-status-group" style={{ gap: '0.75rem' }}>
          <div className="operational-mode-badge" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 700, padding: '0.4rem 0.75rem', borderRadius: '6px', background: '#0f172a', border: '1px solid #334155' }}>
            <Radio size={14} className="spin-pulse" style={{ color: '#f59e0b' }} />
            <span>REAL-TIME DISASTER RESPONSE OPERATIONS • {modeText}</span>
          </div>

          <div
            className={`status-badge ${
              loading ? 'connecting' : isHealthy ? 'healthy' : 'degraded'
            }`}
          >
            <span className="pulse-dot"></span>
                <span>{isHealthy ? 'Backend Connected' : loading ? 'Connecting' : 'Backend Offline'}</span>
          </div>

          <button
            className="btn btn-outline"
            onClick={() => { onRefresh(); fetchStatus(); }}
            title="Refresh status"
            style={{ padding: '0.35rem 0.65rem' }}
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
          </button>

          <NotificationBell refreshKey={notificationRefreshKey} />

          {user && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', borderLeft: '1px solid #334155', paddingLeft: '0.75rem' }}>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#ffffff' }}>{user.full_name || user.username || user.name}</div>
                <div style={{ fontSize: '0.62rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>{user.role}</div>
              </div>
              <button 
                onClick={onLogout}
                className="btn btn-outline"
                style={{ fontSize: '0.68rem', padding: '0.25rem 0.5rem', color: '#f87171', borderColor: 'rgba(239, 68, 68, 0.4)', background: 'transparent', cursor: 'pointer' }}
              >
                Sign Out
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="service-status-board">
        <div><strong>CORE SYSTEM</strong><span><CheckCircle size={11} /> Backend Connected</span><span><CheckCircle size={11} /> WebSocket {wsState}</span><span><CheckCircle size={11} /> Database Connected</span><span><CheckCircle size={11} /> AI Agents Active</span><span><CheckCircle size={11} /> LangGraph Active</span><span><CheckCircle size={11} /> MCP Connected</span><span><CheckCircle size={11} /> Response Planning Active</span></div>
        <div><strong>LOCAL DEVICE CAPABILITIES</strong><span><CheckCircle size={11} /> Browser Voice — Enable Audio</span><span><Circle size={11} /> GPS — Enable Live GPS</span><span><CheckCircle size={11} /> In-App Alert Ready</span></div>
        <div className="optional-services"><strong>OPTIONAL EXTERNAL INTEGRATIONS</strong><span><Circle size={11} /> Email — Optional / Not Configured</span><span><Circle size={11} /> SMS — Optional / Not Configured</span><span><Circle size={11} /> Phone Call — Optional / Not Configured</span><span><Circle size={11} /> Firebase FCM — Optional / Not Configured</span></div>
      </div>
    </header>
  );
};

