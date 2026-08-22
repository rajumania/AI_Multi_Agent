import React, { useState } from 'react';
import {
  AlertTriangle,
  PlusCircle,
  Clock,
  MapPin,
  HeartPulse,
  Filter,
  Radio,
  Sparkles,
  ClipboardList,
  ArrowRight,
  AlertCircle
} from 'lucide-react';

import {
  Incident,
  SeverityLevel,
  IncidentStatus,
} from '../types';
import { api } from '../services/api';
import { IncidentCommandView } from '../components/IncidentCommandView';

interface IncidentsPageProps {
  incidents: Incident[];
  loading: boolean;
  onOpenReportModal: () => void;
  onRefresh: () => void;
}

export const IncidentsPage: React.FC<IncidentsPageProps> = ({
  incidents,
  loading,
  onOpenReportModal,
  onRefresh
}) => {
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [loadingIncidentId, setLoadingIncidentId] = useState<string | null>(null);

  const handleAssessIncident = async (incidentId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setLoadingIncidentId(incidentId);
    setActionError(null);
    try {
      const response = await api.analyzeIncident(incidentId);
      onRefresh();
      setSelectedIncident(response.incident);
    } catch (err: any) {
      setActionError(err.message || 'Assessment failed');
    } finally {
      setLoadingIncidentId(null);
    }
  };

  const handlePlanIncident = async (incidentId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setLoadingIncidentId(incidentId);
    setActionError(null);
    try {
      await api.generateResponsePlan(incidentId);
      onRefresh();
      const updated = incidents.find((i) => i.incident_id === incidentId);
      if (updated) {
        setSelectedIncident(updated);
      }
    } catch (err: any) {
      setActionError(err.message || 'Plan preparation failed');
    } finally {
      setLoadingIncidentId(null);
    }
  };

  const filteredIncidents = incidents.filter((inc) => {
    if (severityFilter !== 'all' && inc.severity !== severityFilter) return false;
    if (statusFilter !== 'all' && inc.status !== statusFilter) return false;
    return true;
  });

  const getSeverityBadge = (severity: SeverityLevel) => {
    switch (severity) {
      case 'critical':
        return <span className="badge badge-critical">🚨 CRITICAL</span>;
      case 'high':
        return <span className="badge badge-high">⚠️ HIGH</span>;
      case 'medium':
        return <span className="badge badge-medium">⚡ MEDIUM</span>;
      case 'low':
        return <span className="badge badge-low">ℹ️ LOW</span>;
      default:
        return <span className="badge badge-unknown">UNKNOWN</span>;
    }
  };

  const getStatusBadge = (status: IncidentStatus) => {
    switch (status) {
      case 'reported':
        return <span className="status-pill status-reported">Reported</span>;
      case 'analyzing':
      case 'assessing':
        return <span className="status-pill status-analyzing">Assessing</span>;
      case 'classified':
        return <span className="status-pill status-classified">Assessed</span>;
      case 'response_planning':
      case 'planning':
        return <span className="status-pill status-planning">Planning</span>;
      case 'awaiting_approval':
        return <span className="status-pill status-planning" style={{ background: '#fef3c7', color: '#92400e', borderColor: '#fde68a' }}>Awaiting Approval</span>;
      case 'approved':
      case 'authorized':
        return <span className="status-pill status-approved">Authorized</span>;
      case 'in_progress':
      case 'response_in_progress':
      case 'dispatched':
        return <span className="status-pill" style={{ background: '#fee2e2', color: '#991b1b', borderColor: '#fecaca' }}>In Progress</span>;
      case 'monitoring':
        return <span className="status-pill" style={{ background: '#f0fdfa', color: '#0f766e', borderColor: '#99f6e4' }}>Monitoring</span>;
      case 'resolved':
        return <span className="status-pill status-resolved">Resolved</span>;
      case 'closed':
        return <span className="status-pill" style={{ background: '#f1f5f9', color: '#475569', borderColor: '#cbd5e1' }}>Closed</span>;
      default:
        return <span className="status-pill">{status}</span>;
    }
  };

  return (
    <div className="app-content">
      {/* Title & Actions Bar */}
      <div className="dashboard-title-row">
        <div>
          <h2>Campus Emergency Incidents & Command Queue</h2>
          <p>Real-time intake stream, operational assessment, commander authorization, and responder telemetry.</p>
        </div>

        <div className="quick-actions-group">
          <button className="btn btn-outline" onClick={onRefresh} disabled={loading}>
            <Clock size={15} />
            <span>Refresh Queue</span>
          </button>
          <button className="btn btn-danger" onClick={onOpenReportModal} style={{ backgroundColor: 'var(--danger-600)', color: '#ffffff' }}>
            <PlusCircle size={16} />
            <span>Report Emergency</span>
          </button>
        </div>
      </div>

      {actionError && (
        <div className="alert-banner" style={{ background: '#fef2f2', borderColor: '#fecaca', color: '#991b1b', marginBottom: '1rem' }}>
          <AlertTriangle size={16} />
          <span>{actionError}</span>
        </div>
      )}

      {/* Filter Bar */}
      <div className="filter-card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)' }}>
          <Filter size={16} />
          <span style={{ fontSize: '0.8125rem', fontWeight: 600 }}>Filter Queue:</span>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <select
            className="form-select-sm"
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>

          <select
            className="form-select-sm"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All Statuses</option>
            <option value="reported">Reported</option>
            <option value="classified">Assessed</option>
            <option value="awaiting_approval">Awaiting Approval</option>
            <option value="approved">Authorized</option>
            <option value="in_progress">In Progress</option>
            <option value="monitoring">Monitoring</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>
        </div>

        <div style={{ marginLeft: 'auto', fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
          Showing <strong>{filteredIncidents.length}</strong> of {incidents.length} incidents
        </div>
      </div>

      {/* Main Incidents Grid */}
      {filteredIncidents.length === 0 ? (
        <div className="panel-card" style={{ padding: '3.5rem 1.5rem', textAlign: 'center' }}>
          <AlertTriangle size={36} color="#94a3b8" style={{ margin: '0 auto 0.75rem' }} />
          <h3 style={{ color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
            No Emergency Incidents Found
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1.25rem' }}>
            {incidents.length === 0
              ? 'No campus emergency reports have been lodged yet. The intake pipeline is standing by.'
              : 'No incidents match the selected filter criteria.'}
          </p>
          <button className="btn btn-danger" onClick={onOpenReportModal} style={{ backgroundColor: 'var(--danger-600)', color: '#ffffff' }}>
            <PlusCircle size={15} />
            <span>Report First Incident</span>
          </button>
        </div>
      ) : (
        <div className="incidents-grid">
          {filteredIncidents.map((incident) => (
            <div
              key={incident.incident_id}
              className={`incident-card ${selectedIncident?.incident_id === incident.incident_id ? 'selected' : ''}`}
              onClick={() => setSelectedIncident(incident)}
              style={{ cursor: 'pointer' }}
            >
              <div className="incident-card-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span className="incident-id-tag">{incident.incident_id}</span>
                  <span className="incident-type-tag">{incident.incident_type.toUpperCase()}</span>
                </div>
                {getSeverityBadge(incident.severity)}
              </div>

              <div className="incident-card-body">
                <p className="incident-description" style={{ fontWeight: 600, color: '#0f172a' }}>
                  {incident.description}
                </p>

                {/* Location & Metadata */}
                <div className="incident-meta-grid" style={{ margin: '0.75rem 0' }}>
                  <div className="meta-item">
                    <MapPin size={14} color="#0284c7" />
                    <span><strong>{incident.location}</strong></span>
                  </div>

                  <div className="meta-item">
                    <HeartPulse size={14} color="#0d9488" />
                    <span>
                      Injured:{' '}
                      {incident.injured_count === null ? (
                        <strong style={{ color: '#0284c7' }}>Unknown</strong>
                      ) : incident.injured_count === 0 ? (
                        <span style={{ color: '#16a34a' }}>0 confirmed</span>
                      ) : (
                        <strong style={{ color: '#dc2626' }}>{incident.injured_count} injured</strong>
                      )}
                    </span>
                  </div>

                  <div className="meta-item">
                    <Clock size={14} color="#64748b" />
                    <span>{new Date(incident.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>

                  <div className="meta-item">
                    <Radio size={14} color="#64748b" />
                    <span>{incident.reported_by || 'Reporter'}</span>
                  </div>
                </div>

                {/* Next Action Box */}
                {incident.next_action && (
                  <div style={{
                    background: '#f8fafc',
                    border: '1px solid #e2e8f0',
                    borderRadius: '6px',
                    padding: '0.45rem 0.65rem',
                    fontSize: '0.75rem',
                    color: '#334155',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.35rem'
                  }}>
                    <AlertCircle size={13} color="#0284c7" />
                    <span><strong>Next:</strong> {incident.next_action}</span>
                  </div>
                )}
              </div>

              <div className="incident-card-footer" style={{ borderTop: '1px solid #e2e8f0', paddingTop: '0.65rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
                  {getStatusBadge(incident.status)}

                  {incident.status === 'reported' && (
                    <button
                      className="btn btn-sm btn-outline"
                      style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem', borderColor: '#38bdf8', color: '#0284c7' }}
                      disabled={loadingIncidentId === incident.incident_id}
                      onClick={(e) => handleAssessIncident(incident.incident_id, e)}
                    >
                      <Sparkles size={12} />
                      <span>{loadingIncidentId === incident.incident_id ? 'Assessing...' : 'Assess'}</span>
                    </button>
                  )}

                  {incident.status === 'classified' && (
                    <button
                      className="btn btn-sm btn-outline"
                      style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem', borderColor: '#0284c7', color: '#0284c7' }}
                      disabled={loadingIncidentId === incident.incident_id}
                      onClick={(e) => handlePlanIncident(incident.incident_id, e)}
                    >
                      <ClipboardList size={12} />
                      <span>{loadingIncidentId === incident.incident_id ? 'Planning...' : 'Plan Response'}</span>
                    </button>
                  )}

                  <button
                    className="btn btn-sm"
                    style={{ padding: '0.2rem 0.55rem', fontSize: '0.75rem', background: '#0284c7', color: '#ffffff', border: 'none', marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
                    onClick={() => setSelectedIncident(incident)}
                  >
                    <span>VIEW COMMAND</span>
                    <ArrowRight size={12} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Incident Command View Modal */}
      {selectedIncident && (
        <IncidentCommandView
          incident={selectedIncident}
          onClose={() => setSelectedIncident(null)}
          onRefresh={() => {
            onRefresh();
            // Re-fetch active incident details
            api.getIncidentById(selectedIncident.incident_id)
              .then((updated) => setSelectedIncident(updated))
              .catch(() => {});
          }}
        />
      )}
    </div>
  );
};
