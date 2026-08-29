// ---------------------------------------------------------------------------
// Command Center 3D — React host for the 3D agent scene (Phase 3).
//
// DEFAULT EXPORT + the lazy/code-split target: importing this module is what
// pulls in three.js, so it must only ever be reached through React.lazy (see
// CommandCenter3DLazy.tsx) and never on the login/signup path (Rules 24–26).
//
// Responsibilities (presentation only — the backend stays the source of truth):
//   * create the imperative three.js scene against a container ref and dispose
//     it on unmount (Phase 15 cleanup),
//   * push the latest REAL incident workflow state into the scene each time it
//     changes (the scene renders it; it never drives the workflow),
//   * overlay a reusable AgentCard per visual agent, each showing the status
//     DERIVED from real backend events,
//   * degrade gracefully to a DOM-only card view when WebGL is unavailable or
//     scene creation throws — the feature keeps working, just without 3D.
// ---------------------------------------------------------------------------

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Activity, AlertTriangle, Clock3, Database, Radio, Route, ShieldAlert, Wifi, WifiOff } from 'lucide-react';
import { AgentCard } from './AgentCard';
import { APPROVAL_AGENT_KEY, VISUAL_AGENTS } from './agentCatalog';
import { STATUS_VISUALS, deriveAgentDisplayStatus } from './agentStatus';
import {
  createCommandCenterScene,
  isWebGLAvailable,
  type CommandCenterSceneHandle,
} from './CommandCenterScene';
import {
  derivePhase,
  workflowProgress,
  type IncidentWorkflowState,
} from '../realtime/workflowReducer';
import { api } from '../services/api';
import type { LiveEvent } from '../types';

export interface CommandCenter3DProps {
  /** The REAL, currently-focused incident workflow state (from Phase 2). */
  incident?: IncidentWorkflowState;
  /** Whether the operator's live WebSocket is connected (for the status dot). */
  connected?: boolean;
  /** The same real event stream already owned by App.tsx (no second socket). */
  liveEvents?: LiveEvent[];
}

type ProviderHealth = {
  provider?: string;
  status?: string;
  last_success?: string | null;
  last_failure?: string | null;
  last_latency_ms?: number | null;
  freshness_seconds?: number | null;
  source?: string;
  failure_count?: number;
};

type SensorSnapshot = {
  sensor_id?: string;
  sensor_type?: string;
  value?: number;
  unit?: string;
  status?: string;
  source?: string;
  location?: string;
  zone_id?: string;
  received_at?: string;
  observed_at?: string;
  age_seconds?: number;
  threshold?: number;
};

type RiskSnapshot = {
  zone?: string;
  zone_id?: string;
  disaster_type?: string;
  risk_score?: number;
  risk_level?: string;
  confidence?: number;
  stale?: boolean;
  data_status?: string;
  created_at?: string;
  data_freshness_seconds?: number | null;
};

type PlanSnapshot = {
  plan_id?: string;
  severity?: string;
  location?: string;
  approval_status?: string;
  incident_id?: string;
};

type CommandTelemetry = {
  providers: ProviderHealth[];
  sensors: SensorSnapshot[];
  risks: RiskSnapshot[];
  plans: PlanSnapshot[];
  alerts: Array<{ id?: number; level?: string; title?: string; created_at?: string }>;
  resources: Array<{ status?: string; availability_status?: string }>;
};

const emptyTelemetry: CommandTelemetry = { providers: [], sensors: [], risks: [], plans: [], alerts: [], resources: [] };

const pretty = (value: unknown) => String(value ?? 'No data available').replace(/_/g, ' ');
const shortTime = (value: unknown) => value ? new Date(String(value)).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'No timestamp';
const ageLabel = (value: unknown) => {
  if (value == null || !Number.isFinite(Number(value))) return 'No freshness';
  const seconds = Math.max(0, Number(value));
  if (seconds < 60) return `${Math.round(seconds)}s ago`;
  return `${Math.round(seconds / 60)}m ago`;
};

