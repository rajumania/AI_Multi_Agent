import React, { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from './components/Header';
import { ReportEmergencyModal } from './components/ReportEmergencyModal';
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './pages/Dashboard';
import { IncidentsPage } from './pages/IncidentsPage';
import { ResourcesPage } from './pages/ResourcesPage';
import { ResponsesPage } from './pages/ResponsesPage';
import { ActivityPage } from './pages/ActivityPage';
import { DepartmentManagementPage } from './pages/DepartmentManagementPage';
import { OperationalDataPage } from './pages/OperationalDataPage';
import { api, appendWsToken } from './services/api';
import { useAuth } from './auth/AuthContext';
import { canAccessDepartmentManagement, displayName, roleDisplayName } from './auth/roles';
import { HealthResponse, Incident, LiveEvent, ResponsePlan } from './types';
import { OperatorLocation } from './components/RealOperationsControls';
import {
  AudioCapabilityState,
  VoiceAlertController,
  VoiceAlertControllerState,
  VoiceAlertState,
} from './services/voiceAlertController';
// Phase 2 realtime model + Phase 3 lazy 3D command center. The reducer is fed by
// the SAME existing WebSocket below (no second socket — Rule 11); the 3D view is
// code-split so it never weighs on login/signup or the main bundle (Rules 24–26).
import {
  getActiveWorkflow,
  initialRealtimeState,
  reduceRealtime,
} from './realtime/workflowReducer';
import { CommandCenter3DLazy } from './command3d/CommandCenter3DLazy';
import { RiskPanel } from './components/RiskPanel';
import { DisasterRiskMap } from './components/DisasterRiskMap';
import { TravelSafetyPage } from './pages/TravelSafetyPage';
import { OfflineStatus } from './components/OfflineStatus';

const upsertIncident = (items: Incident[], incident: Incident) => {
  const previous = items.find((item) => item.incident_id === incident.incident_id);
  const rank: Record<string, number> = {
    reported: 0,
    analyzing: 1,
    assessing: 1,
    classified: 2,
    planning: 3,
    response_planning: 3,
    awaiting_approval: 4,
    approved: 5,
    authorized: 5,
    in_progress: 6,
    response_in_progress: 6,
    dispatched: 6,
    monitoring: 7,
    resolved: 8,
    closed: 9,
  };
  const merged = previous && (rank[previous.status] ?? 0) > (rank[incident.status] ?? 0)
    ? { ...incident, status: previous.status, ai_provider_status: previous.ai_provider_status || incident.ai_provider_status }
    : incident;
  return [merged, ...items.filter((item) => item.incident_id !== incident.incident_id)];
};

export const App: React.FC<{ initialTab?: string }> = ({ initialTab = 'overview' }) => {
  const [activeTab, setActiveTab] = useState<string>(initialTab);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isReportModalOpen, setIsReportModalOpen] = useState<boolean>(false);
  const [wsState, setWsState] = useState<'CONNECTED' | 'CONNECTING' | 'OFFLINE'>('CONNECTING');
  const [timeline, setTimeline] = useState<LiveEvent[]>([]);
  const [responsePlan, setResponsePlan] = useState<ResponsePlan | null>(null);
  const [assignedResources, setAssignedResources] = useState<string[]>([]);
  const [workflowStatus, setWorkflowStatus] = useState('STANDING BY');
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [inAppAlertVisible, setInAppAlertVisible] = useState(false);
  const [operatorLocation, setOperatorLocation] = useState<OperatorLocation | null>(null);
  const [commandIncidentId, setCommandIncidentId] = useState<string | null>(null);
  const [audioState, setAudioState] = useState<AudioCapabilityState>('NOT_ENABLED');
  const [voiceState, setVoiceState] = useState<VoiceAlertState>('IDLE');
  const [voiceIncident, setVoiceIncident] = useState<Incident | null>(null);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [notificationRefreshKey, setNotificationRefreshKey] = useState(0);
  const [riskRefreshKey, setRiskRefreshKey] = useState(0);
  const voiceController = useRef<VoiceAlertController | null>(null);
  // Ref that mirrors commandIncidentId so the stable WS effect (dep: [addTimelineEvent])
  // can always read the current active incident without a stale closure.
  const commandIncidentIdRef = useRef<string | null>(null);

  // Phase 2 realtime workflow state: the normalized, backend-driven view of each
  // incident's agent pipeline. Folded from the REAL WebSocket events already
  // received below; the 3D command center renders this — it never drives it.
  const [realtimeState, dispatchRealtime] = useReducer(reduceRealtime, initialRealtimeState());
  const activeWorkflow = useMemo(() => getActiveWorkflow(realtimeState), [realtimeState]);

  // Identity + logout come from the authenticated session (Increment 2). This
  // route only renders for operator/admin principals (guarded by AppRoutes), so
  // the command console keeps all of its existing capabilities — only the old
  // hardcoded user and no-op logout are replaced.
  const { user: authUser, logout } = useAuth();
  const navigate = useNavigate();
  const handleLogout = useCallback(() => {
    logout();
    navigate('/login', { replace: true });
  }, [logout, navigate]);
  const headerUser = useMemo(
    () => ({ full_name: displayName(authUser), role: roleDisplayName(authUser) }),
    [authUser],
  );

  const handleVoiceStateChange = useCallback((state: VoiceAlertControllerState) => {
    setAudioState(state.audioState);
    setVoiceState(state.voiceState);
    setVoiceIncident(state.incident);
    setVoiceError(state.error);
  }, []);

  const addTimelineEvent = useCallback((event: LiveEvent) => {
    setTimeline((previous) => [event, ...previous.filter((item) => !(item.event_name === event.event_name && item.timestamp === event.timestamp))].slice(0, 80));
  }, []);

  const addClientTimelineEvent = useCallback((incidentId: string, eventName: string, description: string) => {
    const now = new Date();
    addTimelineEvent({ event_name: eventName, incident_id: incidentId, timestamp: now.toISOString(), time_display: now.toLocaleTimeString(), description });
  }, [addTimelineEvent]);

  useEffect(() => {
    const controller = new VoiceAlertController({
      onStateChange: handleVoiceStateChange,
      onClientEvent: (event) => {
        if (event.incident_id) addClientTimelineEvent(event.incident_id, event.event_name, event.description || event.event_name);
      },
    });
    voiceController.current = controller;
    return () => {
      controller.dispose();
      if (voiceController.current === controller) voiceController.current = null;
    };
  }, [addClientTimelineEvent, handleVoiceStateChange]);

  const fetchTelemetry = useCallback(async () => {
    setLoading(true);
    try {
      const [healthData, incidentsData] = await Promise.all([
        api.getHealth().catch((err) => { console.warn('Backend /health unreachable:', err); return null; }),
        api.getIncidents().catch((err) => { console.warn('Incidents fetch failed:', err); return []; }),
      ]);
      setHealth(healthData);
      setIncidents(incidentsData);
      voiceController.current?.syncIncidents(incidentsData);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 10000);
    return () => clearInterval(interval);
  }, [fetchTelemetry]);

  // Keep the ref in sync with state so the WS handler always has the current value.
  useEffect(() => {
    commandIncidentIdRef.current = commandIncidentId;
  }, [commandIncidentId]);

  useEffect(() => {
    const base = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/^http/, 'ws');
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let reconnectDelay = 1000;
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      setWsState('CONNECTING');
      socket = new WebSocket(appendWsToken(`${base}/api/v1/events/ws`));
      socket.onopen = () => {
        reconnectDelay = 1000;
        setWsState('CONNECTED');
        // Reconcile durable notifications after every reconnect.
        setNotificationRefreshKey((value) => value + 1);
        socket?.send('operator-dashboard');
      };
      socket.onerror = () => setWsState('OFFLINE');
      socket.onclose = () => {
        if (disposed) return;
        setWsState('OFFLINE');
        reconnectTimer = window.setTimeout(connect, reconnectDelay);
        reconnectDelay = Math.min(reconnectDelay * 2, 10000);
      };
      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data) as LiveEvent;
          addTimelineEvent(event);
          // Fold the SAME event into the Phase 2 realtime model (dispatch is
          // stable; the reducer ignores non-workflow events). This is what drives
          // the 3D command center from real backend state.
          dispatchRealtime(event);
          if (['notification_created', 'notification_delivered', 'notification_read', 'notification_failed'].includes(event.event_name)) {
            setNotificationRefreshKey((value) => value + 1);
          }
          if (event.event_name === 'notification_created') {
            if (event.notification_id && socket?.readyState === WebSocket.OPEN) {
              socket.send(JSON.stringify({ type: 'notification_delivered', notification_id: event.notification_id }));
            }
          }
          if (['risk_updated', 'early_warning_created', 'weather_updated', 'environment_updated'].includes(event.event_name)) {
            setRiskRefreshKey((value) => value + 1);
          }
          if (event.event_name === 'in_app_alert_available') setInAppAlertVisible(true);
          if (event.event_name === 'incident_resolved' || event.event_name === 'incident_closed') {
            setInAppAlertVisible(false);
            voiceController.current?.handleLifecycleEvent(event);
          }
          if (event.event_name === 'dispatch_started') {
            setAssignedResources(event.dispatched_resources || []);
            // Dispatch can now be triggered from IncidentCommandView (Phase 4),
            // so raise the in-app alert banner here as well as from the old chain.
            if (event.dispatched_resources && event.dispatched_resources.length > 0) {
              setInAppAlertVisible(true);
            }
          }
          // Phase 5 hardening: sync workflowStatus from real backend WS events so
          // the dashboard header reflects operator actions taken in IncidentCommandView
          // (approval, dispatch, resolve) without a stale closure. commandIncidentIdRef
          // always holds the current incident regardless of when the effect ran.
          const activeId = commandIncidentIdRef.current;
          if (activeId && event.incident_id === activeId) {
            if (event.event_name === 'assessment_started') {
              setWorkflowStatus('AI ASSESSMENT IN PROGRESS');
              setWorkflowError(null);
            } else if (event.event_name === 'incident_assessed' || event.event_name === 'incident_updated') {
              setWorkflowStatus(event.ai_provider_status === 'FALLBACK_ACTIVE' ? 'AI FALLBACK ACTIVE' : 'INCIDENT ASSESSED');
              setWorkflowError(null);
            } else if (event.event_name === 'response_plan_generated' || event.event_name === 'awaiting_human_authorization') {
              setWorkflowStatus('AWAITING HUMAN AUTHORIZATION');
              setWorkflowError(null);
            } else if (event.event_name === 'assessment_failed') {
              setWorkflowStatus('WORKFLOW ATTENTION REQUIRED');
              setWorkflowError(event.description || 'Automatic AI assessment failed.');
            } else if (
              event.event_name === 'approval_approved' ||
              event.event_name === 'approval_granted'
            ) {
              setWorkflowStatus('RESPONSE AUTHORIZED — READY TO DISPATCH');
              setWorkflowError(null);
            } else if (event.event_name === 'approval_rejected') {
              setWorkflowStatus('PLAN REJECTED — REPLAN REQUIRED');
            } else if (
              event.event_name === 'dispatch_started' ||
              event.event_name === 'response_dispatched' ||
              event.event_name === 'resource_dispatched'
            ) {
              setWorkflowStatus('RESPONSE IN PROGRESS');
              setWorkflowError(null);
            } else if (event.event_name === 'monitoring_started') {
              setWorkflowStatus('MONITORING — ON SCENE');
            } else if (
              event.event_name === 'incident_resolved' ||
              event.event_name === 'incident_closed'
            ) {
              setWorkflowStatus('STANDING BY');
              setWorkflowError(null);
            }
          }
          if (
            event.event_name === 'incident_created'
            && event.incident_id
            && event.incident_type
            && event.location
            && event.severity
            && event.status
          ) {
            // The create event carries the actual incident fields. Trigger the
            // browser alert from the WebSocket frame immediately; the REST
            // snapshot below then enriches the UI without replaying the alert.
            voiceController.current?.handleIncident({
              incident_id: event.incident_id,
              description: event.incident_description || event.description || '',
              incident_type: event.incident_type,
              location: event.location,
              severity: event.severity,
              injured_count: event.injured_count ?? null,
              status: event.status,
              created_at: event.created_at || event.timestamp,
              updated_at: event.updated_at || event.timestamp,
            } as Incident);
          }
          // Risk lifecycle events use a `risk:<prediction-id>` correlation key,
          // not an incident primary key. Do not turn those into avoidable 404s.
          if (
            event.incident_id
            && event.incident_id !== 'system'
            && event.incident_id !== 'live_telemetry'
            && !event.incident_id.startsWith('risk:')
          ) {
            api.getIncidentById(event.incident_id).then((updated) => {
              setIncidents((previous) => upsertIncident(previous, updated));
              // The existing backend WebSocket event is the trigger. Fetching the
              // record supplies the complete, current incident-specific message.
              voiceController.current?.handleIncident(updated);
            }).catch(() => undefined);
          }
        } catch {
          // Ignore malformed websocket frames while keeping the socket alive.
        }
      };
    };

    connect();
    return () => {
      disposed = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [addTimelineEvent]);

  const activeIncident = useMemo(() => {
    if (commandIncidentId) {
      const selected = incidents.find((item) => item.incident_id === commandIncidentId);
      if (selected && selected.status !== 'resolved' && selected.status !== 'closed') return selected;
    }
    return incidents.find((item) => item.status !== 'resolved' && item.status !== 'closed');
  }, [commandIncidentId, incidents]);

  // Phase 4A: runEmergencyWorkflow now STOPS after generating the response plan.
  // The workflow pauses at AWAITING_APPROVAL so the operator must open the
  // Incident Command View and use the existing APPROVE / REJECT buttons there.
  // Auto-approval and auto-dispatch have been removed — human sign-off is required.
  const runEmergencyWorkflow = useCallback(async (created: Incident) => {
    const incidentId = created.incident_id;
    setCommandIncidentId(incidentId);
    setWorkflowError(null);
    setInAppAlertVisible(false);
    setResponsePlan(null);
    setAssignedResources([]);

    try {
      setWorkflowStatus('AI ASSESSMENT IN PROGRESS');

      // ── HUMAN GATE ────────────────────────────────────────────────────────
      // Workflow intentionally stops here. The operator must open the Incident
      // Command View (via the Incidents page) and click APPROVE RESPONSE
      // DEPLOYMENT. The IncidentCommandView component already contains the full
      // APPROVE / REJECT / DISPATCH controls that call the real backend APIs.
      // ─────────────────────────────────────────────────────────────────────
      setWorkflowStatus('AWAITING HUMAN AUTHORIZATION');
      await fetchTelemetry();
    } catch (error: any) {
      setWorkflowStatus('WORKFLOW ATTENTION REQUIRED');
      setWorkflowError(error.message || 'The live response workflow could not complete.');
      await fetchTelemetry();
    }
  }, [addClientTimelineEvent, addTimelineEvent, fetchTelemetry]);
  void runEmergencyWorkflow;

  const handleIncidentCreated = (newIncident: Incident) => {
    const assessmentStarted: Incident = {
      ...newIncident,
      status: 'analyzing',
      ai_provider_status: newIncident.ai_provider_status || 'GEMINI_IN_PROGRESS',
      current_step: 'AI incident assessment is in progress.',
      next_action: 'Supervisor Agent is assessing the report before response planning.',
    };
    setIncidents((previous) => upsertIncident(previous, assessmentStarted));
    setActiveTab('overview');
    addClientTimelineEvent(newIncident.incident_id, 'incident_reported_client', `Incident reported at ${newIncident.location}.`);
    setCommandIncidentId(newIncident.incident_id);
    setWorkflowError(null);
    setInAppAlertVisible(false);
    setResponsePlan(null);
    setAssignedResources([]);
    setWorkflowStatus('AI ASSESSMENT IN PROGRESS');
  };

  const handleSelectIncident = (incident: Incident) => {
    setCommandIncidentId(incident.incident_id);
    setActiveTab('overview');
  };

  const handleResolveIncident = async (incident: Incident) => {
    try {
      setWorkflowStatus('RESOLVING INCIDENT');
      const resolved = await api.resolveIncident(incident.incident_id, 'Situation confirmed under control by the response commander.');
      setIncidents((previous) => upsertIncident(previous, resolved));
      setInAppAlertVisible(false);
      setWorkflowStatus('STANDING BY');
      setCommandIncidentId(null);
      setOperatorLocation(null);
      await fetchTelemetry();
    } catch (error: any) {
      setWorkflowError(error.message || 'Incident resolution failed.');
    }
  };

  return (
    <div className="app-container" style={{ position: 'relative' }}>
      <OfflineStatus />
      <Header health={health} loading={loading} onRefresh={fetchTelemetry} wsState={wsState} user={headerUser} onLogout={handleLogout} notificationRefreshKey={notificationRefreshKey} onOpenMenu={() => setMobileNavOpen(true)} />
      <div className="main-body">
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} mobileOpen={mobileNavOpen} onClose={() => setMobileNavOpen(false)} showDepartmentManagement={canAccessDepartmentManagement(authUser)} />
        <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          {activeTab === 'overview' && (
            <Dashboard
              health={health}
              incidents={incidents}
              loading={loading}
              onRefresh={fetchTelemetry}
              onOpenReportModal={() => setIsReportModalOpen(true)}
              onNavigateToIncidents={() => setActiveTab('incidents')}
              onSelectIncident={handleSelectIncident}
              activeIncident={activeIncident}
              responsePlan={responsePlan}
              assignedResources={assignedResources}
              timeline={timeline}
              workflowStatus={workflowStatus}
              workflowError={workflowError}
              demoPushVisible={inAppAlertVisible}
              wsState={wsState}
              audioState={audioState}
              voiceState={voiceState}
              voiceIncident={voiceIncident}
              voiceError={voiceError}
              onEnableAudio={() => { void voiceController.current?.initializeAudio(); }}
              onMute={() => voiceController.current?.mute()}
              onUnmute={() => voiceController.current?.unmute()}
              onReplay={() => voiceController.current?.replay()}
              onStopVoice={() => voiceController.current?.stop()}
              operatorLocation={operatorLocation}
              onGpsLocation={setOperatorLocation}
              onResolveIncident={handleResolveIncident}
              onViewResponsePlan={() => setActiveTab('responses')}
              riskRefreshKey={riskRefreshKey}
            />
          )}
          {activeTab === 'risk' && <div className="app-content"><div className="dashboard-title-row"><div><h2>Risk & Early Warning</h2><p>Evidence-based disaster risk estimation for communities and response teams.</p></div></div><RiskPanel refreshKey={riskRefreshKey} /></div>}
          {activeTab === 'travel-safety' && <TravelSafetyPage />}
          {activeTab === 'map' && <div className="app-content"><div className="dashboard-title-row"><div><h2>Disaster Risk Map</h2><p>Interactive backend-driven risk, vulnerability, sensor, incident, resource, route and alert command view.</p></div></div><DisasterRiskMap incidents={incidents} onSelectIncident={handleSelectIncident} activeIncidentId={activeIncident?.incident_id} liveEvents={timeline} operatorLocation={operatorLocation} /></div>}
          {activeTab === 'incidents' && <IncidentsPage incidents={incidents} loading={loading} onOpenReportModal={() => setIsReportModalOpen(true)} onRefresh={fetchTelemetry} liveEvents={timeline} />}
          {activeTab === 'resources' && <ResourcesPage />}
          {activeTab === 'sensors' && <OperationalDataPage view="sensors" liveEvents={timeline} />}
          {activeTab === 'rescue-requests' && <OperationalDataPage view="rescue" liveEvents={timeline} />}
          {activeTab === 'shelters-hospitals' && <OperationalDataPage view="shelters" liveEvents={timeline} />}
          {activeTab === 'responses' && <ResponsesPage />}
          {activeTab === 'alerts' && <OperationalDataPage view="alerts" liveEvents={timeline} />}
          {activeTab === 'activity' && <ActivityPage />}
          {activeTab === 'monitoring' && <OperationalDataPage view="monitoring" liveEvents={timeline} />}
          {activeTab === 'department-management' && canAccessDepartmentManagement(authUser) && <DepartmentManagementPage />}
          {activeTab === 'command3d' && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '1.25rem' }}>
              <CommandCenter3DLazy incident={activeWorkflow} connected={wsState === 'CONNECTED'} liveEvents={timeline} />
            </div>
          )}
        </main>
      </div>
      <ReportEmergencyModal isOpen={isReportModalOpen} onClose={() => setIsReportModalOpen(false)} onIncidentCreated={handleIncidentCreated} />
    </div>
  );
};

export default App;
