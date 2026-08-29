import React from 'react';
import {
  AlertTriangle,
  Flame,
  Layers,
  ShieldCheck,
  PlusCircle,
  RotateCcw,
  Clock,
  HeartPulse,
  ArrowRight
} from 'lucide-react';
import { HealthResponse, Incident, LiveEvent, ResponsePlan } from '../types';
import { MetricCard } from '../components/MetricCard';
import { DisasterRiskMap } from '../components/DisasterRiskMap';
import { RecentActivityPlaceholder } from '../components/RecentActivityPlaceholder';
import { ResourceBreakdownWidget } from '../components/ResourceBreakdownWidget';
import { SimulationControls } from '../components/SimulationControls';
import { OperatorLocation, RealOperationsControls } from '../components/RealOperationsControls';
import { AudioCapabilityState, VoiceAlertState } from '../services/voiceAlertController';
import { RiskPanel } from '../components/RiskPanel';


interface DashboardProps {
  health: HealthResponse | null;
  incidents: Incident[];
  loading: boolean;
  onRefresh: () => void;
  onOpenReportModal: () => void;
  onNavigateToIncidents: () => void;
  onSelectIncident?: (incident: Incident) => void;
  activeIncident?: Incident;
  responsePlan?: ResponsePlan | null;
  assignedResources?: string[];
  timeline?: LiveEvent[];
  workflowStatus?: string;
  workflowError?: string | null;
  demoPushVisible?: boolean;
  wsState?: 'CONNECTED' | 'CONNECTING' | 'OFFLINE';
  audioState?: AudioCapabilityState;
  voiceState?: VoiceAlertState;
  voiceIncident?: Incident | null;
  voiceError?: string | null;
  onEnableAudio?: () => void;
  onMute?: () => void;
  onUnmute?: () => void;
  onReplay?: () => void;
  onStopVoice?: () => void;
  operatorLocation?: OperatorLocation | null;
  onGpsLocation?: (location: OperatorLocation | null) => void;
  onResolveIncident?: (incident: Incident) => void;
  onViewResponsePlan?: () => void;
  riskRefreshKey?: number;
}

const timelineLabel = (eventName: string) => {
  const labels: Record<string, string> = {
    incident_created: 'Incident reported',
    incident_reported_client: 'Incident reported',
    ai_analysis_completed: 'AI Incident Analysis completed',
    resources_verified: 'Emergency resources identified',
    response_plan_generated_client: 'Response plan generated',
    approval_granted_client: 'Response plan authorized',
    dispatch_started_client: 'Responder/resource assignment started',
    incident_updated: 'Severity classified',
    workflow_started: 'AI Incident Analysis started',
    agent_started: 'AI agent started',
    agent_completed: 'AI agent completed',
    response_plan_updated: 'Response plan preparation completed',
    response_plan_generated: 'Response plan generated',
    resource_verified: 'Emergency resources verified',
    approval_granted: 'Response plan authorized',
    dispatch_started: 'Response dispatch started',
    resource_dispatched: 'Responder/resource assigned',
    vehicle_location_updated: 'Responder location updated',
    voice_alert_started: 'Voice emergency alert started',
    in_app_alert_available: 'In-app emergency alert displayed',
    in_app_alert_displayed: 'In-app emergency alert displayed',
    voice_alert_muted: 'Voice alert muted by command user',
    voice_alert_stopped: 'Voice alert stopped',
    incident_resolved: 'Incident resolved',
  };
  return labels[eventName] || eventName.split('_').join(' ').replace(/\b\w/g, (letter: string) => letter.toUpperCase());
};

