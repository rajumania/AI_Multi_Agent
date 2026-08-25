import React, { useState, useEffect, useRef } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
  Clock3,
  ShieldCheck,
  Send,
  XCircle,
  ShieldAlert,
  CheckCheck,
  RefreshCw,
  Lock,
  Download,
  RotateCcw
} from 'lucide-react';
import {
  Incident,
  SeverityLevel,
  IncidentStatus,
  ResponsePlan,
  DepartmentAssignment,
  LiveEvent,
} from '../types';
import { api } from '../services/api';
import { AIDecisionTrace } from './AIDecisionTrace';
import { ExplainabilityCard } from './ExplainabilityCard';
import { CampusMap } from './CampusMap';

interface IncidentCommandViewProps {
  incident: Incident;
  onClose: () => void;
  onRefresh: () => void;
  liveEvents: LiveEvent[];
}

export const IncidentCommandView: React.FC<IncidentCommandViewProps> = ({
  incident,
  onClose,
  onRefresh,
  liveEvents,
}) => {
  const [viewRole, setViewRole] = useState<'operator' | 'student'>('operator');
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [operatorName, setOperatorName] = useState<string>('Campus Safety Commander');
  const [approvalNotes, setApprovalNotes] = useState<string>('Approved for emergency deployment.');
  const [resolutionNotes, setResolutionNotes] = useState<string>('Response team confirmed the situation is fully under control.');
  const [closingNotes, setClosingNotes] = useState<string>('Incident administratively closed and verified safe.');

  // Live data states
  const [responsePlan, setResponsePlan] = useState<ResponsePlan | null>(null);
  const [activityLogs, setActivityLogs] = useState<any[]>([]);
  const [allResources, setAllResources] = useState<any[]>([]);
  const [decisionTrace, setDecisionTrace] = useState<any[]>([]);
  const [assignments, setAssignments] = useState<DepartmentAssignment[]>([]);
  const [loadingData, setLoadingData] = useState<boolean>(true);

  // WebSocket live tracking states
  const [selectedResourceId, setSelectedResourceId] = useState<string | undefined>(undefined);
  const [liveTelemetry, setLiveTelemetry] = useState<any>(null);
  const lastHandledEvent = useRef<string | null>(null);

  useEffect(() => {
    if (responsePlan && responsePlan.allocated_resources && responsePlan.allocated_resources.length > 0) {
      let allocated: string[] = [];
      try {
        allocated = typeof responsePlan.allocated_resources === 'string'
          ? JSON.parse(responsePlan.allocated_resources)
          : responsePlan.allocated_resources;
      } catch (e) {
        allocated = responsePlan.allocated_resources as any;
      }
      if (allocated && allocated.length > 0) {
        setSelectedResourceId(allocated[0]);
      }
    }
  }, [responsePlan]);

  const fetchIncidentDetails = async () => {
    setLoadingData(true);
    try {
      const [plans, logs, resources, traceRes, assignmentsRes] = await Promise.all([
        api.getResponsePlans(incident.incident_id).catch(() => []),
        api.getActivityLogs(incident.incident_id).catch(() => []),
        api.getResources().catch(() => []),
        api.getDecisionTrace(incident.incident_id).catch(() => ({ trace: [] })),
        api.getIncidentAssignments(incident.incident_id).catch(() => [])
      ]);
      setDecisionTrace(traceRes?.trace || []);

      if (plans && plans.length > 0) {
        setResponsePlan(plans[0]);
      }
      setActivityLogs(logs);
      setAllResources(resources);
      setAssignments(assignmentsRes);
    } catch (e: any) {
      console.error('Failed to load incident detail data', e);
    } finally {
      setLoadingData(false);
    }
  };

  useEffect(() => {
    fetchIncidentDetails();
  }, [incident.incident_id]);

  // IncidentCommandView consumes the App-owned event stream. This keeps the
  // command center on one authenticated WebSocket while assignment state is
  // re-read from the backend after each real department event.
  useEffect(() => {
    // Assignment events must be correlated to this exact incident. A prior
    // implementation treated an unrelated/system event without incident_id
    // as a match; because the timeline is newest-first, that could prevent a
    // later department event from refreshing the command-center snapshot.
    const event = liveEvents.find((item) => item.incident_id === incident.incident_id);
    if (!event) return;
    const eventKey = `${event.event_name}:${event.timestamp}:${event.assignment_id || ''}:${event.department || ''}:${event.status || ''}`;
    if (lastHandledEvent.current === eventKey) return;
    lastHandledEvent.current = eventKey;
    if (['vehicle_location_updated', 'transport_location_updated', 'transport_eta_updated'].includes(event.event_name)) setLiveTelemetry(event);
    if (['vehicle_arrived', 'transport_arrived'].includes(event.event_name)) setLiveTelemetry(null);
    if (event.event_name === 'trace_updated' && event.entry) {
      setDecisionTrace((previous) => previous.some((entry) => entry.timestamp === event.entry.timestamp && entry.agent === event.entry.agent && entry.action === event.entry.action) ? previous : [...previous, event.entry]);
    }
    if (['assessment_started', 'incident_assessed', 'assessment_failed', 'incident_updated', 'response_plan_updated', 'response_plan_generated', 'awaiting_human_authorization', 'route_blocked', 'route_recalculated', 'approval_granted', 'approval_approved', 'approval_rejected', 'resource_dispatched', 'response_status_changed', 'replan_completed', 'incident_resolved', 'department_notified', 'dept_assignment_accepted', 'dept_assignment_declined', 'dept_team_assigned', 'dept_en_route', 'dept_on_scene', 'dept_assignment_completed'].includes(event.event_name)) {
      void fetchIncidentDetails();
    }
  }, [incident.incident_id, incident.status, liveEvents]);

  // Operational Action Handlers
  const handleSimulateBlockage = async () => {
    setLoadingAction('block_road');
    setActionError(null);
    setActionSuccess(null);
    try {
      let nodeA = 'library';
      let nodeB = 'admin_roundabout';
      
      const loc = incident.location.toLowerCase();
      if (loc.includes('hostel') || loc.includes('mahalakshmi')) {
        nodeA = 'admin_roundabout';
        nodeB = 'hostel_junc';
      } else if (loc.includes('gate') || loc.includes('entrance')) {
        nodeA = 'depot_junc';
        nodeB = 'gate';
      } else {
        nodeA = 'library';
        nodeB = 'admin_roundabout';
      }

      await api.blockRoad(nodeA, nodeB, true);
      setActionSuccess(`⚠️ Simulated road block injected between ${nodeA} and ${nodeB}. Detour calculated!`);
      fetchIncidentDetails();
    } catch (e: any) {
      setActionError(e.message || 'Block road simulation failed');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleReplan = async () => {
    setLoadingAction('replan');
    setActionError(null);
    try {
      const plan = await api.generateResponsePlan(incident.incident_id);
      setResponsePlan(plan);
      setActionSuccess('Dynamic re-planning complete: Resources and tactical actions re-evaluated.');
      onRefresh();
      fetchIncidentDetails();
    } catch (e: any) {
      setActionError(e.message || 'Re-planning failed');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleExportBriefing = () => {
    const briefingText = `=====================================================
CAMPUSFLOW AI — VIGNAN UNIVERSITY EMERGENCY BRIEFING
Incident ID: ${incident.incident_id}
Generated At: ${new Date().toLocaleString()}
Campus: Vignan University (Vadlamudi, Guntur)
=====================================================

1. INCIDENT SUMMARY:
- Emergency Type: ${(incident.incident_type || 'unknown').toUpperCase()}
- Severity: ${(incident.severity || 'unknown').toUpperCase()}
- Campus Location: ${incident.location}
- Casualties / Injured: ${incident.injured_count === null ? 'Unknown (Unconfirmed)' : incident.injured_count}
- Reported By: ${incident.reported_by || 'Campus Member'}
- Reported Time: ${new Date(incident.created_at).toLocaleString()}
- Current Status: ${(incident.status || 'unknown').toUpperCase()}

2. INTAKE DESCRIPTION:
"${incident.description}"

3. RECOMMENDED ACTIONS:
${responsePlan ? responsePlan.recommended_actions.map((a, i) => `${i + 1}. ${a}`).join('\n') : 'Plan Formulation in Progress'}

4. ALLOCATED EMERGENCY UNITS:
${responsePlan ? responsePlan.allocated_resources.join(', ') : 'None assigned'}

5. COMMANDER AUTHORIZATION:
- Approval Status: ${responsePlan?.approval_status ? responsePlan.approval_status.toUpperCase() : 'PENDING'}
- Authorized By: ${responsePlan?.approved_by || operatorName}

6. RESOLUTION & CLOSURE:
- Resolution Notes: ${incident.resolution_note || 'Situation under active containment'}
=====================================================`;

    const blob = new Blob([briefingText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `Vignan_Emergency_Briefing_${incident.incident_id}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleDecideApproval = async (decision: 'approve' | 'reject') => {
    if (!responsePlan) return;
    setLoadingAction('approval');
    setActionError(null);
    try {
      const updatedPlan = await api.decideApproval(responsePlan.plan_id, {
        decision,
        operator_name: operatorName || 'Campus Safety Commander',
        notes: approvalNotes
      });
      setResponsePlan(updatedPlan);
      setActionSuccess(decision === 'approve' ? 'Response plan authorized for execution.' : 'Response plan rejected.');
      onRefresh();
      fetchIncidentDetails();
    } catch (e: any) {
      setActionError(e.message || 'Approval action failed');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleInitiateDispatch = async () => {
    if (!responsePlan) return;
    setLoadingAction('dispatch');
    setActionError(null);
    try {
      await api.executeDispatch(responsePlan.plan_id);
      setActionSuccess('Emergency response initiated. Response teams dispatched and the in-app alert is active. Optional provider results remain explicitly labeled.');
      onRefresh();
      fetchIncidentDetails();
    } catch (e: any) {
      setActionError(e.message || 'Dispatch execution failed');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleConfirmResponse = async () => {
    setLoadingAction('confirm_response');
    setActionError(null);
    try {
      await api.confirmResponse(incident.incident_id, 'First responders confirmed arrival on-scene and active handling underway.', operatorName);
      setActionSuccess('Response team arrival confirmed. Shifted to active monitoring.');
      onRefresh();
      fetchIncidentDetails();
    } catch (e: any) {
      setActionError(e.message || 'Confirmation failed');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleResolveIncident = async () => {
    setLoadingAction('resolve');
    setActionError(null);
    try {
      await api.resolveIncident(incident.incident_id, resolutionNotes, operatorName);
      setActionSuccess('Incident confirmed under control and marked RESOLVED.');
      onRefresh();
      fetchIncidentDetails();
    } catch (e: any) {
      setActionError(e.message || 'Resolution failed');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleCloseIncident = async () => {
    setLoadingAction('close');
    setActionError(null);
    try {
      await api.closeIncident(incident.incident_id, closingNotes, operatorName);
      setActionSuccess('Incident record administratively closed.');
      onRefresh();
      fetchIncidentDetails();
    } catch (e: any) {
      setActionError(e.message || 'Close action failed');
    } finally {
      setLoadingAction(null);
    }
  };

  // Helper functions for status & severity
  const getSeverityBadge = (severity: SeverityLevel) => {
    switch (severity) {
      case 'critical':
        return <span className="badge badge-critical">🚨 CRITICAL</span>;
      case 'high':
        return <span className="badge badge-high">⚠️ HIGH SEVERITY</span>;
      case 'medium':
        return <span className="badge badge-medium">⚡ MEDIUM SEVERITY</span>;
      case 'low':
        return <span className="badge badge-low">ℹ️ LOW SEVERITY</span>;
      default:
        return <span className="badge badge-unknown">UNKNOWN SEVERITY</span>;
    }
  };

  const getStatusDisplay = (status: IncidentStatus) => {
    switch (status) {
      case 'reported':
        return { label: 'REPORTED', class: 'status-reported', color: '#64748b' };
      case 'analyzing':
      case 'assessing':
        return { label: 'UNDER ASSESSMENT', class: 'status-analyzing', color: '#0284c7' };
      case 'classified':
        return { label: 'ASSESSED', class: 'status-classified', color: '#0284c7' };
      case 'response_planning':
      case 'planning':
        return { label: 'RESPONSE PLANNING', class: 'status-planning', color: '#8b5cf6' };
      case 'awaiting_approval':
        return { label: 'AWAITING AUTHORIZATION', class: 'status-planning', color: '#f59e0b' };
      case 'approved':
      case 'authorized':
        return { label: 'RESPONSE AUTHORIZED', class: 'status-approved', color: '#10b981' };
      case 'in_progress':
      case 'response_in_progress':
      case 'dispatched':
        return { label: 'RESPONSE IN PROGRESS', class: 'status-analyzing', color: '#dc2626' };
      case 'monitoring':
        return { label: 'MONITORING SITUATION', class: 'status-analyzing', color: '#0d9488' };
      case 'resolved':
        return { label: 'RESOLVED', class: 'status-resolved', color: '#16a34a' };
      case 'closed':
        return { label: 'CLOSED', class: 'status-resolved', color: '#475569' };
      case 'rejected':
        return { label: 'PLAN REJECTED', class: 'status-reported', color: '#dc2626' };
      default:
        return { label: String(status).toUpperCase(), class: 'status-reported', color: '#64748b' };
    }
  };

  const getCurrentMilestoneIndex = (status: IncidentStatus): number => {
    if (status === 'reported' || status === 'analyzing') return 0;
    if (status === 'classified' || status === 'assessing') return 1;
    if (status === 'response_planning' || status === 'planning') return 2;
    if (status === 'awaiting_approval') return 3;
    if (status === 'approved' || status === 'authorized') return 4;
    if (status === 'in_progress' || status === 'response_in_progress' || status === 'dispatched') return 5;
    if (status === 'monitoring') return 6;
    if (status === 'resolved') return 7;
    if (status === 'closed') return 8;
    if (status === 'rejected') return 3;
    return 0;
  };

  const currentIndex = getCurrentMilestoneIndex(incident.status);

  const milestones = [
    { title: 'Report Received', desc: 'Emergency report logged in system' },
    { title: 'Incident Assessed', desc: 'Category and severity evaluated' },
    { title: 'Response Planned', desc: 'Resource check & plan prepared' },
    { title: 'Authorization', desc: 'Commander review & approval' },
    { title: 'Authorized', desc: 'Response approved for deployment' },
    { title: 'Response in Progress', desc: 'Teams deployed & in-app alert active' },
    { title: 'Monitoring', desc: 'On-scene response confirmed' },
    { title: 'Incident Resolved', desc: 'Situation confirmed under control' },
    { title: 'Incident Closed', desc: 'Record administratively finalized' }
  ];

  // Dynamic "What is Happening Now?" Text
  const getWhatIsHappeningNow = () => {
    if (incident.status === 'reported') {
      return `Emergency intake report received for ${incident.location}. The system is preparing to assess the classification and severity.`;
    }
    if (incident.status === 'analyzing' || incident.status === 'assessing') {
      return `The incident description is being assessed to identify the emergency type, severity level, and potential casualty impact.`;
    }
    if (incident.status === 'classified') {
      return `The incident has been classified as a ${(incident.severity || 'unknown').toUpperCase()} severity ${(incident.incident_type || 'unknown').toUpperCase()} emergency at ${incident.location}. Response resources are ready to be verified.`;
    }
    if (incident.status === 'response_planning' || incident.status === 'planning') {
      return `Available campus response resources (security, medical, transport, and facilities) have been evaluated. An action plan is ready for commander review.`;
    }
    if (incident.status === 'awaiting_approval') {
      return `A recommended response plan has been formulated. An authorized campus safety commander must review and approve the deployment.`;
    }
    if (incident.status === 'approved' || incident.status === 'authorized') {
      return `Response plan has been authorized by the safety commander. Ready to initiate physical team dispatch and campus broadcast alerts.`;
    }
    if (incident.status === 'in_progress' || incident.status === 'response_in_progress' || incident.status === 'dispatched') {
      return `Emergency response is actively in progress. Dispatched units are responding to ${incident.location}; the browser voice and in-app alert are active.`;
    }
    if (incident.status === 'monitoring') {
      return `Response teams have arrived on-scene at ${incident.location} and confirmed active containment. Responders are working to bring the situation fully under control.`;
    }
    if (incident.status === 'resolved') {
      return `The emergency at ${incident.location} has been confirmed under control and resolved. Allocated physical assets have been returned to the available campus pool.`;
    }
    if (incident.status === 'closed') {
      return `This incident record has been administratively closed and archived in the university safety registry.`;
    }
    if (incident.status === 'rejected') {
      return `The proposed response plan was rejected by the safety commander. Re-planning or manual tactical intervention is required.`;
    }
    return incident.current_step || 'Emergency operations are underway.';
  };

  // Dynamic "What Happens Next?" Text
  const getWhatHappensNext = () => {
    if (incident.status === 'reported') {
      return 'Run the intake assessment to determine emergency classification and severity.';
    }
    if (incident.status === 'classified') {
      return 'Verify campus resource availability and prepare a structured response plan.';
    }
    if (incident.status === 'response_planning' || incident.status === 'awaiting_approval') {
      return 'An authorized safety commander must review and approve the recommended emergency response.';
    }
    if (incident.status === 'approved') {
      return 'Initiate the response workflow to dispatch physical units and notify affected campus zones.';
    }
    if (incident.status === 'in_progress' || incident.status === 'dispatched') {
      return 'First responders arrive on-scene and confirm initial containment.';
    }
    if (incident.status === 'monitoring') {
      return 'Maintain on-scene operations until the situation is confirmed under control, then resolve the incident.';
    }
    if (incident.status === 'resolved') {
      return 'An authorized operator can review the resolution notes and close the incident record.';
    }
    if (incident.status === 'closed') {
      return 'Incident lifecycle is complete. No further action required.';
    }
    return incident.next_action || 'Follow commander instructions.';
  };

  // Safety Guidance Generator
  const getSafetyGuidance = () => {
    switch (incident.incident_type) {
      case 'fire':
        return {
          title: '🔥 Campus Fire Safety Guidance',
          steps: [
            'Evacuate the building immediately using the nearest marked stairwells. Do NOT use elevators.',
            'Move to designated open assembly muster points (NTR Convocation Grounds or Quadrangle).',
            'Keep roads and building entrances clear for emergency fire and medical vehicles.',
            'Do not re-enter the facility until all-clear is confirmed by campus safety authorities.'
          ]
        };
      case 'medical':
        return {
          title: '🏥 Medical Emergency Protocol',
          steps: [
            'Keep the affected person calm and still. Do not move injured individuals unless in immediate physical danger.',
            'Clear the surrounding corridor to allow fast stretcher and paramedic access.',
            'Campus Health Centre primary ambulance dispatched with trained first-responders.'
          ]
        };
      case 'security':
        return {
          title: '🛡️ Security & Lockdown Protocol',
          steps: [
            'Follow steward guidance and move away from the reported incident sector.',
            'Secure exterior doors if in an adjacent classroom or lab.',
            'Carry student/staff identification and report suspicious activity to Security Alpha.'
          ]
        };
      default:
        return {
          title: '⚠️ General Campus Emergency Guidance',
          steps: [
            'Remain calm and stay clear of the affected incident zone.',
            'Follow the browser voice and in-app alert. SMS and other external channels are optional integrations.',
            'Report any secondary hazards or trapped individuals immediately.'
          ]
        };
    }
  };

  const safetyInfo = getSafetyGuidance();
  const currentStatusObj = getStatusDisplay(incident.status);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-card incident-command-modal"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '980px', width: '95vw', maxHeight: '92vh', display: 'flex', flexDirection: 'column' }}
      >
        {/* Top Command Bar */}
        <div className="modal-header" style={{ borderBottom: '1px solid #e2e8f0', padding: '1rem 1.25rem', background: '#f8fafc' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div className="incident-lifecycle-grid" style={{
              background: '#0284c7',
              color: '#ffffff',
              padding: '0.45rem',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <ShieldAlert size={22} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                <h3 style={{ fontSize: '1.2rem', margin: 0, color: '#0f172a', fontWeight: 700 }}>
                  Incident Command: {incident.incident_id}
                </h3>
                <span className="badge" style={{ background: currentStatusObj.color, color: '#ffffff', fontWeight: 700, fontSize: '0.75rem' }}>
                  {currentStatusObj.label}
                </span>
                {getSeverityBadge(incident.severity)}
              </div>
              <div style={{ fontSize: '0.78125rem', color: '#64748b', marginTop: '0.15rem' }}>
                📍 {incident.location} • Reported {new Date(incident.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} • Vignan University (Vadlamudi)
              </div>
              <div style={{ fontSize: '0.72rem', marginTop: '0.35rem', color: incident.ai_provider_status === 'FALLBACK_ACTIVE' ? '#b45309' : '#0369a1', fontWeight: 700 }}>
                AI PROVIDER: {incident.ai_provider_status || 'PENDING'}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            {/* View Mode Toggle */}
            <div style={{
              display: 'flex',
              background: '#e2e8f0',
              padding: '2px',
              borderRadius: '6px',
              fontSize: '0.75rem',
              fontWeight: 600
            }}>
              <button
                onClick={() => setViewRole('operator')}
                style={{
                  background: viewRole === 'operator' ? '#ffffff' : 'transparent',
                  color: viewRole === 'operator' ? '#0f172a' : '#64748b',
                  border: 'none',
                  padding: '0.25rem 0.65rem',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
              >
                Operator View
              </button>
              <button
                onClick={() => setViewRole('student')}
                style={{
                  background: viewRole === 'student' ? '#ffffff' : 'transparent',
                  color: viewRole === 'student' ? '#0f172a' : '#64748b',
                  border: 'none',
                  padding: '0.25rem 0.65rem',
                  borderRadius: '4px',
                  cursor: 'pointer'
                }}
              >
                Student Tracker
              </button>
            </div>

            <button
              className="btn btn-outline"
              style={{ padding: '0.35rem 0.65rem', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
              onClick={handleExportBriefing}
              title="Download Official Emergency Briefing"
            >
              <Download size={13} />
              <span>Briefing</span>
            </button>

            <button
              className="btn btn-outline"
              style={{ padding: '0.35rem 0.65rem' }}
              onClick={fetchIncidentDetails}
              disabled={loadingData}
              title="Refresh Data"
            >
              <RefreshCw size={14} className={loadingData ? 'spin' : ''} />
            </button>

            <button
              className="btn btn-outline"
              style={{ padding: '0.35rem 0.65rem', borderRadius: '50%' }}
              onClick={onClose}
            >
              ✕
            </button>
          </div>
        </div>

        {/* Scrollable Body */}
        <div style={{ padding: '1.25rem', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          
          <div style={{ display: 'flex', gap: '1.25rem', alignItems: 'flex-start', minHeight: 0 }}>
            {/* Left Column (54% width) */}
            <div style={{ width: '54%', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

              {/* Feedback Alerts */}
          {actionError && (
            <div className="alert-banner" style={{ background: '#fef2f2', borderColor: '#fecaca', color: '#991b1b' }}>
              <AlertTriangle size={16} />
              <span>{actionError}</span>
            </div>
          )}

          {actionSuccess && (
            <div className="alert-banner" style={{ background: '#f0fdf4', borderColor: '#bbf7d0', color: '#166534' }}>
              <CheckCircle2 size={16} />
              <span>{actionSuccess}</span>
            </div>
          )}

          {/* ============================================================ */}
          {/* 1. VISUAL INCIDENT PROGRESS TIMELINE */}
          {/* ============================================================ */}
          <div style={{
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: '10px',
            padding: '1rem',
            boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
          }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase', marginBottom: '0.85rem', letterSpacing: '0.05em' }}>
              Incident Progress Lifecycle
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(9, 1fr)',
              gap: '0.35rem',
              alignItems: 'center'
            }}>
              {milestones.map((m, idx) => {
                const isCompleted = idx < currentIndex;
                const isCurrent = idx === currentIndex;

                return (
                  <div key={idx} style={{ textAlign: 'center', position: 'relative' }}>
                    <div style={{
                      width: '28px',
                      height: '28px',
                      borderRadius: '50%',
                      margin: '0 auto 0.35rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '0.75rem',
                      fontWeight: 'bold',
                      background: isCompleted
                        ? '#16a34a'
                        : isCurrent
                        ? '#0284c7'
                        : '#f1f5f9',
                      color: isCompleted || isCurrent ? '#ffffff' : '#94a3b8',
                      border: isCurrent ? '3px solid #bae6fd' : '1px solid #cbd5e1',
                      boxShadow: isCurrent ? '0 0 8px rgba(2, 132, 199, 0.4)' : 'none'
                    }}>
                      {isCompleted ? '✓' : isCurrent ? '●' : idx + 1}
                    </div>
                    <div style={{
                      fontSize: '0.6875rem',
                      fontWeight: isCurrent ? 700 : isCompleted ? 600 : 500,
                      color: isCurrent ? '#0284c7' : isCompleted ? '#166534' : '#94a3b8',
                      lineHeight: 1.2
                    }}>
                      {m.title}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ============================================================ */}
          {/* 2. THE 3 CORE OPERATIONAL CARDS */}
          {/* (What is happening now / What happened so far / What happens next) */}
          {/* ============================================================ */}
          <div className="incident-core-cards" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.85rem' }}>
            {/* What is Happening Now */}
            <div style={{
              background: '#f0f9ff',
              border: '1px solid #bae6fd',
              borderRadius: '8px',
              padding: '0.85rem',
              display: 'flex',
              flexDirection: 'column'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#0369a1', fontWeight: 700, fontSize: '0.8125rem', marginBottom: '0.35rem' }}>
                <Clock3 size={15} />
                <span>WHAT IS HAPPENING NOW?</span>
              </div>
              <p style={{ margin: 0, fontSize: '0.8125rem', color: '#0c4a6e', lineHeight: 1.45, flex: 1 }}>
                {getWhatIsHappeningNow()}
              </p>
            </div>

            {/* What Happened So Far */}
            <div style={{
              background: '#f0fdf4',
              border: '1px solid #bbf7d0',
              borderRadius: '8px',
              padding: '0.85rem',
              display: 'flex',
              flexDirection: 'column'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#15803d', fontWeight: 700, fontSize: '0.8125rem', marginBottom: '0.35rem' }}>
                <CheckCircle2 size={15} />
                <span>WHAT HAPPENED SO FAR?</span>
              </div>
              <div style={{ fontSize: '0.78125rem', color: '#14532d', lineHeight: 1.4, flex: 1 }}>
                <div>✓ Emergency reported at {incident.location}</div>
                {currentIndex >= 1 && <div>✓ Incident classified as {(incident.incident_type || 'unknown').toUpperCase()} ({(incident.severity || 'unknown').toUpperCase()})</div>}
                {currentIndex >= 2 && <div>✓ Available response resources identified</div>}
                {currentIndex >= 3 && <div>✓ Recommended response plan formulated</div>}
                {currentIndex >= 4 && <div>✓ Response authorized by safety commander</div>}
                {currentIndex >= 5 && <div>✓ Units dispatched & in-app alert displayed</div>}
                {currentIndex >= 6 && <div>✓ Response team arrival confirmed on-scene</div>}
                {currentIndex >= 7 && <div>✓ Situation confirmed under control & resolved</div>}
                {currentIndex >= 8 && <div>✓ Incident closed and archived</div>}
              </div>
            </div>

            {/* What Happens Next */}
            <div style={{
              background: '#fefce8',
              border: '1px solid #fef08a',
              borderRadius: '8px',
              padding: '0.85rem',
              display: 'flex',
              flexDirection: 'column'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#a16207', fontWeight: 700, fontSize: '0.8125rem', marginBottom: '0.35rem' }}>
                <AlertCircle size={15} />
                <span>WHAT HAPPENS NEXT?</span>
              </div>
              <p style={{ margin: 0, fontSize: '0.8125rem', color: '#713f12', lineHeight: 1.45, flex: 1, fontWeight: 500 }}>
                {getWhatHappensNext()}
              </p>
            </div>
          </div>

          {/* ============================================================ */}
          {/* 3. REPORT SUMMARY & INTAKE DETAILS */}
          {/* ============================================================ */}
          <div style={{
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            padding: '1rem'
          }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase', marginBottom: '0.5rem' }}>
              Intake Report & Description
            </div>
            <div style={{ fontSize: '0.9375rem', color: '#0f172a', lineHeight: 1.5, background: '#f8fafc', padding: '0.75rem', borderRadius: '6px', border: '1px solid #e2e8f0', marginBottom: '0.75rem' }}>
              "{incident.description}"
            </div>

            <div className="incident-meta-cards" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.6rem' }}>
              <div className="meta-card">
                <div className="meta-title">Campus Location</div>
                <div className="meta-value" style={{ fontSize: '0.8125rem', color: '#0284c7', fontWeight: 600 }}>
                  📍 {incident.location}
                </div>
              </div>

              <div className="meta-card">
                <div className="meta-title">Emergency Classification</div>
                <div className="meta-value" style={{ fontSize: '0.8125rem', fontWeight: 600, textTransform: 'uppercase' }}>
                  {incident.incident_type}
                </div>
              </div>

              <div className="meta-card">
                <div className="meta-title">Casualties / Injured</div>
                <div className="meta-value" style={{ fontSize: '0.8125rem' }}>
                  {incident.injured_count === null ? (
                    <strong style={{ color: '#0284c7' }}>Unknown (Unconfirmed)</strong>
                  ) : incident.injured_count === 0 ? (
                    <span style={{ color: '#16a34a' }}>0 (Confirmed None)</span>
                  ) : (
                    <strong style={{ color: '#dc2626' }}>{incident.injured_count} Casualties</strong>
                  )}
                </div>
              </div>

              <div className="meta-card">
                <div className="meta-title">Reported By</div>
                <div className="meta-value" style={{ fontSize: '0.8125rem' }}>
                  {incident.reported_by || 'Campus Reporter'}
                </div>
              </div>
            </div>

            {/* Explainability 'Why?' Card */}
            <div style={{ marginTop: '0.75rem' }}>
              <ExplainabilityCard
                severity={incident.severity}
                explanation={incident.summary}
              />
            </div>
            <div style={{ marginTop: '0.75rem', padding: '0.65rem 0.75rem', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '7px', fontSize: '0.75rem', color: '#1e3a8a' }}>
              <strong>AI-required departments: </strong>
              {(incident.required_departments || []).length > 0 ? incident.required_departments?.join(' • ') : 'Awaiting AI routing assessment'}
            </div>
          </div>

          {/* Live AI Agent Decision Trace Component */}
          <AIDecisionTrace
            trace={decisionTrace}
            incidentId={incident.incident_id}
          />

          <section style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', padding: '1rem', color: '#e2e8f0' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 800, letterSpacing: '0.05em', marginBottom: '0.7rem' }}>DEPARTMENT RESPONSES</div>
            {assignments.length === 0 ? (
              <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>No department assignments yet. They appear after an approved plan is dispatched.</div>
            ) : (
              <div style={{ display: 'grid', gap: '0.55rem' }}>
                {assignments.map((assignment) => (
                  <div key={assignment.id} className="incident-assignment-row" style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr 1.5fr', gap: '0.5rem', alignItems: 'center', padding: '0.55rem 0.65rem', border: '1px solid #334155', borderRadius: '6px', background: '#111c31' }}>
                    <strong style={{ fontSize: '0.72rem' }}>{assignment.department}</strong>
                    <span style={{ color: assignment.status === 'DECLINED' ? '#f87171' : assignment.status === 'COMPLETED' ? '#4ade80' : '#38bdf8', fontSize: '0.7rem', fontWeight: 800 }}>{assignment.status}</span>
                    <span style={{ color: '#cbd5e1', fontSize: '0.68rem' }}>{assignment.assigned_resources.length ? assignment.assigned_resources.join(', ') : (assignment.message || 'No team assigned')} · {new Date(assignment.updated_at).toLocaleString()}</span>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* ============================================================ */}
          {/* 4. RECOMMENDED RESPONSE PLAN & PHYSICAL RESOURCES */}
          {/* ============================================================ */}
          {responsePlan ? (
            <div style={{
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '8px',
              padding: '1rem'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase' }}>
                  Recommended Emergency Response Plan ({responsePlan.plan_id})
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <button
                    type="button"
                    className="btn btn-sm btn-outline"
                    style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', display: 'flex', alignItems: 'center', gap: '0.25rem', borderColor: '#cbd5e1', color: '#0284c7' }}
                    onClick={handleReplan}
                    disabled={loadingAction === 'replan'}
                    title="Re-evaluate response actions and resource availability"
                  >
                    <RotateCcw size={12} className={loadingAction === 'replan' ? 'spin' : ''} />
                    <span>{loadingAction === 'replan' ? 'Re-Evaluating...' : 'Dynamic Re-Plan'}</span>
                  </button>

                  <span className="badge" style={{
                    background: responsePlan.approval_status === 'approved' ? '#dcfce7' : responsePlan.approval_status === 'rejected' ? '#fee2e2' : '#fef3c7',
                    color: responsePlan.approval_status === 'approved' ? '#166534' : responsePlan.approval_status === 'rejected' ? '#991b1b' : '#92400e',
                    fontWeight: 700,
                    fontSize: '0.7rem'
                  }}>
                    {responsePlan.approval_status === 'approved' ? '✓ AUTHORIZED' : responsePlan.approval_status === 'rejected' ? '✕ REJECTED' : '⚠ AUTHORIZATION REQUIRED'}
                  </span>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1rem' }}>
                {responsePlan.recommended_actions.map((act, i) => (
                  <div key={i} style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.5rem 0.75rem',
                    background: '#f8fafc',
                    border: '1px solid #e2e8f0',
                    borderRadius: '6px',
                    fontSize: '0.8125rem'
                  }}>
                    <span style={{ color: '#0f172a', fontWeight: 500 }}>
                      {i + 1}. {act}
                    </span>
                    <span className="badge" style={{
                      background: incident.status === 'resolved' || incident.status === 'closed'
                        ? '#dcfce7'
                        : incident.status === 'in_progress' || incident.status === 'monitoring'
                        ? '#e0f2fe'
                        : responsePlan.approval_status === 'approved'
                        ? '#dcfce7'
                        : '#f1f5f9',
                      color: incident.status === 'resolved' || incident.status === 'closed'
                        ? '#166534'
                        : incident.status === 'in_progress' || incident.status === 'monitoring'
                        ? '#0369a1'
                        : responsePlan.approval_status === 'approved'
                        ? '#166534'
                        : '#475569',
                      fontSize: '0.6875rem'
                    }}>
                      {incident.status === 'resolved' || incident.status === 'closed'
                        ? 'COMPLETED'
                        : incident.status === 'in_progress' || incident.status === 'monitoring'
                        ? 'IN PROGRESS'
                        : responsePlan.approval_status === 'approved'
                        ? 'APPROVED'
                        : 'RECOMMENDED'}
                    </span>
                  </div>
                ))}
              </div>

              {/* Allocated Resources */}
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase', marginBottom: '0.4rem' }}>
                Allocated Campus Resources for This Incident:
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.5rem' }}>
                {responsePlan.allocated_resources.map((rid) => {
                  const resObj = allResources.find((r) => r.resource_id === rid);
                  const isBusy = resObj?.availability_status === 'busy' || incident.status === 'in_progress' || incident.status === 'monitoring';
                  const isCardSelected = rid === selectedResourceId;
                  return (
                    <div 
                      key={rid} 
                      onClick={() => setSelectedResourceId(rid)}
                      style={{
                        padding: '0.5rem 0.65rem',
                        background: isCardSelected ? '#eff6ff' : '#ffffff',
                        border: isCardSelected ? '2px solid #3b82f6' : '1px solid #cbd5e1',
                        borderRadius: '6px',
                        fontSize: '0.75rem',
                        cursor: 'pointer',
                        boxShadow: isCardSelected ? '0 0 5px rgba(59, 130, 246, 0.15)' : 'none',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <strong>{rid}</strong>
                        <span style={{
                          fontSize: '0.65rem',
                          background: isBusy ? '#fee2e2' : '#dcfce7',
                          color: isBusy ? '#991b1b' : '#166534',
                          padding: '1px 5px',
                          borderRadius: '4px',
                          fontWeight: 700
                        }}>
                          {isBusy ? 'DISPATCHED' : 'AVAILABLE'}
                        </span>
                      </div>
                      <div style={{ color: '#334155', marginTop: '2px' }}>{resObj?.name || 'Assigned Campus Unit'}</div>
                      <div style={{ color: '#64748b', fontSize: '0.7rem' }}>📍 {resObj?.location || incident.location}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div style={{
              background: '#f8fafc',
              border: '1px dashed #cbd5e1',
              borderRadius: '8px',
              padding: '1.25rem',
              textAlign: 'center'
            }}>
              <p style={{ margin: 0, fontSize: '0.8125rem', color: '#64748b' }}>
                No response plan prepared yet for this report.
              </p>
            </div>
          )}

          {/* ============================================================ */}
          {/* 5. OPERATOR ACTION CONTROLS & COMMAND CENTER */}
          {/* ============================================================ */}
          {viewRole === 'operator' && (
            <div style={{
              background: '#ffffff',
              border: '2px solid #0284c7',
              borderRadius: '8px',
              padding: '1rem',
              boxShadow: '0 2px 4px rgba(2, 132, 199, 0.08)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#0284c7', fontWeight: 700, fontSize: '0.875rem', marginBottom: '0.75rem' }}>
                <ShieldCheck size={18} />
                <span>Command Actions & Operational Authorization</span>
              </div>

              {/* The report, assessment, and plan stages are automatic after
                  submission. This view only exposes the human authorization
                  decision once a real plan is ready. */}
              {(incident.status === 'reported' || incident.status === 'analyzing' || incident.status === 'classified' || incident.status === 'response_planning') && !responsePlan && (
                <p style={{ fontSize: '0.8125rem', color: '#334155', margin: 0 }}>
                  AI assessment and response-plan preparation are in progress. Operator authorization will appear when the plan is ready.
                </p>
              )}

              {/* Stage 3: Awaiting Commander Approval */}
              {incident.status === 'awaiting_approval' && responsePlan && (
                <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '6px', padding: '0.85rem' }}>
                  <div style={{ fontWeight: 700, color: '#92400e', fontSize: '0.875rem', marginBottom: '0.35rem' }}>
                    ⚠️ Human Commander Authorization Required
                  </div>
                  <p style={{ fontSize: '0.8125rem', color: '#78350f', marginBottom: '0.65rem' }}>
                    A response plan has been prepared for high-impact deployment at {incident.location}. Please review the recommended actions above and provide authorization.
                  </p>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '0.5rem', marginBottom: '0.75rem' }}>
                    <div>
                      <label style={{ fontSize: '0.7rem', fontWeight: 600, color: '#78350f' }}>Authorizing Commander</label>
                      <input
                        type="text"
                        className="form-input"
                        style={{ fontSize: '0.75rem', padding: '0.35rem 0.5rem' }}
                        value={operatorName}
                        onChange={(e) => setOperatorName(e.target.value)}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: '0.7rem', fontWeight: 600, color: '#78350f' }}>Authorization Notes</label>
                      <input
                        type="text"
                        className="form-input"
                        style={{ fontSize: '0.75rem', padding: '0.35rem 0.5rem' }}
                        value={approvalNotes}
                        onChange={(e) => setApprovalNotes(e.target.value)}
                      />
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      className="btn"
                      style={{ flex: 1, background: '#16a34a', color: '#ffffff', border: 'none', padding: '0.55rem', fontWeight: 600 }}
                      onClick={() => handleDecideApproval('approve')}
                      disabled={loadingAction === 'approval'}
                    >
                      <CheckCircle2 size={15} />
                      <span>{loadingAction === 'approval' ? 'Authorizing...' : 'APPROVE RESPONSE DEPLOYMENT'}</span>
                    </button>

                    <button
                      className="btn"
                      style={{ flex: 1, background: '#dc2626', color: '#ffffff', border: 'none', padding: '0.55rem', fontWeight: 600 }}
                      onClick={() => handleDecideApproval('reject')}
                      disabled={loadingAction === 'approval'}
                    >
                      <XCircle size={15} />
                      <span>REJECT PLAN</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Stage 4: Approved, ready to dispatch */}
              {(incident.status === 'approved' || incident.status === 'authorized') && responsePlan && (
                <div>
                  <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '6px', padding: '0.65rem', marginBottom: '0.75rem', fontSize: '0.8125rem', color: '#166534' }}>
                    ✓ <strong>Approved by:</strong> {responsePlan.approved_by || operatorName} at {new Date(responsePlan.updated_at).toLocaleTimeString()}
                  </div>

                  <button
                    className="btn"
                    style={{ width: '100%', padding: '0.65rem', background: '#0284c7', color: '#ffffff', border: 'none', fontWeight: 700 }}
                    onClick={handleInitiateDispatch}
                    disabled={loadingAction === 'dispatch'}
                  >
                    <Send size={16} />
                    <span>{loadingAction === 'dispatch' ? 'Deploying Resources & Sending Alerts...' : 'INITIATE RESPONSE DISPATCH & BROADCASTS'}</span>
                  </button>
                </div>
              )}

              {/* Stage 5: Response In Progress */}
              {(incident.status === 'in_progress' || incident.status === 'response_in_progress' || incident.status === 'dispatched') && (
                <div>
                  <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '6px', padding: '0.75rem', marginBottom: '0.75rem' }}>
                    <div style={{ fontWeight: 700, color: '#991b1b', fontSize: '0.8125rem' }}>
                      🚨 Active Response & Dispatch In Progress
                    </div>
                    <p style={{ fontSize: '0.75rem', color: '#7f1d1d', margin: '0.25rem 0 0.5rem' }}>
                      Units deployed to {incident.location}. Once first responders confirm arrival and containment, confirm the status below.
                    </p>

                    {/* Broadcast Channels Live Telemetry */}
                    <div style={{ background: '#ffffff', border: '1px solid #fca5a5', borderRadius: '6px', padding: '0.6rem', marginTop: '0.5rem' }}>
                      <div style={{ fontWeight: 700, color: '#991b1b', fontSize: '0.72rem', marginBottom: '0.35rem', textTransform: 'uppercase' }}>
                        📡 EMERGENCY COMMUNICATION BROADCAST PANEL
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.4rem' }}>
                        <div style={{ background: '#f8fafc', padding: '0.35rem 0.5rem', borderRadius: '4px', border: '1px solid #e2e8f0', fontSize: '0.7rem' }}>
                          <span style={{ color: '#b45309', fontWeight: 700 }}>• IN-APP ALERT — LOCAL</span>
                          <div style={{ color: '#64748b', fontSize: '0.65rem' }}>Status: DISPLAYED IN THIS COMMAND CENTER</div>
                        </div>
                        <div style={{ background: '#f8fafc', padding: '0.35rem 0.5rem', borderRadius: '4px', border: '1px solid #e2e8f0', fontSize: '0.7rem' }}>
                          <span style={{ color: '#64748b', fontWeight: 700 }}>○ SMS — OPTIONAL</span>
                          <div style={{ color: '#64748b', fontSize: '0.65rem' }}>Status: NOT SENT / PROVIDER NOT CONFIGURED</div>
                        </div>
                        <div style={{ background: '#f8fafc', padding: '0.35rem 0.5rem', borderRadius: '4px', border: '1px solid #e2e8f0', fontSize: '0.7rem' }}>
                          <span style={{ color: '#b45309', fontWeight: 700 }}>• BROWSER VOICE — REAL</span>
                          <div style={{ color: '#64748b', fontSize: '0.65rem' }}>Status: OPERATOR CONTROLLED</div>
                        </div>
                        <div style={{ background: '#f8fafc', padding: '0.35rem 0.5rem', borderRadius: '4px', border: '1px solid #e2e8f0', fontSize: '0.7rem' }}>
                          <span style={{ color: '#64748b', fontWeight: 700 }}>○ PHONE / RADIO — OPTIONAL</span>
                          <div style={{ color: '#64748b', fontSize: '0.65rem' }}>Status: NO EXTERNAL CALL CLAIMED</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <button
                    className="btn"
                    style={{ width: '100%', padding: '0.6rem', background: '#0d9488', color: '#ffffff', border: 'none', fontWeight: 700 }}
                    onClick={handleConfirmResponse}
                    disabled={loadingAction === 'confirm_response'}
                  >
                    <CheckCheck size={16} />
                    <span>{loadingAction === 'confirm_response' ? 'Confirming...' : 'CONFIRM RESPONSE TEAM ON-SCENE'}</span>
                  </button>
                </div>
              )}

              {/* Stage 6: Monitoring */}
              {incident.status === 'monitoring' && (
                <div>
                  <div style={{ background: '#f0fdfa', border: '1px solid #99f6e4', borderRadius: '6px', padding: '0.75rem', marginBottom: '0.75rem' }}>
                    <div style={{ fontWeight: 700, color: '#0f766e', fontSize: '0.8125rem' }}>
                      👁️ Situation Under Active Monitoring
                    </div>
                    <p style={{ fontSize: '0.75rem', color: '#115e59', margin: '0.25rem 0 0.5rem' }}>
                      Response teams are active at {incident.location}. Once fire/emergency is completely neutralized and situation is safe, confirm resolution below.
                    </p>

                    <div style={{ marginTop: '0.5rem' }}>
                      <label style={{ fontSize: '0.7rem', fontWeight: 600, color: '#0f766e' }}>Resolution Verification Notes</label>
                      <input
                        type="text"
                        className="form-input"
                        style={{ fontSize: '0.75rem', padding: '0.35rem 0.5rem' }}
                        value={resolutionNotes}
                        onChange={(e) => setResolutionNotes(e.target.value)}
                      />
                    </div>
                  </div>

                  <button
                    className="btn"
                    style={{ width: '100%', padding: '0.65rem', background: '#16a34a', color: '#ffffff', border: 'none', fontWeight: 700 }}
                    onClick={handleResolveIncident}
                    disabled={loadingAction === 'resolve'}
                  >
                    <CheckCircle2 size={16} />
                    <span>{loadingAction === 'resolve' ? 'Resolving Emergency...' : 'CONFIRM SITUATION UNDER CONTROL & RESOLVE'}</span>
                  </button>
                </div>
              )}

              {/* Stage 7: Resolved -> Close */}
              {incident.status === 'resolved' && (
                <div>
                  <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '6px', padding: '0.75rem', marginBottom: '0.75rem' }}>
                    <div style={{ fontWeight: 700, color: '#166534', fontSize: '0.8125rem' }}>
                      ✓ Emergency Incident Resolved
                    </div>
                    <p style={{ fontSize: '0.75rem', color: '#14532d', margin: '0.25rem 0 0.5rem' }}>
                      All allocated emergency assets have been released. Ready for official administrative closure.
                    </p>

                    <div style={{ marginTop: '0.5rem' }}>
                      <label style={{ fontSize: '0.7rem', fontWeight: 600, color: '#166534' }}>Archival / Closing Notes</label>
                      <input
                        type="text"
                        className="form-input"
                        style={{ fontSize: '0.75rem', padding: '0.35rem 0.5rem' }}
                        value={closingNotes}
                        onChange={(e) => setClosingNotes(e.target.value)}
                      />
                    </div>
                  </div>

                  <button
                    className="btn"
                    style={{ width: '100%', padding: '0.6rem', background: '#475569', color: '#ffffff', border: 'none', fontWeight: 700 }}
                    onClick={handleCloseIncident}
                    disabled={loadingAction === 'close'}
                  >
                    <Lock size={15} />
                    <span>{loadingAction === 'close' ? 'Closing...' : 'CLOSE INCIDENT RECORD'}</span>
                  </button>
                </div>
              )}

              {/* Stage 8: Closed */}
              {incident.status === 'closed' && (
                <div style={{ background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '6px', padding: '0.75rem', textAlign: 'center' }}>
                  <div style={{ fontWeight: 700, color: '#475569', fontSize: '0.8125rem' }}>
                    🔒 Incident Closed & Archived
                  </div>
                  <p style={{ fontSize: '0.75rem', color: '#64748b', margin: '0.25rem 0 0' }}>
                    The incident workflow has been finalized. Full audit history preserved below.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* ============================================================ */}
          {/* 6. STUDENT / REPORTER TRACKING VIEW */}
          {/* ============================================================ */}
          {viewRole === 'student' && (
            <div style={{
              background: '#ffffff',
              border: '1px solid #e2e8f0',
              borderRadius: '8px',
              padding: '1.25rem',
              boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
            }}>
              <div style={{ fontSize: '0.875rem', fontWeight: 700, color: '#0f172a', marginBottom: '0.5rem' }}>
                📢 Student Emergency Status Tracker
              </div>
              <p style={{ fontSize: '0.8125rem', color: '#475569', marginBottom: '1rem' }}>
                Your report <strong>#{incident.incident_id}</strong> is registered with Vignan University Emergency Services. Below is the verified live status.
              </p>

              <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '6px', padding: '0.85rem', marginBottom: '1rem' }}>
                <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>CURRENT OPERATIONAL STATUS</div>
                <div style={{ fontSize: '1rem', fontWeight: 700, color: currentStatusObj.color, marginTop: '0.15rem' }}>
                  {currentStatusObj.label}
                </div>
                <div style={{ fontSize: '0.8125rem', color: '#334155', marginTop: '0.35rem' }}>
                  {getWhatIsHappeningNow()}
                </div>
              </div>

              {/* Safety Instructions */}
              <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '6px', padding: '0.85rem' }}>
                <div style={{ fontWeight: 700, color: '#991b1b', fontSize: '0.8125rem', marginBottom: '0.35rem' }}>
                  {safetyInfo.title}
                </div>
                <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.78125rem', color: '#7f1d1d' }}>
                  {safetyInfo.steps.map((s, i) => (
                    <li key={i} style={{ marginBottom: '0.25rem' }}>{s}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* ============================================================ */}
          {/* 7. SAFETY GUIDANCE NOTICE (Operator view) */}
          {/* ============================================================ */}
          {viewRole === 'operator' && (
            <div style={{
              background: '#fef2f2',
              border: '1px solid #fecaca',
              borderRadius: '8px',
              padding: '0.85rem'
            }}>
              <div style={{ fontWeight: 700, color: '#991b1b', fontSize: '0.8125rem', marginBottom: '0.35rem' }}>
                {safetyInfo.title}
              </div>
              <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.78125rem', color: '#7f1d1d' }}>
                {safetyInfo.steps.map((s, i) => (
                  <li key={i} style={{ marginBottom: '0.2rem' }}>{s}</li>
                ))}
              </ul>
            </div>
          )}

          {/* ============================================================ */}
          {/* 8. LIVE ACTIVITY TIMELINE & AUDIT LOGS */}
          {/* ============================================================ */}
          <div style={{
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            padding: '1rem'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase' }}>
                Live Activity & Operations Timeline
              </div>
              <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>
                {activityLogs.length} verified events logged
              </span>
            </div>

            {activityLogs.length === 0 ? (
              <p style={{ fontSize: '0.78125rem', color: '#94a3b8', margin: 0 }}>
                No activity logs recorded yet.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', maxHeight: '220px', overflowY: 'auto' }}>
                {activityLogs.map((log, idx) => (
                  <div key={idx} style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '0.6rem',
                    padding: '0.4rem 0.6rem',
                    background: '#f8fafc',
                    borderRadius: '4px',
                    fontSize: '0.75rem',
                    borderLeft: '3px solid #0284c7'
                  }}>
                    <span style={{ color: '#64748b', fontSize: '0.7rem', fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, color: '#0f172a' }}>
                        {log.description}
                      </div>
                      <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>
                        Actor: <strong>{log.actor || 'System'}</strong> • Type: {log.action_type}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
                      </div>
    
            </div>

            {/* Right Column: Map & Telemetry Dashboard (46% width) */}
            <div style={{ width: '46%', display: 'flex', flexDirection: 'column', gap: '0.85rem', position: 'sticky', top: 0 }}>
              <div style={{ height: '410px', border: '1px solid #cbd5e1', borderRadius: '8px', overflow: 'hidden', boxShadow: '0 2px 6px rgba(0,0,0,0.06)' }}>
                <CampusMap
                  incidents={[incident]}
                  activeIncidentId={incident.incident_id}
                  selectedResourceId={selectedResourceId}
                />
              </div>

              {/* Live Telemetry Tracking Card */}
              {liveTelemetry && (
                <div style={{
                  background: '#0f172a',
                  color: '#cbd5e1',
                  borderRadius: '8px',
                  padding: '0.9rem',
                  border: '1px solid #334155',
                  boxShadow: '0 4px 10px rgba(0,0,0,0.15)',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
                    <strong style={{ color: '#ffffff', fontSize: '0.78rem' }}>
                      🛰️ LIVE GPS TRANSIT TRACKING ({liveTelemetry.resource_id})
                    </strong>
                    <span style={{ fontSize: '0.62rem', background: '#dc2626', color: 'white', padding: '2px 6px', borderRadius: '4px', fontWeight: 700, animation: 'pulse 1.2s infinite' }}>
                      EN ROUTE
                    </span>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.75rem', borderBottom: '1px solid #334155', paddingBottom: '0.55rem', marginBottom: '0.55rem' }}>
                    <div>
                      <span style={{ color: '#64748b', fontSize: '0.65rem', display: 'block', textTransform: 'uppercase' }}>Dispatched Unit</span>
                      <strong style={{ color: '#ffffff' }}>{liveTelemetry.resource_id}</strong>
                    </div>
                    <div>
                      <span style={{ color: '#64748b', fontSize: '0.65rem', display: 'block', textTransform: 'uppercase' }}>Destination</span>
                      <strong style={{ color: '#ffffff' }}>{incident.location}</strong>
                    </div>
                    <div>
                      <span style={{ color: '#64748b', fontSize: '0.65rem', display: 'block', textTransform: 'uppercase' }}>ETA Remaining</span>
                      <strong style={{ color: '#10b981' }}>
                        {liveTelemetry.eta_seconds > 60 
                          ? `${Math.floor(liveTelemetry.eta_seconds / 60)} min ${liveTelemetry.eta_seconds % 60} sec`
                          : `${liveTelemetry.eta_seconds} sec`
                        }
                      </strong>
                    </div>
                    <div>
                      <span style={{ color: '#64748b', fontSize: '0.65rem', display: 'block', textTransform: 'uppercase' }}>Distance Remaining</span>
                      <strong style={{ color: '#38bdf8' }}>{liveTelemetry.distance_remaining} km</strong>
                    </div>
                  </div>

                  {/* Simulate road blockage button */}
                  <button
                    className="btn btn-sm btn-outline"
                    style={{ width: '100%', padding: '0.35rem', borderColor: '#ef4444', color: '#f87171', background: 'transparent', fontSize: '0.7rem', fontWeight: 700, cursor: 'pointer' }}
                    onClick={handleSimulateBlockage}
                    disabled={loadingAction === 'block_road'}
                  >
                    ⚠️ SIMULATE ROAD BLOCKAGE ON ACTIVE ROUTE
                  </button>
                </div>
              )}

              {/* Route preview details if selected but not dispatched */}
              {!liveTelemetry && selectedResourceId && (
                <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '0.85rem', fontSize: '0.75rem', color: '#334155' }}>
                  <div style={{ fontWeight: 700, color: '#0f172a', marginBottom: '0.35rem' }}>
                    Route Preview: {selectedResourceId} ➔ {incident.location}
                  </div>
                  <p style={{ margin: '0 0 0.45rem', fontSize: '0.72rem', color: '#64748b' }}>
                    Calculated optimal path via road network. Route distance and ETA are estimated.
                  </p>
                  <div style={{ display: 'flex', gap: '1rem', fontWeight: 600 }}>
                     <span style={{ color: '#0284c7' }}>✓ GPS Lock Confirmed</span>
                     <span style={{ color: '#475569' }}>Avg Speed: 36 km/h</span>
                  </div>
                </div>
              )}
            </div>
          </div>

        </div>

        {/* Modal Footer */}
        <div style={{
          padding: '0.75rem 1.25rem',
          borderTop: '1px solid #e2e8f0',
          background: '#f8fafc',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
            Vignan University Campus Operations Center • Vadlamudi, Guntur
          </div>

          <button className="btn btn-outline" onClick={onClose}>
            Close View
          </button>
        </div>
      </div>
    </div>
  );
};
