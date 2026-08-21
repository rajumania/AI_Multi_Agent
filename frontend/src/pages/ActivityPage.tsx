import React, { useEffect, useState } from 'react';
import { History, RefreshCw, Filter, Cpu, Shield, AlertTriangle, FileText, CheckCircle } from 'lucide-react';

import { AuditLog } from '../types';
import { api } from '../services/api';

export const ActivityPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionFilter, setActionFilter] = useState<string>('all');
  const [incidentFilter, setIncidentFilter] = useState<string>('');

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const data = await api.getActivityLogs(incidentFilter || undefined, 100);
      setLogs(data);
    } catch (e) {
      console.error('Failed to load audit logs', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [incidentFilter]);

  const filtered = logs.filter((l) => {
    if (actionFilter !== 'all' && l.action_type !== actionFilter) return false;
    return true;
  });

  const getActionIcon = (actionType: string) => {
    switch (actionType) {
      case 'incident_created':
        return { icon: AlertTriangle, color: '#dc2626' };
      case 'ai_classification':
        return { icon: Cpu, color: '#0284c7' };
      case 'agent_execution':
        return { icon: Shield, color: '#6366f1' };
      case 'response_plan_generated':
        return { icon: FileText, color: '#0d9488' };
      case 'approval_decision':
        return { icon: CheckCircle, color: '#16a34a' };
      default:
        return { icon: History, color: '#64748b' };
    }
  };

  return (
    <div className="app-content">
      <div className="dashboard-title-row">
        <div>
          <h2>System Audit & Compliance Activity Feed</h2>
          <p>Immutable event stream recording incident creation, AI analysis, MCP queries, human approvals, and automated dispatch.</p>
        </div>

        <div className="quick-actions-group">
          <button className="btn btn-outline" onClick={fetchLogs} disabled={loading}>
            <RefreshCw size={15} className={loading ? 'spin' : ''} />
            <span>Sync Audit Log</span>
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="filter-bar" style={{ marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>
            <Filter size={15} />
            <span>Filter Event:</span>
          </div>

          <select
            className="form-select-sm"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
          >
            <option value="all">All Action Types ({logs.length})</option>
            <option value="incident_created">Incident Lodged</option>
            <option value="ai_classification">AI Classification</option>
            <option value="agent_execution">Agent Execution</option>
            <option value="response_plan_generated">Response Plan Generated</option>
            <option value="approval_decision">Human Approval Decision</option>
            <option value="automation_execution">Automated Dispatch</option>
            <option value="incident_resolved">Incident Resolved</option>
          </select>

          <input
            type="text"
            className="form-input"
            style={{ width: '200px', padding: '0.35rem 0.6rem', fontSize: '0.8125rem' }}
            placeholder="Filter by Incident ID..."
            value={incidentFilter}
            onChange={(e) => setIncidentFilter(e.target.value)}
          />
        </div>

        <div style={{ marginLeft: 'auto', fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
          Showing <strong>{filtered.length}</strong> logged events
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
          Retrieving audit timeline from SQLite database...
        </div>
      ) : filtered.length === 0 ? (
        <div className="panel-card" style={{ padding: '3rem', textAlign: 'center' }}>
          <History size={32} color="#94a3b8" style={{ margin: '0 auto 0.5rem' }} />
          <h3>No Audit Records Found</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Actions taken in the system will automatically populate this audit trail.
          </p>
        </div>
      ) : (
        <div className="panel-card">
          <div className="panel-body" style={{ padding: '1.25rem' }}>
            <div className="timeline-list">
              {filtered.map((item) => {
                const { icon: Icon, color } = getActionIcon(item.action_type);
                return (
                  <div key={item.id} className="timeline-item">
                    <div className="timeline-icon-slot" style={{ color, backgroundColor: `${color}15` }}>
                      <Icon size={16} />
                    </div>
                    <div className="timeline-content">
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.15rem' }}>
                        <strong style={{ fontSize: '0.875rem', color: 'var(--text-primary)', textTransform: 'capitalize' }}>
                          {item.action_type.replace(/_/g, ' ')}
                        </strong>
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                          {new Date(item.timestamp).toLocaleString()}
                        </span>
                      </div>
                      <div className="timeline-desc" style={{ fontSize: '0.8125rem', color: '#334155', marginBottom: '0.25rem' }}>
                        {item.description}
                      </div>
                      <div style={{ fontSize: '0.71875rem', color: 'var(--text-muted)' }}>
                        Actor: <strong style={{ color: '#0284c7' }}>{item.actor}</strong>
                        {item.incident_id && <span> • Incident: <strong>{item.incident_id}</strong></span>}
                        {item.plan_id && <span> • Plan: <strong>{item.plan_id}</strong></span>}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
