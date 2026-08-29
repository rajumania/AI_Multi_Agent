import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, Clock3, HeartPulse, MapPin, RefreshCw, ShieldCheck, Thermometer, Users } from 'lucide-react';
import { api } from '../services/api';
import { LiveEvent } from '../types';

export type OperationalView = 'alerts' | 'rescue' | 'shelters' | 'sensors' | 'monitoring';

interface Props {
  view: OperationalView;
  liveEvents?: LiveEvent[];
}

const titleFor: Record<OperationalView, string> = {
  alerts: 'Alerts',
  rescue: 'Rescue Requests',
  shelters: 'Shelters & Hospitals',
  sensors: 'Sensor Dashboard',
  monitoring: 'Monitoring',
};

const pretty = (value: unknown) => String(value ?? 'No data available').replace(/_/g, ' ');
const when = (value: unknown) => value ? new Date(String(value)).toLocaleString() : 'No timestamp available';
const statusColor = (value: unknown) => {
  const status = String(value || '').toLowerCase();
  if (status.includes('critical') || status.includes('offline')) return '#dc2626';
  if (status.includes('warning') || status.includes('high') || status.includes('pending')) return '#d97706';
  if (status.includes('available') || status.includes('normal') || status.includes('approved')) return '#047857';
  return '#475569';
};

function State({ loading, error, empty }: { loading: boolean; error: string | null; empty: boolean }) {
  if (loading) return <div className="panel-card" style={{ padding: '2.5rem', textAlign: 'center', color: '#64748b' }}>Loading current disaster-response data…</div>;
  if (error) return <div className="panel-card" style={{ padding: '1rem', color: '#991b1b', background: '#fef2f2', borderColor: '#fecaca' }}><AlertTriangle size={16} /> {error}</div>;
  if (empty) return <div className="panel-card" style={{ padding: '2.5rem', textAlign: 'center', color: '#64748b' }}>No data available from the response database.</div>;
  return null;
}

