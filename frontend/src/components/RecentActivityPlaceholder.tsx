import React, { useEffect, useState } from 'react';
import { History, Shield, Cpu, AlertTriangle, FileText, CheckCircle } from 'lucide-react';
import { api } from '../services/api';
import { AuditLog } from '../types';


export const RecentActivityPlaceholder: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchLogs = async () => {
    try {
      const data = await api.getActivityLogs(undefined, 10);
      setLogs(data);
    } catch (e) {
      console.error('Failed to fetch activity logs', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, []);

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
    <div className="panel-card" style={{ height: '100%' }}>
      <div className="panel-header">
        <div className="panel-title">
          <History size={18} color="#0d9488" />
          <span>Real-Time Audit & Activity Log (SQLite)</span>
        </div>
        <span className="panel-tag">Live Stream</span>
      </div>

      <div className="panel-body">
        {loading && logs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>
            Loading audit telemetry...
          </div>
        ) : logs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>
            No recent activity recorded yet. Report an incident to populate the audit trail.
          </div>
        ) : (
          <div className="timeline-list">
            {logs.map((item) => {
              const { icon: Icon, color } = getActionIcon(item.action_type);
              return (
                <div key={item.id} className="timeline-item">
                  <div className="timeline-icon-slot" style={{ color, backgroundColor: `${color}15` }}>
                    <Icon size={15} />
                  </div>
                  <div className="timeline-content">
                    <div className="timeline-title" style={{ textTransform: 'capitalize' }}>
                      {item.action_type.replace(/_/g, ' ')}
                    </div>
                    <div className="timeline-desc">{item.description}</div>
                    <div className="timeline-time">
                      {new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })} • Actor: <strong>{item.actor}</strong>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