export const Dashboard: React.FC<DashboardProps> = ({
  health,
  incidents,
  loading,
  onRefresh,
  onOpenReportModal,
  onNavigateToIncidents,
  onSelectIncident,
  activeIncident,
  responsePlan,
  assignedResources = [],
  timeline = [],
  workflowStatus = 'STANDING BY',
  workflowError,
  demoPushVisible = false,
  wsState = 'OFFLINE',
  audioState = 'NOT_ENABLED',
  voiceState = 'IDLE',
  voiceIncident = null,
  voiceError = null,
  onEnableAudio,
  onMute,
  onUnmute,
  onReplay,
  onStopVoice,
  operatorLocation,
  onGpsLocation,
  onResolveIncident,
  onViewResponsePlan,
  riskRefreshKey = 0,
}) => {
  const resourceCount = health?.seeded_resources ?? 13;
  const activeIncidents = incidents.filter((i) => i.status !== 'resolved' && i.status !== 'closed');
  const latestActiveId = activeIncidents.length > 0 ? activeIncidents[0].incident_id : undefined;

  return (
    <div className="app-content">
      {/* Digital Twin Autonomous Simulation Bar */}
      <SimulationControls
        activeIncidentId={latestActiveId}
        onRefresh={onRefresh}
        onScenarioStarted={(inc) => {
          if (onSelectIncident) {
            onSelectIncident(inc);
          } else {
            onNavigateToIncidents();
          }
        }}
      />
      <RealOperationsControls
        incident={activeIncident || activeIncidents[0]}
        voiceIncident={voiceIncident}
        audioState={audioState}
        voiceState={voiceState}
        voiceError={voiceError}
        wsState={wsState}
        demoPushVisible={demoPushVisible}
        onEnableAudio={onEnableAudio}
        onMute={onMute}
        onUnmute={onUnmute}
        onReplay={onReplay}
        onStopVoice={onStopVoice}
        onGpsLocation={onGpsLocation}
      />

      {activeIncident && (
        <div className="command-center-grid">
          <section className="active-emergency-card">
            <div className="active-emergency-heading"><span className="live-pulse-dot" /> ACTIVE EMERGENCY <span className="workflow-chip">{workflowStatus}</span></div>
            <div className="active-emergency-body">
              <div><small>INCIDENT</small><strong>{activeIncident.incident_type.toUpperCase()} — {activeIncident.location}</strong><span>{activeIncident.description}</span></div>
              <div className="emergency-facts"><div><small>SEVERITY</small><strong>{activeIncident.severity.toUpperCase()}</strong></div><div><small>STATUS</small><strong>RESPONSE IN PROGRESS</strong></div><div><small>AI ASSESSMENT</small><strong>{activeIncident.summary ? 'COMPLETED' : 'PROCESSING'}</strong></div><div><small>RESPONSE PLAN</small><strong>{responsePlan ? 'ACTIVE' : 'PROCESSING'}</strong></div><div><small>RESPONDERS</small><strong>{assignedResources.length || 'COORDINATING'}</strong></div><div><small>NOTIFICATIONS</small><strong>{demoPushVisible ? 'IN-APP ACTIVE' : 'OPTIONAL CHANNELS'}</strong></div></div>
              <div className="emergency-actions"><button className="btn btn-outline" onClick={onViewResponsePlan}>VIEW RESPONSE PLAN</button><button className="btn btn-outline" onClick={() => document.querySelector('.map-command-panel')?.scrollIntoView({ behavior: 'smooth' })}>VIEW MAP</button><button className="btn btn-danger" onClick={() => onResolveIncident?.(activeIncident)}>RESOLVE INCIDENT</button></div>
            </div>
          </section>
          {demoPushVisible && <section className="demo-push-card"><div className="demo-push-label">IN-APP ALERT — LOCAL CHANNEL</div><h3>AITAM EMERGENCY ALERT</h3><strong>{activeIncident.incident_type.toUpperCase()} reported:</strong><p>{activeIncident.location}</p><p>Response teams activated.</p><small>Recipients: Security Team • Medical Team • Evacuation Team</small><em>No external mobile push delivery claimed.</em></section>}
        </div>
      )}
      {workflowError && <div className="alert-banner error" role="alert">{workflowError}</div>}

      <div className="dashboard-title-row">
        <div>
          <h2>Disaster Response Command Center</h2>
          <p>Real-time emergency operations, AITAM community monitoring, and rapid response coordination.</p>
        </div>

        <div className="quick-actions-group">
          <button
            className="btn btn-outline"
            onClick={onRefresh}
            disabled={loading}
          >
            <RotateCcw size={15} />
            <span>Refresh Telemetry</span>
          </button>

          <button
            className="btn btn-danger"
            onClick={onOpenReportModal}
            style={{ backgroundColor: 'var(--danger-600)', color: '#ffffff' }}
          >
            <PlusCircle size={16} />
            <span>Report Emergency</span>
          </button>
        </div>
      </div>

      <RiskPanel refreshKey={riskRefreshKey} />

      {/* Top Level Metric Cards */}
      <div className="metrics-grid">
        <MetricCard
          label="Active Incidents"
          value={activeIncidents.length}
          subtext={
            activeIncidents.length > 0
              ? `${activeIncidents.length} active emergency event(s)`
              : 'All sectors reported clear'
          }
          icon={AlertTriangle}
          variant={activeIncidents.length > 0 ? 'red' : 'blue'}
        />

        <MetricCard
          label="Critical & High"
          value={incidents.filter((i) => i.severity === 'critical' || i.severity === 'high').length}
          subtext={
            incidents.filter((i) => i.severity === 'critical' || i.severity === 'high').length > 0
              ? `${incidents.filter((i) => i.severity === 'critical' || i.severity === 'high').length} priority situation(s)`
              : 'No critical escalations'
          }
          icon={Flame}
          variant="red"
        />

        <MetricCard
          label="Available Resources"
          value={resourceCount}
          subtext={`${resourceCount} verified emergency resources`}
          icon={Layers}
          variant="teal"
        />

        <MetricCard
          label="Response Operations"
          value="Level 1"
          subtext="Security, Medical, Transport & Public Alerts Ready"
          icon={ShieldCheck}
          variant="green"
        />
      </div>

      {/* If incidents exist, show an Active Emergency Banner / Quick Preview */}
      {incidents.length > 0 && (
        <div className="panel-card" style={{ marginBottom: '1.5rem', borderLeft: '4px solid var(--danger-600)' }}>
          <div className="panel-header" style={{ background: '#fef2f2' }}>
            <div className="panel-title" style={{ color: 'var(--danger-text)' }}>
              <AlertTriangle size={18} />
              <span>Latest Reported Incident Stream</span>
            </div>
            <button
              className="btn btn-outline"
              style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
              onClick={onNavigateToIncidents}
            >
              <span>View All ({incidents.length})</span>
              <ArrowRight size={13} />
            </button>
          </div>
          <div className="panel-body" style={{ padding: '0.875rem 1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                  <span className="incident-id-tag">{incidents[0].incident_id}</span>
                  <strong style={{ fontSize: '0.9375rem', color: 'var(--text-primary)' }}>
                    {incidents[0].location}
                  </strong>
                  <span className="badge badge-high">{(incidents[0].severity || 'unknown').toUpperCase()}</span>
                </div>
                <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                  {incidents[0].description}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <HeartPulse size={14} color="#0d9488" />
                  <span>
                    Injured:{' '}
                    {incidents[0].injured_count === null ? (
                      <strong>Unknown (null)</strong>
                    ) : (
                      `${incidents[0].injured_count} confirmed`
                    )}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <Clock size={14} />
                  <span>{new Date(incidents[0].created_at).toLocaleTimeString()}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main 2-Column Section: Map & Activity Feed */}
      <div className="dashboard-columns">
        <div className="map-command-panel"><DisasterRiskMap incidents={incidents} onSelectIncident={onSelectIncident} activeIncidentId={activeIncident?.incident_id} liveEvents={timeline} operatorLocation={operatorLocation} /></div>
        <div className="timeline-column">
          <section className="panel-card live-timeline-card"><div className="panel-header"><div className="panel-title">LIVE RESPONSE TIMELINE</div><span className="panel-tag">SERVER / CLIENT EVENTS</span></div><div className="timeline-list">{timeline.filter((event) => !activeIncident || !event.incident_id || event.incident_id === activeIncident.incident_id).slice(0, 14).map((event, index) => <div className="timeline-item" key={`${event.timestamp}-${event.event_name}-${index}`}><div className="timeline-time">{event.time_display || new Date(event.timestamp).toLocaleTimeString()}</div><div className="timeline-content"><div className="timeline-title">{timelineLabel(event.event_name)}</div><div className="timeline-desc">{event.description || event.event_name.split('_').join(' ')}</div></div></div>)}{timeline.length === 0 && <div className="empty-timeline">Waiting for live incident events…</div>}</div></section>
          <RecentActivityPlaceholder />
        </div>
      </div>


      {/* Resource Breakdown Table/Cards */}
      <ResourceBreakdownWidget />
    </div>
  );
};