function providerBadge(provider: ProviderHealth): { label: string; color: string } {
  const status = String(provider.status || '').toUpperCase();
  if (status === 'HEALTHY' || status === 'LIVE') return { label: 'LIVE', color: '#34d399' };
  if (status.includes('FALLBACK')) return { label: 'FALLBACK', color: '#fbbf24' };
  if (status.includes('STALE')) return { label: 'STALE', color: '#fb923c' };
  if (status.includes('FAIL') || status.includes('OFFLINE')) return { label: 'OFFLINE', color: '#f87171' };
  return { label: status || 'UNKNOWN', color: '#94a3b8' };
}

function sourceBadge(source: unknown): { label: string; color: string } {
  const value = String(source || '').toUpperCase();
  if (!value) return { label: 'UNKNOWN', color: '#94a3b8' };
  if (value.includes('DEMO')) return { label: 'FALLBACK', color: '#fbbf24' };
  if (value.includes('OFFLINE')) return { label: 'OFFLINE', color: '#f87171' };
  return { label: 'LIVE', color: '#34d399' };
}

function riskColor(level: unknown): string {
  const value = String(level || '').toLowerCase();
  if (value === 'critical') return '#fb7185';
  if (value === 'high') return '#fb923c';
  if (value === 'medium') return '#facc15';
  return '#34d399';
}

function useCommandTelemetry(liveEvents: LiveEvent[]) {
  const [telemetry, setTelemetry] = useState<CommandTelemetry>(emptyTelemetry);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const results = await Promise.allSettled([
      api.getProviderHealth(),
      api.getSensorStatus(),
      api.getRiskPredictions(),
      api.getResponsePlans(),
      api.getNotifications(),
      api.getResources(),
    ]);
    const value = (index: number): any[] => results[index].status === 'fulfilled' && Array.isArray(results[index].value) ? results[index].value : [];
    const failures = results.filter((result) => result.status === 'rejected').length;
    setTelemetry({ providers: value(0), sensors: value(1), risks: value(2), plans: value(3), alerts: value(4), resources: value(5) });
    setError(failures === results.length ? 'Command telemetry is unavailable.' : failures ? 'Some telemetry sources are unavailable.' : null);
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 15000);
    return () => window.clearInterval(timer);
  }, [load]);

  const latestEvent = liveEvents.find((event) => ['sensor_anomaly', 'evidence_received', 'image_analysis_started', 'image_analysis_completed', 'evidence_fused', 'risk_updated', 'departments_targeted', 'department_tasks_dispatched', 'notification_created', 'notification_delivered', 'notification_read', 'notification_failed', 'response_plan_generated', 'approval_required', 'approval_approved', 'replan_triggered', 'monitoring_started'].includes(event.event_name));
  useEffect(() => {
    if (latestEvent) void load();
  }, [latestEvent?.timestamp, load]);

  return { telemetry, loading, error };
}

const PHASE_LABELS: Record<string, string> = {
  idle: 'Standing by',
  analyzing: 'Analyzing incident',
  coordinating: 'Coordinating responders',
  synthesizing: 'Synthesizing plan',
  planned: 'Plan ready',
  awaiting_approval: 'Awaiting approval',
  approved: 'Approved',
  rejected: 'Rejected',
  dispatched: 'Dispatched',
  resolved: 'Resolved',
  attention: 'Needs attention',
};