export const OperationalDataPage: React.FC<Props> = ({ view, liveEvents = [] }) => {
  const [data, setData] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSensor, setSelectedSensor] = useState<any | null>(null);
  const [approvalAction, setApprovalAction] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (view === 'alerts') setData({ alerts: await api.getNotifications() });
      if (view === 'rescue') setData({ requests: await api.getRescueRequests() });
      if (view === 'shelters') {
        const [shelters, hospitals] = await Promise.all([api.getShelters(), api.getHospitals()]);
        setData({ shelters, hospitals });
      }
      if (view === 'sensors') {
        const [status, observations, events] = await Promise.all([api.getSensorStatus(), api.getSensors(), api.getSensorEvents()]);
        setData({ status, observations, events });
        setSelectedSensor((current: any | null) => current ? status.find((item) => item.sensor_id === current.sensor_id) || current : null);
      }
      if (view === 'monitoring') {
        const [health, incidents, sensors, risks, plans, approvals, alerts, runs] = await Promise.all([
          api.getHealth(), api.getIncidents(), api.getSensorStatus(), api.getRiskPredictions(), api.getResponsePlans(), api.getPendingApprovals(), api.getNotifications(), api.getAgentRuns(),
        ]);
        setData({ health, incidents, sensors, risks, plans, approvals, alerts, runs });
      }
      setError(null);
    } catch (err: any) {
      setError(err?.message || 'The response data could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, [view]);

  useEffect(() => { void load(); const timer = window.setInterval(() => void load(), 10000); return () => window.clearInterval(timer); }, [load]);
  const latestEvent = liveEvents.find((event) => ['sensor_update', 'environment_anomaly', 'sensor_correlated', 'event_fused', 'risk_updated', 'community_alert', 'notification_created', 'replan_triggered', 'response_plan_updated', 'agent_started', 'agent_completed', 'agent_failed'].includes(event.event_name));
  useEffect(() => { if (latestEvent) void load(); }, [latestEvent?.timestamp]);

  const decidePlan = async (planId: string, decision: 'approve' | 'reject') => {
    setApprovalAction(`${planId}:${decision}`);
    setError(null);
    try {
      await api.decideApproval(planId, { decision, operator_name: 'Authenticated Department Approver' });
      await load();
    } catch (err: any) {
      setError(err?.message || 'Approval decision failed. The backend rejected the action.');
    } finally {
      setApprovalAction(null);
    }
  };

  const content = useMemo(() => {
    if (view === 'alerts') return <div className="operational-card-grid">{(data.alerts || []).map((alert: any) => <article className="panel-card" key={alert.id} style={{ borderLeft: `4px solid ${statusColor(alert.level)}` }}><div className="panel-title"><AlertTriangle size={16} /> {alert.title}</div><p>{alert.message}</p><small>{pretty(alert.level).toUpperCase()} · {when(alert.created_at)}{alert.incident_id ? ` · ${alert.incident_id}` : ''}</small></article>)}</div>;
    if (view === 'rescue') return <div className="operational-card-grid">{(data.requests || []).map((request: any) => <article className="panel-card" key={request.request_id} style={{ borderLeft: `4px solid ${statusColor(request.hazard_level)}` }}><div className="panel-title"><ShieldCheck size={16} /> {request.request_id} <span className="status-pill" style={{ marginLeft: 'auto', color: statusColor(request.hazard_level) }}>{pretty(request.hazard_level).toUpperCase()}</span></div><div className="data-row"><MapPin size={14} /> {request.location}</div><div className="data-row"><Users size={14} /> {request.people_count} people · {request.injured_count} injured</div><div className="data-row"><Clock3 size={14} /> {when(request.created_at)}</div><p>{request.description}</p><small>Priority score: {request.priority_score == null ? 'No data available' : request.priority_score} · Status: {pretty(request.status)} · Assigned team: No data available</small></article>)}</div>;
    if (view === 'shelters') return <div className="operational-card-grid">{[...(data.shelters || []).map((item: any) => ({ ...item, category: 'Shelter' })), ...(data.hospitals || []).map((item: any) => ({ ...item, category: 'Hospital' }))].map((item: any) => <article className="panel-card" key={`${item.category}-${item.resource_id}`} style={{ borderTop: `3px solid ${item.category === 'Hospital' ? '#dc2626' : '#0d9488'}` }}><div className="panel-title">{item.category === 'Hospital' ? <HeartPulse size={16} /> : <ShieldCheck size={16} />} {item.name}</div><div className="data-row"><MapPin size={14} /> {item.location}</div><div className="data-row">Status: <strong style={{ color: statusColor(item.availability_status) }}>{pretty(item.availability_status).toUpperCase()}</strong></div><div className="data-row">Capacity: {item.capacity ?? 'No data available'} · Emergency beds: {item.emergency_beds ?? 'No data available'}</div><small>Safety status: {item.availability_status === 'available' ? 'AVAILABLE' : 'REVIEW REQUIRED'} · Distance: No data available</small></article>)}</div>;
    if (view === 'sensors') return <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 300px', gap: '1rem' }}><div className="operational-card-grid">{(data.status || []).map((sensor: any) => <button type="button" className="panel-card sensor-card" key={sensor.sensor_id} onClick={() => setSelectedSensor(sensor)} style={{ textAlign: 'left', borderLeft: `4px solid ${statusColor(sensor.status)}` }}><div className="panel-title"><Thermometer size={16} /> {sensor.sensor_id}<span className="status-pill" style={{ marginLeft: 'auto', color: statusColor(sensor.status) }}>{sensor.status}</span></div><div className="data-row">{pretty(sensor.sensor_type)} · {sensor.value} {sensor.unit || ''}</div><div className="data-row"><MapPin size={14} /> {sensor.location || sensor.zone_id || 'No location available'}</div><small>Threshold: {sensor.threshold ?? 'No data available'} · Updated: {when(sensor.received_at)}</small></button>)}</div><aside className="panel-card" style={{ padding: '1rem' }}><div className="panel-title"><Activity size={16} /> Sensor detail</div>{selectedSensor ? <><h3>{selectedSensor.sensor_id}</h3><div className="data-row">Location: {selectedSensor.location || selectedSensor.zone_id}</div><div className="data-row">Current value: {selectedSensor.value} {selectedSensor.unit || ''}</div><div className="data-row">Previous value: {selectedSensor.previous_value ?? 'No data available'}</div><div className="data-row">Warning threshold: {selectedSensor.warning_threshold ?? 'No data available'}</div><div className="data-row">Critical threshold: {selectedSensor.threshold ?? 'No data available'}</div><div className="data-row">Anomaly/status: {selectedSensor.status}</div><div className="data-row">Last update: {when(selectedSensor.received_at)}</div></> : <p>Select a sensor to inspect its latest reading.</p>}</aside></div>;
    const monitoring = data;
    const active = (monitoring.incidents || []).filter((item: any) => !['resolved', 'closed'].includes(item.status));
    const critical = (monitoring.risks || []).filter((item: any) => ['critical', 'high'].includes(String(item.risk_level).toLowerCase()));
    const recentRuns = monitoring.runs || [];
    return <div className="operational-card-grid"><article className="panel-card"><div className="panel-title"><Activity size={16} /> Live response state</div><div className="monitoring-metrics"><strong>{active.length}<small>Active disasters</small></strong><strong>{critical.length}<small>High/critical risks</small></strong><strong>{(monitoring.sensors || []).filter((item: any) => item.status !== 'NORMAL').length}<small>Sensor conditions</small></strong><strong>{(monitoring.alerts || []).length}<small>Alerts</small></strong></div><small>Backend: {monitoring.health?.status || 'No data available'} · Database: {monitoring.health?.database || 'No data available'}</small></article><article className="panel-card"><div className="panel-title"><AlertTriangle size={16} /> Current risk & freshness</div>{critical.slice(0, 5).map((risk: any) => <div className="data-row" key={`${risk.zone_id}-${risk.disaster_type}`}><strong>{risk.zone || risk.zone_id}</strong>: {risk.risk_score}/100 · {pretty(risk.risk_level)} · confidence {risk.confidence}% · {risk.stale ? 'STALE' : 'fresh'}</div>)}{critical.length === 0 && <p>No high or critical risk prediction available.</p>}</article><article className="panel-card"><div className="panel-title"><ShieldCheck size={16} /> Human approval & re-planning</div><div className="data-row">Response plans: {(monitoring.plans || []).length} · Recent re-plans: {liveEvents.filter((event) => event.event_name === 'replan_triggered').length}</div>{(monitoring.approvals || []).slice(0, 3).map((plan: any) => <div className="data-row" key={plan.plan_id} style={{ display: 'flex', gap: '.45rem', alignItems: 'center', flexWrap: 'wrap' }}><span><strong>{plan.plan_id}</strong> · {pretty(plan.severity)} · {plan.location}</span><button className="btn btn-sm btn-outline" disabled={!!approvalAction} onClick={() => void decidePlan(plan.plan_id, 'approve')}>{approvalAction === `${plan.plan_id}:approve` ? 'Approving…' : 'Approve'}</button><button className="btn btn-sm btn-outline" disabled={!!approvalAction} onClick={() => void decidePlan(plan.plan_id, 'reject')}>{approvalAction === `${plan.plan_id}:reject` ? 'Rejecting…' : 'Reject'}</button></div>)}{!(monitoring.approvals || []).length && <p>No pending human approval.</p>}<small>Department users can decide only plans routed to their own department; physical dispatch remains separately authorized.</small></article><article className="panel-card"><div className="panel-title"><Activity size={16} /> AI orchestration runs</div>{recentRuns.slice(0, 5).map((run: any) => <div className="data-row" key={run.run_id}><strong>{run.run_id}</strong> · {pretty(run.status)} · {run.required_agents?.length || 0} stages · {when(run.created_at)}</div>)}{recentRuns.length === 0 && <p>No data available for recent orchestration runs.</p>}<small>Agent lifecycle cards in the 3D command center update from the same WebSocket events.</small></article></div>;
  }, [data, liveEvents, selectedSensor, view]);

  return <div className="app-content"><div className="dashboard-title-row"><div><h2>{titleFor[view]}</h2><p>Current backend-connected disaster intelligence data. Missing values are shown explicitly.</p></div><button className="btn btn-outline" onClick={() => void load()} disabled={loading}><RefreshCw size={15} className={loading ? 'spin' : ''} /> Refresh</button></div><State loading={loading} error={error} empty={!loading && !error && (view === 'alerts' ? !data.alerts?.length : view === 'rescue' ? !data.requests?.length : view === 'shelters' ? !data.shelters?.length && !data.hospitals?.length : view === 'sensors' ? !data.status?.length : !data.incidents?.length && !data.risks?.length)} />{!loading && !error && content}</div>;
};
