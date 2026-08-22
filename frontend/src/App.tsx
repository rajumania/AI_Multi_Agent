import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Header } from './components/Header';
import { ReportEmergencyModal } from './components/ReportEmergencyModal';
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './pages/Dashboard';
import { IncidentsPage } from './pages/IncidentsPage';
import { ResourcesPage } from './pages/ResourcesPage';
import { ResponsesPage } from './pages/ResponsesPage';
import { ActivityPage } from './pages/ActivityPage';
import { api } from './services/api';
import { HealthResponse, Incident, LiveEvent, ResponsePlan } from './types';
import { OperatorLocation } from './components/RealOperationsControls';

const upsertIncident = (items: Incident[], incident: Incident) => [
  incident,
  ...items.filter((item) => item.incident_id !== incident.incident_id),
];

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('overview');
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
  const [demoPushVisible, setDemoPushVisible] = useState(false);
  const [operatorLocation, setOperatorLocation] = useState<OperatorLocation | null>(null);
  const [commandIncidentId, setCommandIncidentId] = useState<string | null>(null);
  const workflowRun = useRef(0);

  const [user] = useState<any>({ name: 'Demo' });

  const addTimelineEvent = useCallback((event: LiveEvent) => {
    setTimeline((previous) => [event, ...previous.filter((item) => !(item.event_name === event.event_name && item.timestamp === event.timestamp))].slice(0, 80));
  }, []);

  const addClientTimelineEvent = useCallback((incidentId: string, eventName: string, description: string) => {
    const now = new Date();
    addTimelineEvent({ event_name: eventName, incident_id: incidentId, timestamp: now.toISOString(), time_display: now.toLocaleTimeString(), description });
  }, [addTimelineEvent]);

  const fetchTelemetry = useCallback(async () => {
    setLoading(true);
    try {
      const [healthData, incidentsData] = await Promise.all([
        api.getHealth().catch((err) => { console.warn('Backend /health unreachable:', err); return null; }),
        api.getIncidents().catch((err) => { console.warn('Incidents fetch failed:', err); return []; }),
      ]);
      setHealth(healthData);
      setIncidents(incidentsData);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 10000);
    return () => clearInterval(interval);
  }, [fetchTelemetry]);

  useEffect(() => {
    const base = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/^http/, 'ws');
    const socket = new WebSocket(`${base}/api/v1/events/ws`);
    setWsState('CONNECTING');
    socket.onopen = () => {
      setWsState('CONNECTED');
      socket.send('operator-dashboard');
    };
    socket.onerror = () => setWsState('OFFLINE');
    socket.onclose = () => setWsState('OFFLINE');
    socket.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as LiveEvent;
        addTimelineEvent(event);
        if (event.event_name === 'demo_push_available') setDemoPushVisible(true);
        if (event.event_name === 'incident_resolved') setDemoPushVisible(false);
        if (event.event_name === 'dispatch_started') setAssignedResources(event.dispatched_resources || []);
        if (event.incident_id && event.incident_id !== 'system' && event.incident_id !== 'live_telemetry') {
          api.getIncidentById(event.incident_id).then((updated) => {
            setIncidents((previous) => upsertIncident(previous, updated));
          }).catch(() => undefined);
        }
      } catch {
        // Ignore malformed websocket frames while keeping the socket alive.
      }
    };
    return () => socket.close();
  }, [addTimelineEvent]);

  const activeIncident = useMemo(() => {
    if (commandIncidentId) {
      const selected = incidents.find((item) => item.incident_id === commandIncidentId);
      if (selected && selected.status !== 'resolved' && selected.status !== 'closed') return selected;
    }
    return incidents.find((item) => item.status !== 'resolved' && item.status !== 'closed');
  }, [commandIncidentId, incidents]);

  const runEmergencyWorkflow = useCallback(async (created: Incident) => {
    const runId = ++workflowRun.current;
    const incidentId = created.incident_id;
    setCommandIncidentId(incidentId);
    setWorkflowError(null);
    setDemoPushVisible(false);
    setResponsePlan(null);
    setAssignedResources([]);

    try {
      setWorkflowStatus('AI INCIDENT ANALYSIS');
      const analysis = await api.analyzeIncident(incidentId);
      if (runId !== workflowRun.current) return;
      setIncidents((previous) => upsertIncident(previous, analysis.incident));
      addClientTimelineEvent(incidentId, 'ai_analysis_completed', `AI classified ${analysis.incident.incident_type.toUpperCase()} as ${analysis.incident.severity.toUpperCase()}.`);

      setWorkflowStatus('MULTI-AGENT RESPONSE PLANNING');
      const orchestration = await api.orchestrateIncident(incidentId);
      if (runId !== workflowRun.current) return;
      setIncidents((previous) => upsertIncident(previous, orchestration.incident));
      setAssignedResources(orchestration.mcp_resources?.map((resource) => resource.resource_id) || []);
      addClientTimelineEvent(incidentId, 'resources_verified', `${orchestration.mcp_resources?.length || 0} campus resources identified for response.`);

      setWorkflowStatus('RESPONSE PLAN GENERATED');
      const plan = await api.generateResponsePlan(incidentId);
      if (runId !== workflowRun.current) return;
      setResponsePlan(plan);
      addClientTimelineEvent(incidentId, 'response_plan_generated_client', 'Response plan generated from existing AI recommendations.');

      setWorkflowStatus('COMMAND AUTHORIZATION');
      const approvedPlan = await api.decideApproval(plan.plan_id, {
        decision: 'approve',
        operator_name: 'Demo Safety Commander',
        notes: 'Authorized in DEMO MODE for judge demonstration; provider delivery remains optional.',
      });
      setResponsePlan(approvedPlan);
      addClientTimelineEvent(incidentId, 'approval_granted_client', 'Demo commander authorized the response plan.');

      setWorkflowStatus('RESPONSE DISPATCH IN PROGRESS');
      const dispatch = await api.executeDispatch(plan.plan_id);
      setAssignedResources(dispatch.dispatched_resources || []);
      addClientTimelineEvent(incidentId, 'dispatch_started_client', `${dispatch.dispatched_resources?.length || 0} responders/resources assigned.`);
      const now = new Date();
      setDemoPushVisible(true);
      addTimelineEvent({
        event_name: 'demo_push_displayed',
        incident_id: incidentId,
        timestamp: now.toISOString(),
        time_display: now.toLocaleTimeString(),
        description: 'DEMO PUSH — IN APP displayed. No external mobile delivery claimed.',
      });
      setWorkflowStatus('RESPONSE IN PROGRESS');
      await fetchTelemetry();
    } catch (error: any) {
      setWorkflowStatus('WORKFLOW ATTENTION REQUIRED');
      setWorkflowError(error.message || 'The live response workflow could not complete.');
      await fetchTelemetry();
    }
  }, [addTimelineEvent, fetchTelemetry]);

  const handleIncidentCreated = (newIncident: Incident) => {
    setIncidents((previous) => upsertIncident(previous, newIncident));
    setActiveTab('overview');
    addClientTimelineEvent(newIncident.incident_id, 'incident_reported_client', `Incident reported at ${newIncident.location}.`);
    void runEmergencyWorkflow(newIncident);
  };

  const handleSelectIncident = (incident: Incident) => {
    setCommandIncidentId(incident.incident_id);
    setActiveTab('overview');
  };

  const handleResolveIncident = async (incident: Incident) => {
    try {
      setWorkflowStatus('RESOLVING INCIDENT');
      const resolved = await api.resolveIncident(incident.incident_id, 'Situation confirmed under control by the campus operator.');
      setIncidents((previous) => upsertIncident(previous, resolved));
      setDemoPushVisible(false);
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
      <Header health={health} loading={loading} onRefresh={fetchTelemetry} wsState={wsState} user={user} onLogout={() => console.log('Logout clicked')} />
      <div className="main-body">
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
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
              demoPushVisible={demoPushVisible}
              wsState={wsState}
              operatorLocation={operatorLocation}
              onClientEvent={addTimelineEvent}
              onGpsLocation={setOperatorLocation}
              onResolveIncident={handleResolveIncident}
              onViewResponsePlan={() => setActiveTab('responses')}
            />
          )}
          {activeTab === 'incidents' && <IncidentsPage incidents={incidents} loading={loading} onOpenReportModal={() => setIsReportModalOpen(true)} onRefresh={fetchTelemetry} />}
          {activeTab === 'resources' && <ResourcesPage />}
          {activeTab === 'responses' && <ResponsesPage />}
          {activeTab === 'activity' && <ActivityPage />}
        </main>
      </div>
      <ReportEmergencyModal isOpen={isReportModalOpen} onClose={() => setIsReportModalOpen(false)} onIncidentCreated={handleIncidentCreated} />
    </div>
  );
};

export default App;