export default function CommandCenter3D({ incident, connected, liveEvents = [] }: CommandCenter3DProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<CommandCenterSceneHandle | null>(null);
  const [webglOk, setWebglOk] = useState<boolean>(() => isWebGLAvailable());
  const [selectedAgentKey, setSelectedAgentKey] = useState<string | null>(null);
  const { telemetry, loading: telemetryLoading, error: telemetryError } = useCommandTelemetry(liveEvents);

  // Create / dispose the 3D scene. Re-runs only if WebGL availability flips.
  useEffect(() => {
    if (!webglOk) return;
    const el = containerRef.current;
    if (!el) return;

    let handle: CommandCenterSceneHandle | null = null;
    try {
      handle = createCommandCenterScene(el, (key) => {
        setSelectedAgentKey(key);
      });
      sceneRef.current = handle;
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn('[command3d] WebGL scene unavailable, using DOM fallback', err);
      setWebglOk(false);
      return;
    }

    return () => {
      handle?.dispose();
      sceneRef.current = null;
    };
  }, [webglOk]);

  // Feed the latest REAL state into the scene whenever it changes.
  useEffect(() => {
    sceneRef.current?.setIncident(incident);
  }, [incident]);

  // Sync selection to the 3D scene.
  useEffect(() => {
    sceneRef.current?.setSelectedAgent(selectedAgentKey);
  }, [selectedAgentKey]);

  const phase = incident ? derivePhase(incident) : 'idle';
  const progress = incident ? Math.round(workflowProgress(incident) * 100) : 0;
  const activeRisks = useMemo(
    () => [...telemetry.risks].sort((a, b) => Number(b.risk_score || 0) - Number(a.risk_score || 0)).slice(0, 3),
    [telemetry.risks],
  );
  const focusedPlan = useMemo(
    () => telemetry.plans.find((plan) => plan.incident_id === incident?.incidentId) || telemetry.plans[0],
    [incident?.incidentId, telemetry.plans],
  );
  const recentEvents = liveEvents.slice(0, 5);
  const onlineSensors = telemetry.sensors.filter((sensor) => !['OFFLINE', 'UNAVAILABLE'].includes(String(sensor.status || '').toUpperCase())).length;
  const criticalAlerts = telemetry.alerts.filter((alert) => ['critical', 'high'].includes(String(alert.level || '').toLowerCase())).length;
  const pendingPlans = telemetry.plans.filter((plan) => String(plan.approval_status || '').toLowerCase() === 'pending').length;

  const cards = useMemo(() => {
    return VISUAL_AGENTS.map((agent) => {
      const status = deriveAgentDisplayStatus(incident, agent.key);
      const node = incident?.agents[agent.key];
      const message =
        node?.message ??
        (agent.key === APPROVAL_AGENT_KEY && incident?.approval.required
          ? incident.approval.message
          : undefined);
      return {
        key: agent.key,
        title: agent.title,
        subtitle: agent.subtitle,
        accent: agent.accent,
        status,
        message,
        output: node?.output,
        active: status === 'WORKING' || status === 'WAITING_APPROVAL',
        selected: selectedAgentKey === agent.key,
      };
    });
  }, [incident, selectedAgentKey]);

  const selectedAgentInfo = useMemo(() => {
    if (!selectedAgentKey) return null;
    const agent = VISUAL_AGENTS.find((a) => a.key === selectedAgentKey);
    if (!agent) return null;
    const status = deriveAgentDisplayStatus(incident, agent.key);
    const node = incident?.agents[agent.key];
    const message =
      node?.message ??
      (agent.key === APPROVAL_AGENT_KEY && incident?.approval.required
        ? incident.approval.message
        : undefined);
    return {
      ...agent,
      status,
      message,
      startedAt: node?.startedAt,
      completedAt: node?.completedAt,
      output: node?.output,
      error: node?.error,
    };
  }, [incident, selectedAgentKey]);

  return (
    <div className="command-center-3d" style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '540px', gap: '0.75rem' }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.75rem',
        }}
      >
        <div>
          <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            AI Command Center
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
            Live multi-agent response — driven by real backend events
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            <span
              className={connected ? 'pulse' : undefined}
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: connected ? 'var(--success-500)' : '#94a3b8',
                display: 'inline-block',
              }}
            />
            {connected ? 'Live' : 'Offline'}
          </span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            {incident ? (
              <>
                Incident <strong style={{ color: 'var(--text-primary)' }}>{incident.incidentId}</strong> · {PHASE_LABELS[phase] ?? phase} · {progress}%
              </>
            ) : (
              'No active incident — nodes idle until a real incident arrives'
            )}
          </span>
        </div>
      </header>

      <section className="command-center-telemetry" aria-label="Current command telemetry">
        {[
          { label: 'ACTIVE INCIDENT', value: incident ? '1' : '0', icon: <ShieldAlert size={15} /> },
          { label: 'SENSORS ONLINE', value: telemetryLoading ? '…' : `${onlineSensors}/${telemetry.sensors.length || 0}`, icon: <Radio size={15} /> },
          { label: 'HIGH / CRITICAL', value: telemetryLoading ? '…' : String(activeRisks.filter((risk) => ['high', 'critical'].includes(String(risk.risk_level || '').toLowerCase())).length), icon: <Activity size={15} /> },
          { label: 'PENDING APPROVAL', value: telemetryLoading ? '…' : String(pendingPlans), icon: <AlertTriangle size={15} /> },
          { label: 'ALERTS', value: telemetryLoading ? '…' : String(criticalAlerts), icon: <Wifi size={15} /> },
        ].map((metric) => (
          <div className="command-center-metric" key={metric.label}>
            <span className="command-center-metric-icon">{metric.icon}</span>
            <span><strong>{metric.value}</strong><small>{metric.label}</small></span>
          </div>
        ))}
      </section>

      {telemetryError && (
        <div className="command-center-data-warning" role="status">
          <AlertTriangle size={14} /> {telemetryError} Values shown below are from the sources that responded.
        </div>
      )}

      <section className="command-center-provider-strip" aria-label="External data provider status">
        <div className="command-center-panel-heading"><Database size={14} /> DATA SOURCES</div>
        {telemetryLoading && <span className="command-center-empty">Checking provider health…</span>}
        {!telemetryLoading && telemetry.providers.length === 0 && <span className="command-center-empty">No provider status available</span>}
        {!telemetryLoading && telemetry.providers.slice(0, 6).map((provider, index) => {
          const badge = providerBadge(provider);
          return <span className="command-center-provider" key={`${provider.provider || provider.source}-${index}`}><strong>{pretty(provider.provider || provider.source)}</strong><em style={{ color: badge.color }}>● {badge.label}</em><small>{pretty(provider.source)} · {provider.last_latency_ms == null ? 'No latency' : `${provider.last_latency_ms}ms`} · {ageLabel(provider.freshness_seconds)}</small></span>;
        })}
      </section>

      {/* State legend so the color language is legible to operators/judges. */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
        {Object.values(STATUS_VISUALS).map((v) => (
          <span key={v.status} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.66rem', color: 'var(--text-muted)' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: v.color, display: 'inline-block' }} />
            {v.label}
          </span>
        ))}
      </div>

      <div
        className="command-center-stage"
        style={{
          position: 'relative',
          flex: 1,
          minHeight: '360px',
          borderRadius: '14px',
          overflow: 'hidden',
          border: '1px solid rgba(148, 163, 184, 0.18)',
          background: 'radial-gradient(circle at 50% 35%, #172033 0%, #0b1120 60%, #070b16 100%)',
        }}
      >
        {webglOk ? (
          <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} aria-label="3D agent command center" />
        ) : (
          <div
            style={{
              position: 'absolute',
              top: '0.75rem',
              left: '50%',
              transform: 'translateX(-50%)',
              fontSize: '0.7rem',
              color: '#cbd5e1',
              background: 'rgba(15, 23, 42, 0.7)',
              border: '1px solid rgba(148, 163, 184, 0.25)',
              borderRadius: '999px',
              padding: '0.25rem 0.7rem',
            }}
          >
            3D view unavailable on this device — showing live agent status
          </div>
        )}

        <aside className="command-center-stage-panel command-center-stage-panel-left" aria-label="Live sensor feed">
          <div className="command-center-panel-heading"><Radio size={14} /> LIVE SENSOR FEED</div>
          {telemetryLoading && <div className="command-center-empty">Loading sensor telemetry…</div>}
          {!telemetryLoading && telemetry.sensors.length === 0 && <div className="command-center-empty">No data available</div>}
          {!telemetryLoading && telemetry.sensors.slice(0, 4).map((sensor, index) => {
            const badge = sourceBadge(sensor.source);
            const status = String(sensor.status || 'UNKNOWN').toUpperCase();
            return (
              <div className="command-center-sensor-row" key={`${sensor.sensor_id}-${index}`}>
                <span className="command-center-sensor-dot" style={{ background: status === 'CRITICAL' ? '#fb7185' : status === 'WARNING' ? '#facc15' : '#34d399' }} />
                <span className="command-center-sensor-copy"><strong>{pretty(sensor.sensor_type)}</strong><small>{sensor.sensor_id || 'No sensor ID'} · {sensor.location || sensor.zone_id || 'No location'}</small></span>
                <span className="command-center-sensor-value"><strong>{sensor.value ?? '—'}</strong><small>{sensor.unit || ''}</small><em style={{ color: badge.color }}>{badge.label}</em></span>
              </div>
            );
          })}
        </aside>

        <aside className="command-center-stage-panel command-center-stage-panel-right" aria-label="Risk and response snapshot">
          <div className="command-center-panel-heading"><ShieldAlert size={14} /> RESPONSE SNAPSHOT</div>
          {activeRisks.length === 0 && <div className="command-center-empty">No data available</div>}
          {activeRisks.map((risk, index) => (
            <div className="command-center-risk-row" key={`${risk.zone_id || risk.zone}-${risk.disaster_type}-${index}`}>
              <div><strong>{pretty(risk.disaster_type)}</strong><small>{risk.zone || risk.zone_id || 'No affected zone'}</small></div>
              <div className="command-center-risk-score" style={{ color: riskColor(risk.risk_level) }}><strong>{risk.risk_score == null ? '—' : risk.risk_score.toFixed(2)}</strong><small>{pretty(risk.risk_level).toUpperCase()}</small></div>
              <span className="command-center-data-badge" style={{ color: sourceBadge(risk.data_status).color }}>{sourceBadge(risk.data_status).label}</span>
            </div>
          ))}
          <div className="command-center-plan-line"><Route size={13} /> {focusedPlan ? <span><strong>{pretty(focusedPlan.approval_status)}</strong> · {focusedPlan.location || 'No affected location'}</span> : 'No response plan available'}</div>
        </aside>

        {/* Selected Agent Details Panel Overlay (Futuristic EOC glass design) */}
        {selectedAgentInfo && (
          <div
            style={{
              position: 'absolute',
              top: '1rem',
              right: '1rem',
              bottom: '1rem',
              width: '340px',
              maxWidth: 'calc(100% - 2rem)',
              background: 'rgba(15, 23, 42, 0.82)',
              border: `1px solid ${selectedAgentInfo.accent}aa`,
              borderRadius: '12px',
              boxShadow: `0 8px 32px rgba(0, 0, 0, 0.65), 0 0 16px ${selectedAgentInfo.accent}22`,
              backdropFilter: 'blur(12px)',
              WebkitBackdropFilter: 'blur(12px)',
              zIndex: 10,
              padding: '1.25rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.85rem',
              color: '#cbd5e1',
              overflowY: 'auto',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <h4 style={{ fontSize: '0.95rem', fontWeight: 800, color: '#f8fafc', margin: 0 }}>
                  {selectedAgentInfo.title}
                </h4>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '0.15rem' }}>
                  {selectedAgentInfo.subtitle}
                </div>
              </div>
              <button
                type="button"
                aria-label="Close agent details"
                onClick={() => setSelectedAgentKey(null)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#94a3b8',
                  fontSize: '1.4rem',
                  cursor: 'pointer',
                  padding: '0 0.4rem',
                  lineHeight: 1,
                }}
              >
                &times;
              </button>
            </div>

            <hr style={{ border: '0', borderTop: '1px solid rgba(148, 163, 184, 0.18)', margin: 0 }} />

            <div>
              <div style={{ fontSize: '0.62rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8' }}>
                Status
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '0.25rem' }}>
                <span
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background: STATUS_VISUALS[selectedAgentInfo.status].color,
                    display: 'inline-block',
                    boxShadow: `0 0 8px ${STATUS_VISUALS[selectedAgentInfo.status].color}`,
                  }}
                />
                <span style={{ fontSize: '0.78rem', fontWeight: 700, color: STATUS_VISUALS[selectedAgentInfo.status].color }}>
                  {STATUS_VISUALS[selectedAgentInfo.status].label}
                </span>
              </div>
            </div>

            {selectedAgentInfo.message && (
              <div>
                <div style={{ fontSize: '0.62rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8' }}>
                  Current Activity
                </div>
                <div style={{ fontSize: '0.75rem', color: '#e2e8f0', marginTop: '0.25rem', lineHeight: 1.4, background: 'rgba(51, 65, 85, 0.25)', padding: '0.5rem', borderRadius: '6px', border: '1px solid rgba(148,163,184,0.1)' }}>
                  {selectedAgentInfo.message}
                </div>
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div>
                <div style={{ fontSize: '0.62rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8' }}>
                  Started At
                </div>
                <div style={{ fontSize: '0.72rem', color: '#e2e8f0', marginTop: '0.15rem' }}>
                  {selectedAgentInfo.startedAt ? new Date(selectedAgentInfo.startedAt).toLocaleTimeString() : 'N/A'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.62rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8' }}>
                  Completed At
                </div>
                <div style={{ fontSize: '0.72rem', color: '#e2e8f0', marginTop: '0.15rem' }}>
                  {selectedAgentInfo.completedAt ? new Date(selectedAgentInfo.completedAt).toLocaleTimeString() : 'N/A'}
                </div>
              </div>
            </div>

            {selectedAgentInfo.error && (
              <div style={{ background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.4)', borderRadius: '6px', padding: '0.5rem 0.65rem' }}>
                <div style={{ fontSize: '0.62rem', fontWeight: 700, color: '#ef4444', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Error Output
                </div>
                <div style={{ fontSize: '0.7rem', color: '#fca5a5', marginTop: '0.2rem', fontFamily: 'monospace' }}>
                  {selectedAgentInfo.error}
                </div>
              </div>
            )}

            {/* Resources Consulted */}
            <div>
              <div style={{ fontSize: '0.62rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8' }}>
                Resources Consulted
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginTop: '0.35rem' }}>
                {incident?.dispatch.resources && incident.dispatch.resources.length > 0 ? (
                  incident.dispatch.resources.map((res) => (
                    <span
                      key={res}
                      style={{
                        fontSize: '0.66rem',
                        background: 'rgba(51, 65, 85, 0.4)',
                        border: '1px solid rgba(148, 163, 184, 0.18)',
                        borderRadius: '4px',
                        padding: '0.1rem 0.35rem',
                        color: '#f8fafc',
                      }}
                    >
                      {res}
                    </span>
                  ))
                ) : (
                  <span style={{ fontSize: '0.7rem', color: '#64748b', fontStyle: 'italic' }}>
                    No assets dispatched yet
                  </span>
                )}
              </div>
            </div>

            {selectedAgentInfo.output && (
              <div>
                <div style={{ fontSize: '0.62rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8', marginBottom: '0.35rem' }}>
                  Structured Output
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', background: 'rgba(15, 23, 42, 0.45)', padding: '0.65rem', borderRadius: '6px', border: '1px solid rgba(148, 163, 184, 0.15)' }}>
                  {Object.entries(selectedAgentInfo.output).map(([key, val]) => (
                    <div key={key} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem' }}>
                      <span style={{ color: '#94a3b8' }}>{key.replace(/_/g, ' ')}:</span>
                      <span style={{ fontWeight: 700, color: '#f8fafc', textAlign: 'right' }}>
                        {typeof val === 'boolean' ? (val ? 'Yes' : 'No') : String(val)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* AgentCard overlay: cards capture pointer events; the empty stage
            around them stays draggable for orbiting the 3D scene. */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            display: 'flex',
            alignItems: webglOk ? 'flex-end' : 'center',
            padding: webglOk ? '0.9rem' : '2.6rem 0.9rem 0.9rem',
            overflowY: webglOk ? 'visible' : 'auto',
          }}
        >
          <div
            style={{
              width: '100%',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
              gap: '0.6rem',
            }}
          >
            {cards.map((c) => (
              <div key={c.key} style={{ pointerEvents: 'auto' }}>
                <AgentCard
                  title={c.title}
                  subtitle={c.subtitle}
                  accent={c.accent}
                  status={c.status}
                  message={c.message}
                  output={c.output}
                  active={c.active}
                  selected={c.selected}
                  onClick={() => setSelectedAgentKey(c.key === selectedAgentKey ? null : c.key)}
                />
              </div>
            ))}
          </div>
        </div>
      </div>

      <section className="command-center-event-rail" aria-label="Recent backend workflow events">
        <div className="command-center-panel-heading"><Clock3 size={14} /> REAL EVENT STREAM <span>{connected ? <><Wifi size={12} /> CONNECTED</> : <><WifiOff size={12} /> OFFLINE</>}</span></div>
        {recentEvents.length === 0 ? (
          <div className="command-center-empty">No workflow events received yet. Agent nodes remain idle until the backend emits a real event.</div>
        ) : (
          <div className="command-center-event-list">
            {recentEvents.map((event, index) => (
              <div className="command-center-event" key={`${event.event_name}-${event.timestamp}-${index}`}>
                <strong>{pretty(event.event_name).toUpperCase()}</strong>
                <span>{event.incident_id || 'system'}</span>
                <time dateTime={event.timestamp}>{shortTime(event.timestamp)}</time>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
