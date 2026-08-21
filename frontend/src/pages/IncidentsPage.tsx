import React, { useState } from 'react';
import {
  AlertTriangle,
  PlusCircle,
  Clock,
  MapPin,
  HeartPulse,
  Filter,
  CheckCircle2,
  Radio,
  FileText,
  Sparkles,
  Bot,
  ShieldAlert,
  Activity,
  Truck,
  MessageSquare,
  Cpu,
  Layers,
  ListCheck,
  CheckCircle,
  XCircle,
  UserCheck,
  ShieldCheck,
  ClipboardList,
  Send,
  Megaphone,
  CheckCheck
} from 'lucide-react';

import {
  Incident,
  SeverityLevel,
  IncidentStatus,
  MultiAgentOrchestrationResponse,
  ResponsePlan,
  DispatchExecutionResult,
} from '../types';
import { api } from '../services/api';

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
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [orchestratingId, setOrchestratingId] = useState<string | null>(null);
  const [generatingPlanId, setGeneratingPlanId] = useState<string | null>(null);
  const [approvingPlanId, setApprovingPlanId] = useState<string | null>(null);
  const [dispatchingPlanId, setDispatchingPlanId] = useState<string | null>(null);
  const [resolvingIncidentId, setResolvingIncidentId] = useState<string | null>(null);
  const [orchestrationData, setOrchestrationData] = useState<Record<string, MultiAgentOrchestrationResponse>>({});
  const [responsePlans, setResponsePlans] = useState<Record<string, ResponsePlan>>({});
  const [dispatchResults, setDispatchResults] = useState<Record<string, DispatchExecutionResult>>({});
  const [operatorName, setOperatorName] = useState<string>('Campus Safety Commander');
  const [approvalNotes, setApprovalNotes] = useState<string>('');
  const [resolutionNotes, setResolutionNotes] = useState<string>('Emergency situation contained and neutralized. All safety perimeters stood down.');
  const [actionError, setActionError] = useState<string | null>(null);

  const handleAnalyze = async (incidentId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setAnalyzingId(incidentId);
    setActionError(null);
    try {
      const response = await api.analyzeIncident(incidentId);
      if (selectedIncident && selectedIncident.incident_id === incidentId) {
        setSelectedIncident(response.incident);
      }
      onRefresh();
    } catch (err: any) {
      setActionError(err.message || 'Analysis failed');
    } finally {
      setAnalyzingId(null);
    }
  };

  const handleOrchestrate = async (incidentId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setOrchestratingId(incidentId);
    setActionError(null);
    try {
      const response = await api.orchestrateIncident(incidentId);
      setOrchestrationData((prev) => ({ ...prev, [incidentId]: response }));
      if (selectedIncident && selectedIncident.incident_id === incidentId) {
        setSelectedIncident(response.incident);
      }
      onRefresh();
    } catch (err: any) {
      setActionError(err.message || 'Multi-Agent Orchestration failed');
    } finally {
      setOrchestratingId(null);
    }
  };

  const handleGeneratePlan = async (incidentId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setGeneratingPlanId(incidentId);
    setActionError(null);
    try {
      const plan = await api.generateResponsePlan(incidentId);
      setResponsePlans((prev) => ({ ...prev, [incidentId]: plan }));
      onRefresh();
      // Update selected incident if currently viewing
      const updatedIncident = incidents.find((i) => i.incident_id === incidentId);
      if (updatedIncident && selectedIncident?.incident_id === incidentId) {
        setSelectedIncident({ ...updatedIncident, status: 'awaiting_approval' as IncidentStatus });
      }
    } catch (err: any) {
      setActionError(err.message || 'Response plan generation failed');
    } finally {
      setGeneratingPlanId(null);
    }
  };

  const handleDecideApproval = async (planId: string, decision: 'approve' | 'reject', incidentId: string) => {
    setApprovingPlanId(planId);
    setActionError(null);
    try {
      const updatedPlan = await api.decideApproval(planId, {
        decision,
        operator_name: operatorName || 'Campus Safety Commander',
        notes: approvalNotes || (decision === 'approve' ? 'Approved for emergency execution.' : 'Rejected by safety commander.')
      });
      setResponsePlans((prev) => ({ ...prev, [incidentId]: updatedPlan }));
      onRefresh();
      if (selectedIncident?.incident_id === incidentId) {
        setSelectedIncident((prev) => prev ? { ...prev, status: decision === 'approve' ? 'approved' as IncidentStatus : 'rejected' as IncidentStatus } : null);
      }
    } catch (err: any) {
      setActionError(err.message || 'Approval decision failed');
    } finally {
      setApprovingPlanId(null);
    }
  };

  const handleExecuteDispatch = async (planId: string, incidentId: string) => {
    setDispatchingPlanId(planId);
    setActionError(null);
    try {
      const result = await api.executeDispatch(planId);
      setDispatchResults((prev) => ({ ...prev, [incidentId]: result }));
      onRefresh();
      if (selectedIncident?.incident_id === incidentId) {
        setSelectedIncident((prev) => prev ? { ...prev, status: 'in_progress' as IncidentStatus } : null);
      }
    } catch (err: any) {
      setActionError(err.message || 'Dispatch execution failed');
    } finally {
      setDispatchingPlanId(null);
    }
  };

  const handleResolveIncident = async (incidentId: string) => {
    setResolvingIncidentId(incidentId);
    setActionError(null);
    try {
      const resolved = await api.resolveIncident(incidentId, resolutionNotes, operatorName);
      if (selectedIncident?.incident_id === incidentId) {
        setSelectedIncident(resolved);
      }
      onRefresh();
    } catch (err: any) {
      setActionError(err.message || 'Incident resolution failed');
    } finally {
      setResolvingIncidentId(null);
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
        return <span className="status-pill status-analyzing">AI Analyzing</span>;
      case 'classified':
        return <span className="status-pill status-classified">Classified</span>;
      case 'response_planning':
        return <span className="status-pill status-planning">Response Planning</span>;
      case 'approved':
        return <span className="status-pill status-approved">Approved</span>;
      case 'resolved':
        return <span className="status-pill status-resolved">Resolved</span>;
      default:
        return <span className="status-pill">{status}</span>;
    }
  };

  return (
    <div className="app-content">
      {/* Title & Actions Bar */}
      <div className="dashboard-title-row">
        <div>
          <h2>Campus Emergency Incidents</h2>
          <p>Real-time intake stream, Supervisor classification, and LangGraph multi-agent orchestration.</p>
        </div>

        <div className="quick-actions-group">
          <button className="btn btn-outline" onClick={onRefresh} disabled={loading}>
            <Clock size={15} />
            <span>Refresh</span>
          </button>
          <button className="btn btn-danger" onClick={onOpenReportModal} style={{ backgroundColor: 'var(--danger-600)', color: '#ffffff' }}>
            <PlusCircle size={16} />
            <span>Report Emergency</span>
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="filter-card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)' }}>
          <Filter size={16} />
          <span style={{ fontSize: '0.8125rem', fontWeight: 600 }}>Filter Stream:</span>
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
            <option value="analyzing">Analyzing</option>
            <option value="classified">Classified</option>
            <option value="response_planning">Response Planning</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>

        <div style={{ marginLeft: 'auto', fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
          Showing <strong>{filteredIncidents.length}</strong> of {incidents.length} recorded incidents
        </div>
      </div>

      {/* Main Incidents Grid */}
      {filteredIncidents.length === 0 ? (
        <div className="panel-card" style={{ padding: '3.5rem 1.5rem', textAlign: 'center' }}>
          <AlertTriangle size={36} color="#94a3b8" style={{ margin: '0 auto 0.75rem' }} />
          <h3 style={{ color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
            No Incidents Found
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
            >
              <div className="incident-card-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span className="incident-id-tag">{incident.incident_id}</span>
                  <span className="incident-type-tag">{incident.incident_type.toUpperCase()}</span>
                </div>
                {getSeverityBadge(incident.severity)}
              </div>

              <div className="incident-card-body">
                <p className="incident-description">{incident.description}</p>

                {incident.summary && (
                  <div style={{ background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 'var(--radius-sm)', padding: '0.5rem 0.65rem', marginBottom: '0.75rem', fontSize: '0.8125rem', color: '#0369a1' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontWeight: 600, marginBottom: '0.15rem' }}>
                      <Sparkles size={13} color="#0284c7" />
                      <span>Supervisor Summary {incident.confidence ? `(${Math.round(incident.confidence * 100)}%)` : ''}</span>
                    </div>
                    {incident.summary}
                  </div>
                )}

                <div className="incident-meta-grid">
                  <div className="meta-item">
                    <MapPin size={14} color="#0284c7" />
                    <span>{incident.location}</span>
                  </div>

                  <div className="meta-item">
                    <HeartPulse size={14} color="#0d9488" />
                    <span>
                      Injured:{' '}
                      {incident.injured_count === null ? (
                        <strong style={{ color: '#0369a1' }}>Unknown (null)</strong>
                      ) : incident.injured_count === 0 ? (
                        <span style={{ color: '#16a34a' }}>0 (Confirmed none)</span>
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
                    <span>{incident.reported_by || 'Operator'}</span>
                  </div>
                </div>
              </div>

              <div className="incident-card-footer">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
                  {getStatusBadge(incident.status)}

                  {incident.status === 'reported' && (
                    <button
                      className="btn btn-sm btn-outline"
                      style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem', borderColor: '#38bdf8', color: '#0284c7' }}
                      disabled={analyzingId === incident.incident_id || orchestratingId === incident.incident_id}
                      onClick={(e) => handleAnalyze(incident.incident_id, e)}
                    >
                      <Sparkles size={12} />
                      <span>{analyzingId === incident.incident_id ? 'Analyzing...' : 'AI Analyze'}</span>
                    </button>
                  )}

                  <button
                    className="btn btn-sm btn-outline"
                    style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem', borderColor: '#0284c7', color: '#0284c7' }}
                    disabled={orchestratingId === incident.incident_id || analyzingId === incident.incident_id || generatingPlanId === incident.incident_id}
                    onClick={(e) => handleOrchestrate(incident.incident_id, e)}
                  >
                    <Cpu size={12} />
                    <span>{orchestratingId === incident.incident_id ? 'Orchestrating...' : 'Multi-Agent Graph'}</span>
                  </button>

                  <button
                    className="btn btn-sm"
                    style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem', background: '#0284c7', color: '#ffffff', border: 'none' }}
                    disabled={generatingPlanId === incident.incident_id || orchestratingId === incident.incident_id}
                    onClick={(e) => handleGeneratePlan(incident.incident_id, e)}
                  >
                    <ClipboardList size={12} />
                    <span>{generatingPlanId === incident.incident_id ? 'Planning...' : 'Response Plan'}</span>
                  </button>
                </div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Source: {incident.evidence_source || 'direct'}
                </span>
              </div>
            </div>
          ))}

        </div>
      )}

      {/* Incident Details Modal / Dossier */}
      {selectedIncident && (
        <div className="modal-backdrop" onClick={() => setSelectedIncident(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '780px' }}>
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <FileText size={20} color="#0284c7" />
                <div>
                  <h3 style={{ fontSize: '1.125rem' }}>Incident Dossier & Multi-Agent State: {selectedIncident.incident_id}</h3>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    Intake: {new Date(selectedIncident.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
              <button
                className="btn btn-outline"
                style={{ padding: '0.35rem', borderRadius: '50%' }}
                onClick={() => setSelectedIncident(null)}
              >
                ✕
              </button>
            </div>

            <div style={{ padding: '1.25rem', maxHeight: '75vh', overflowY: 'auto' }}>
              {actionError && (
                <div className="alert-banner" style={{ background: '#fef2f2', borderColor: '#fecaca', color: '#991b1b', marginBottom: '1rem' }}>
                  <AlertTriangle size={16} />
                  <span>{actionError}</span>
                </div>
              )}

              {/* Raw Intake Description */}
              <div style={{ marginBottom: '1rem' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Intake Description
                </div>
                <div style={{ fontSize: '0.9375rem', color: 'var(--text-primary)', marginTop: '0.25rem', lineHeight: 1.5, background: 'var(--bg-subtle)', padding: '0.75rem', borderRadius: 'var(--radius-md)' }}>
                  {selectedIncident.description}
                </div>
              </div>

              {/* Meta Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '0.6rem', marginBottom: '1rem' }}>
                <div className="meta-card">
                  <div className="meta-title">Location</div>
                  <div className="meta-value" style={{ fontSize: '0.8125rem' }}>{selectedIncident.location}</div>
                </div>

                <div className="meta-card">
                  <div className="meta-title">Severity</div>
                  <div className="meta-value">{getSeverityBadge(selectedIncident.severity)}</div>
                </div>

                <div className="meta-card">
                  <div className="meta-title">Casualties</div>
                  <div className="meta-value" style={{ fontSize: '0.8125rem' }}>
                    {selectedIncident.injured_count === null
                      ? 'Unknown (null)'
                      : `${selectedIncident.injured_count} confirmed`}
                  </div>
                </div>

                <div className="meta-card">
                  <div className="meta-title">Status</div>
                  <div className="meta-value">{getStatusBadge(selectedIncident.status)}</div>
                </div>
              </div>

              {/* Action Bar inside Dossier */}
              <div style={{ display: 'flex', gap: '0.6rem', marginBottom: '1rem' }}>
                <button
                  className="btn btn-primary"
                  style={{ flex: 1, padding: '0.5rem', fontSize: '0.8125rem' }}
                  disabled={orchestratingId === selectedIncident.incident_id}
                  onClick={() => handleOrchestrate(selectedIncident.incident_id)}
                >
                  <Cpu size={15} />
                  <span>{orchestratingId === selectedIncident.incident_id ? 'Executing LangGraph...' : 'Run LangGraph Multi-Agent Orchestration'}</span>
                </button>
              </div>

              {/* LangGraph Multi-Agent Orchestration Dossier */}
              {orchestrationData[selectedIncident.incident_id] ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {/* Supervisor Agent Node */}
                  <div style={{ background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: 'var(--radius-md)', padding: '0.85rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#0f172a', fontWeight: 600, fontSize: '0.875rem' }}>
                        <Bot size={17} color="#0284c7" />
                        <span>Supervisor Agent Node (Classification & Routing)</span>
                      </div>
                      {selectedIncident.confidence ? (
                        <span style={{ fontSize: '0.75rem', background: '#e0f2fe', color: '#0369a1', padding: '0.15rem 0.45rem', borderRadius: '999px', fontWeight: 600 }}>
                          {Math.round(selectedIncident.confidence * 100)}% Confidence
                        </span>
                      ) : null}
                    </div>
                    <p style={{ fontSize: '0.8125rem', color: 'var(--text-primary)', marginBottom: '0.4rem' }}>
                      {selectedIncident.summary}
                    </p>
                    <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      <span>Delegated Nodes:</span>
                      {orchestrationData[selectedIncident.incident_id].delegated_agents.map((ag) => (
                        <span key={ag} className="badge" style={{ background: '#e2e8f0', color: '#1e293b', textTransform: 'capitalize' }}>
                          {ag}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Security Agent Node */}
                  {orchestrationData[selectedIncident.incident_id].security_result && (
                    <div style={{ background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 'var(--radius-md)', padding: '0.85rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#0369a1', fontWeight: 600, fontSize: '0.875rem' }}>
                          <ShieldAlert size={17} color="#0284c7" />
                          <span>Security Agent Node</span>
                        </div>
                        <span className="badge badge-high" style={{ textTransform: 'uppercase', fontSize: '0.7rem' }}>
                          Threat: {orchestrationData[selectedIncident.incident_id].security_result?.threat_level}
                        </span>
                      </div>
                      <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.8125rem', color: '#0f172a' }}>
                        {orchestrationData[selectedIncident.incident_id].security_result?.actions.map((act, idx) => (
                          <li key={idx} style={{ marginBottom: '0.2rem' }}>{act}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Medical Agent Node */}
                  {orchestrationData[selectedIncident.incident_id].medical_result && (
                    <div style={{ background: '#f0fdfa', border: '1px solid #99f6e4', borderRadius: 'var(--radius-md)', padding: '0.85rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#0f766e', fontWeight: 600, fontSize: '0.875rem' }}>
                          <Activity size={17} color="#0d9488" />
                          <span>Medical Agent Node</span>
                        </div>
                        <span className="badge badge-teal" style={{ textTransform: 'uppercase', fontSize: '0.7rem' }}>
                          Triage: {orchestrationData[selectedIncident.incident_id].medical_result?.triage_priority}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#115e59', marginBottom: '0.4rem', fontWeight: 500 }}>
                        {orchestrationData[selectedIncident.incident_id].medical_result?.casualty_assessment}
                      </div>
                      <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.8125rem', color: '#0f172a' }}>
                        {orchestrationData[selectedIncident.incident_id].medical_result?.actions.map((act, idx) => (
                          <li key={idx} style={{ marginBottom: '0.2rem' }}>{act}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Transport Agent Node */}
                  {orchestrationData[selectedIncident.incident_id].transport_result && (
                    <div style={{ background: '#faf5ff', border: '1px solid #e9d5ff', borderRadius: 'var(--radius-md)', padding: '0.85rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#6b21a8', fontWeight: 600, fontSize: '0.875rem' }}>
                          <Truck size={17} color="#8b5cf6" />
                          <span>Transport Agent Node</span>
                        </div>
                        <span className="badge" style={{ background: '#f3e8ff', color: '#6b21a8', textTransform: 'uppercase', fontSize: '0.7rem' }}>
                          Route: {orchestrationData[selectedIncident.incident_id].transport_result?.route_status}
                        </span>
                      </div>
                      <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.8125rem', color: '#0f172a' }}>
                        {orchestrationData[selectedIncident.incident_id].transport_result?.actions.map((act, idx) => (
                          <li key={idx} style={{ marginBottom: '0.2rem' }}>{act}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Communication Agent Node */}
                  {orchestrationData[selectedIncident.incident_id].communication_result && (
                    <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 'var(--radius-md)', padding: '0.85rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#92400e', fontWeight: 600, fontSize: '0.875rem' }}>
                          <MessageSquare size={17} color="#f59e0b" />
                          <span>Communication Agent Node</span>
                        </div>
                        <span className="badge badge-medium" style={{ textTransform: 'uppercase', fontSize: '0.7rem' }}>
                          Priority: {orchestrationData[selectedIncident.incident_id].communication_result?.broadcast_priority}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#78350f', marginBottom: '0.25rem' }}>
                        Headline: {orchestrationData[selectedIncident.incident_id].communication_result?.alert_headline}
                      </div>
                      <div style={{ fontSize: '0.78125rem', background: '#ffffff', border: '1px solid #fef3c7', borderRadius: 'var(--radius-sm)', padding: '0.5rem', color: '#451a03', marginBottom: '0.4rem' }}>
                        "{orchestrationData[selectedIncident.incident_id].communication_result?.recommended_message}"
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#92400e' }}>
                        Channels: {orchestrationData[selectedIncident.incident_id].communication_result?.broadcast_channels.join(', ')}
                      </div>
                    </div>
                  )}

                  {/* Step 5 MCP Discovered Campus Resources Panel */}
                  {orchestrationData[selectedIncident.incident_id].mcp_resources && orchestrationData[selectedIncident.incident_id].mcp_resources.length > 0 && (
                    <div style={{ background: '#f8fafc', border: '1px solid #0284c7', borderRadius: 'var(--radius-md)', padding: '0.85rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#0369a1', fontWeight: 600, fontSize: '0.875rem' }}>
                          <Layers size={17} color="#0284c7" />
                          <span>MCP Verified Physical Campus Resources (SQLite Grounded)</span>
                        </div>
                        <span style={{ fontSize: '0.75rem', background: '#e0f2fe', color: '#0369a1', padding: '0.15rem 0.45rem', borderRadius: '999px', fontWeight: 600 }}>
                          {orchestrationData[selectedIncident.incident_id].mcp_resources.length} Verified Asset(s)
                        </span>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.5rem' }}>
                        {orchestrationData[selectedIncident.incident_id].mcp_resources.map((res) => (
                          <div key={res.resource_id} style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 'var(--radius-sm)', padding: '0.5rem 0.65rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                              <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#0f172a' }}>{res.resource_id}</span>
                              <span className="status-pill status-approved" style={{ fontSize: '0.65rem', padding: '0.1rem 0.35rem' }}>
                                {res.availability_status}
                              </span>
                            </div>
                            <div style={{ fontSize: '0.78125rem', fontWeight: 500, color: '#334155', marginBottom: '0.2rem' }}>
                              {res.name}
                            </div>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '0.1rem' }}>
                              <div>📍 {res.location}</div>
                              {res.contact && <div>📻 {res.contact}</div>}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Step 6 Response Planner & Human Approval Interface */}
                  {responsePlans[selectedIncident.incident_id] ? (
                    <div style={{ background: '#f8fafc', border: '2px solid #0284c7', borderRadius: 'var(--radius-md)', padding: '1rem', marginTop: '0.5rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem' }}>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#0369a1', fontWeight: 700, fontSize: '0.9375rem' }}>
                            <ShieldCheck size={18} color="#0284c7" />
                            <span>{responsePlans[selectedIncident.incident_id].title}</span>
                          </div>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            Plan ID: {responsePlans[selectedIncident.incident_id].plan_id}
                          </span>
                        </div>
                        <div>
                          {responsePlans[selectedIncident.incident_id].approval_status === 'approved' ? (
                            <span className="badge badge-approved" style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}>
                              ✅ APPROVED FOR DISPATCH
                            </span>
                          ) : responsePlans[selectedIncident.incident_id].approval_status === 'rejected' ? (
                            <span className="badge badge-rejected" style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}>
                              ❌ REJECTED BY COMMANDER
                            </span>
                          ) : (
                            <span className="badge badge-high" style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}>
                              ⏳ AWAITING HUMAN APPROVAL
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Recommended Response Actions */}
                      <div style={{ marginBottom: '0.75rem' }}>
                        <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.35rem' }}>
                          Recommended Action Sequence:
                        </div>
                        <ol style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.8125rem', color: '#0f172a', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                          {responsePlans[selectedIncident.incident_id].recommended_actions.map((act, idx) => (
                            <li key={idx} style={{ lineHeight: 1.4 }}>{act}</li>
                          ))}
                        </ol>
                      </div>

                      {/* Allocated Physical Resources */}
                      <div style={{ marginBottom: '0.75rem' }}>
                        <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.35rem' }}>
                          Allocated Verified Physical Resources:
                        </div>
                        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                          {responsePlans[selectedIncident.incident_id].allocated_resources.map((resId) => (
                            <span key={resId} style={{ background: '#e0f2fe', color: '#0369a1', padding: '0.15rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700 }}>
                              {resId}
                            </span>
                          ))}
                        </div>
                      </div>

                      {/* Human Approval Decision Workflow */}
                      {responsePlans[selectedIncident.incident_id].approval_status === 'pending' ? (
                        <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 'var(--radius-sm)', padding: '0.75rem', marginTop: '0.5rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#92400e', fontWeight: 600, fontSize: '0.8125rem', marginBottom: '0.4rem' }}>
                            <UserCheck size={16} />
                            <span>Human-In-The-Loop Safety Gate: Operator Authorization Required</span>
                          </div>
                          <p style={{ fontSize: '0.75rem', color: '#78350f', margin: '0 0 0.5rem' }}>
                            High-impact actions (emergency dispatch, lane lockdowns, sirens) cannot trigger automatically. Please confirm situational authorization.
                          </p>

                          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
                            <input
                              type="text"
                              className="form-input"
                              style={{ fontSize: '0.78125rem', padding: '0.35rem 0.5rem', flex: 1 }}
                              placeholder="Approving Operator / Commander Name"
                              value={operatorName}
                              onChange={(e) => setOperatorName(e.target.value)}
                            />
                            <input
                              type="text"
                              className="form-input"
                              style={{ fontSize: '0.78125rem', padding: '0.35rem 0.5rem', flex: 2 }}
                              placeholder="Operational notes / justification..."
                              value={approvalNotes}
                              onChange={(e) => setApprovalNotes(e.target.value)}
                            />
                          </div>

                          <div style={{ display: 'flex', gap: '0.5rem' }}>
                            <button
                              className="btn btn-sm"
                              style={{ background: '#16a34a', color: '#ffffff', border: 'none', padding: '0.35rem 0.75rem', fontWeight: 600 }}
                              disabled={approvingPlanId === responsePlans[selectedIncident.incident_id].plan_id}
                              onClick={() => handleDecideApproval(responsePlans[selectedIncident.incident_id].plan_id, 'approve', selectedIncident.incident_id)}
                            >
                              <CheckCircle size={14} />
                              <span>{approvingPlanId === responsePlans[selectedIncident.incident_id].plan_id ? 'Authorizing...' : 'Approve Response Plan'}</span>
                            </button>

                            <button
                              className="btn btn-sm btn-outline"
                              style={{ borderColor: '#dc2626', color: '#dc2626', padding: '0.35rem 0.75rem' }}
                              disabled={approvingPlanId === responsePlans[selectedIncident.incident_id].plan_id}
                              onClick={() => handleDecideApproval(responsePlans[selectedIncident.incident_id].plan_id, 'reject', selectedIncident.incident_id)}
                            >
                              <XCircle size={14} />
                              <span>Reject Plan</span>
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div style={{ background: responsePlans[selectedIncident.incident_id].approval_status === 'approved' ? '#f0fdf4' : '#fef2f2', border: `1px solid ${responsePlans[selectedIncident.incident_id].approval_status === 'approved' ? '#bbf7d0' : '#fecaca'}`, borderRadius: 'var(--radius-sm)', padding: '0.65rem', marginTop: '0.5rem', fontSize: '0.78125rem' }}>
                          <div style={{ fontWeight: 600, color: responsePlans[selectedIncident.incident_id].approval_status === 'approved' ? '#166534' : '#991b1b', marginBottom: '0.15rem' }}>
                            {responsePlans[selectedIncident.incident_id].approval_status === 'approved' ? '✓ Authorized By:' : '✗ Rejected By:'}{' '}
                            {responsePlans[selectedIncident.incident_id].approved_by || 'Operator'} on {new Date(responsePlans[selectedIncident.incident_id].updated_at).toLocaleString()}
                          </div>
                          <div style={{ color: 'var(--text-secondary)' }}>
                            Notes: {responsePlans[selectedIncident.incident_id].approval_notes || 'None provided.'}
                          </div>
                        </div>
                      )}

                      {/* Step 7 Dispatch Execution & Resolution Workflow (Unlocked upon Approval) */}
                      {responsePlans[selectedIncident.incident_id].approval_status === 'approved' && (
                        <div style={{ marginTop: '0.85rem', paddingTop: '0.85rem', borderTop: '1px dashed #cbd5e1' }}>
                          {!dispatchResults[selectedIncident.incident_id] && selectedIncident.status !== 'resolved' ? (
                            <div style={{ textAlign: 'center', padding: '0.5rem' }}>
                              <button
                                className="btn btn-danger"
                                style={{ backgroundColor: 'var(--danger-600)', color: '#ffffff', padding: '0.5rem 1.25rem', fontSize: '0.875rem', fontWeight: 600 }}
                                disabled={dispatchingPlanId === responsePlans[selectedIncident.incident_id].plan_id}
                                onClick={() => handleExecuteDispatch(responsePlans[selectedIncident.incident_id].plan_id, selectedIncident.incident_id)}
                              >
                                <Send size={15} />
                                <span>{dispatchingPlanId === responsePlans[selectedIncident.incident_id].plan_id ? 'Deploying Emergency Assets...' : '🚀 Step 7: Execute Dispatch & Multi-Channel Broadcast'}</span>
                              </button>
                            </div>
                          ) : selectedIncident.status === 'resolved' ? (
                            <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 'var(--radius-sm)', padding: '0.75rem', textAlign: 'center' }}>
                              <CheckCheck size={20} color="#16a34a" style={{ margin: '0 auto 0.25rem' }} />
                              <div style={{ fontWeight: 700, color: '#166534', fontSize: '0.875rem' }}>
                                EMERGENCY INCIDENT RESOLVED & CLOSED
                              </div>
                              <p style={{ fontSize: '0.78125rem', color: '#15803d', margin: '0.2rem 0 0' }}>
                                All dispatched emergency physical assets have been restored to available readiness in SQLite.
                              </p>
                            </div>
                          ) : (
                            <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 'var(--radius-sm)', padding: '0.75rem' }}>
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#1d4ed8', fontWeight: 700, fontSize: '0.875rem' }}>
                                  <Send size={16} />
                                  <span>Automated Dispatch Active & Simulated Broadcasts Sent</span>
                                </div>
                                <span className="status-pill status-planning" style={{ background: '#dbeafe', color: '#1d4ed8', fontSize: '0.7rem' }}>
                                  UNITS EN ROUTE
                                </span>
                              </div>

                              {/* Live Dispatched Units */}
                              <div style={{ marginBottom: '0.5rem' }}>
                                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#1e40af' }}>Dispatched Physical Units (Locked in SQLite as Busy):</span>
                                <div style={{ display: 'flex', gap: '0.35rem', marginTop: '0.2rem', flexWrap: 'wrap' }}>
                                  {dispatchResults[selectedIncident.incident_id].dispatched_resources.map((rid) => (
                                    <span key={rid} style={{ background: '#fee2e2', color: '#dc2626', border: '1px solid #fecaca', padding: '0.15rem 0.45rem', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700 }}>
                                      🚒 {rid} (BUSY / EN ROUTE)
                                    </span>
                                  ))}
                                </div>
                              </div>

                              {/* Multi-Channel Broadcast Streams */}
                              <div style={{ marginBottom: '0.75rem' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.75rem', fontWeight: 600, color: '#1e40af', marginBottom: '0.25rem' }}>
                                  <Megaphone size={14} />
                                  <span>Simulated Emergency Notification Streams (3 Channels):</span>
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                                  {dispatchResults[selectedIncident.incident_id].broadcast_alerts.map((b, idx) => (
                                    <div key={idx} style={{ background: '#ffffff', border: '1px solid #dbeafe', borderRadius: '4px', padding: '0.4rem 0.5rem', fontSize: '0.75rem' }}>
                                      <div style={{ display: 'flex', justifyContent: 'space-between', color: '#1e40af', fontWeight: 600 }}>
                                        <span>📡 {b.channel} → {b.recipient_group}</span>
                                        <span style={{ color: '#16a34a', textTransform: 'uppercase', fontSize: '0.65rem' }}>✓ {b.status}</span>
                                      </div>
                                      <div style={{ color: '#334155', marginTop: '0.1rem' }}>{b.message}</div>
                                    </div>
                                  ))}
                                </div>
                              </div>

                              {/* Incident Resolution Form */}
                              <div style={{ background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: 'var(--radius-sm)', padding: '0.65rem' }}>
                                <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#0f172a', marginBottom: '0.35rem' }}>
                                  Resolve Emergency & Release Resources:
                                </div>
                                <input
                                  type="text"
                                  className="form-input"
                                  style={{ fontSize: '0.78125rem', padding: '0.35rem 0.5rem', marginBottom: '0.4rem' }}
                                  value={resolutionNotes}
                                  onChange={(e) => setResolutionNotes(e.target.value)}
                                  placeholder="Post-incident resolution summary..."
                                />
                                <button
                                  className="btn btn-sm"
                                  style={{ background: '#16a34a', color: '#ffffff', border: 'none', padding: '0.35rem 0.75rem', fontWeight: 600 }}
                                  disabled={resolvingIncidentId === selectedIncident.incident_id}
                                  onClick={() => handleResolveIncident(selectedIncident.incident_id)}
                                >
                                  <CheckCheck size={14} />
                                  <span>{resolvingIncidentId === selectedIncident.incident_id ? 'Releasing Assets...' : 'Complete Resolution & Release Resources'}</span>
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{ textAlign: 'center', marginTop: '0.75rem' }}>
                      <button
                        className="btn"
                        style={{ background: '#0284c7', color: '#ffffff', padding: '0.45rem 1rem', fontSize: '0.8125rem' }}
                        disabled={generatingPlanId === selectedIncident.incident_id}
                        onClick={() => handleGeneratePlan(selectedIncident.incident_id)}
                      >
                        <ClipboardList size={15} />
                        <span>{generatingPlanId === selectedIncident.incident_id ? 'Generating Action Plan...' : 'Generate Step 6 Response Plan (Incident + Agents + MCP)'}</span>
                      </button>
                    </div>
                  )}

                  {/* LangGraph Audit Trail */}
                  <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 'var(--radius-md)', padding: '0.85rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 600, fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                      <ListCheck size={16} />
                      <span>LangGraph Execution Audit Log</span>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      {orchestrationData[selectedIncident.incident_id].audit_trail.map((log, i) => (
                        <div key={i} style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
                          {log}
                        </div>
                      ))}
                    </div>
                  </div>

                </div>
              ) : (
                /* Fallback if orchestration has not yet been executed for this incident */
                <div style={{ background: '#f8fafc', border: '1px dashed #cbd5e1', borderRadius: 'var(--radius-md)', padding: '1.25rem', textAlign: 'center' }}>
                  <Cpu size={24} color="#64748b" style={{ margin: '0 auto 0.5rem' }} />
                  <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
                    Multi-Agent Orchestration Ready
                  </div>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                    Click "Run LangGraph Multi-Agent Orchestration" to execute Supervisor, Security, Medical, Transport, and Communication agents and discover factual campus resources via MCP.
                  </p>
                </div>
              )}

              <div className="alert-banner" style={{ background: '#f0fdf4', borderColor: '#bbf7d0', color: '#166534', fontSize: '0.8125rem', marginTop: '1rem' }}>
                <CheckCircle2 size={16} />
                <span>Step 6 Response Planning & Human Approval active: Comprehensive audit trail preserved.</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};




