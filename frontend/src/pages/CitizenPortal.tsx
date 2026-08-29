import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  Clock,
  Bell,
  ArrowRight,
  BookOpen,
  MessageCircle,
  MapPin,
  Plus,
  Sparkles,
  ShieldCheck,
} from 'lucide-react';
import { PortalHeader } from '../components/PortalHeader';
import { ReportEmergencyModal } from '../components/ReportEmergencyModal';
import { api, appendWsToken } from '../services/api';
import { Incident } from '../types';
import { citizenProgress, PhaseState } from '../portal/incidentProgress';
import { PersonalAssistant } from '../components/PersonalAssistant';
import { OfflineStatus } from '../components/OfflineStatus';
import { CommunitySafetyPanel } from '../components/CommunitySafetyPanel';


const SEVERITY_COLORS: Record<string, string> = {
  critical: '#dc2626',
  high: '#ea580c',
  medium: '#ca8a04',
  low: '#0284c7',
  unknown: '#64748b',
};

function severityColor(sev?: string): string {
  return SEVERITY_COLORS[(sev || 'unknown').toLowerCase()] || '#64748b';
}

function formatTime(value?: string): string {
  if (!value) return '';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString();
}

function PhaseDot({ state }: { state: PhaseState }) {
  if (state === 'done') return <CheckCircle2 size={18} color="#16a34a" />;
  if (state === 'active')
    return <Circle size={18} color="#2563eb" className="pulse" style={{ fill: '#bfdbfe' }} />;
  return <Circle size={18} color="#cbd5e1" />;
}

// ---------------------------------------------------------------------------
// CitizenPortal (Increment 2). A community member can:
//   * Report an emergency (reuses the existing ReportEmergencyModal).
//   * See ONLY the incidents they themselves reported (the backend scopes
//     GET /incidents by the verified token — this list is not client-filtered).
//   * Track a simplified, agent-free progress timeline derived from status.
//   * Notifications & chatbot are clearly-labeled previews (no backend yet).
// It never shows internal agent reasoning, resource IDs, approvals, or the
// operator command console.
// ---------------------------------------------------------------------------
export const CitizenPortal: React.FC = () => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reportOpen, setReportOpen] = useState(false);
  const [notificationRefreshKey, setNotificationRefreshKey] = useState(0);
  const [assistantOpenRequest, setAssistantOpenRequest] = useState<{ id: number; prompt?: string }>();

  // Keep a ref of known incident IDs so the WS handler can check ownership
  // without a stale closure over the incidents array.
  const incidentIdsRef = useRef<Set<string>>(new Set());

  const fetchMine = useCallback(async () => {
    try {
      const mine = await api.getIncidents();
      const list = Array.isArray(mine) ? mine : [];
      setIncidents(list);
      incidentIdsRef.current = new Set(list.map((i) => i.incident_id));
    } catch {
      setIncidents([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Real backend-driven state: poll the citizen's own incidents so the progress
  // advances as the operator/agents move the incident forward (no fake timers).
  useEffect(() => {
    fetchMine();
    const interval = setInterval(fetchMine, 10000);
    const handleOnline = () => { void fetchMine(); };
    window.addEventListener('online', handleOnline);
    return () => { clearInterval(interval); window.removeEventListener('online', handleOnline); };
  }, [fetchMine]);

  // Phase 4B: Real-time WebSocket listener. The backend's event_visibility.py
  // already filters the WS stream so citizens only receive USER_SAFE_EVENTS for
  // their own incidents. When any arrive we immediately re-fetch so the progress
  // timeline advances in near-real-time without waiting for the 10-second poll.
  useEffect(() => {
    const base = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/^http/, 'ws');
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let reconnectDelay = 1500;
    let disposed = false;

    // Events the citizen is allowed to see (mirrors event_visibility.USER_SAFE_EVENTS).
    const USER_SAFE_EVENTS = new Set([
      'incident_created',
      'assessment_started',
      'incident_assessed',
      'assessment_failed',
      'incident_updated',
      'response_status_changed',
      'dispatch_started',
      'response_dispatched',
      'resource_dispatched',
      'vehicle_arrived',
      'route_selected',
      'vehicle_location_updated',
      'monitoring_started',
      'incident_resolved',
      'incident_closed',
      'in_app_alert_available',
      'notification_created',
    ]);

    const connect = () => {
      if (disposed) return;
      try {
        socket = new WebSocket(appendWsToken(`${base}/api/v1/events/ws`));
        socket.onopen = () => setNotificationRefreshKey((value) => value + 1);
        socket.onmessage = (msg) => {
          try {
            const data = JSON.parse(msg.data);
            const eventName: string = data.event_name || data.event || '';
            const incidentId: string = data.incident_id || '';
            // Only refresh if this is a safe event for one of this user's incidents.
            if (eventName === 'notification_created' && data.recipient_type === 'user' && data.notification_id) {
              setNotificationRefreshKey((value) => value + 1);
              if (socket?.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({ type: 'notification_delivered', notification_id: data.notification_id }));
              }
            }
            if (USER_SAFE_EVENTS.has(eventName) && incidentId && incidentIdsRef.current.has(incidentId)) {
              fetchMine();
            }
          } catch {
            // Ignore malformed frames.
          }
        };
        socket.onclose = () => {
          if (disposed) return;
          reconnectTimer = setTimeout(() => {
            reconnectDelay = Math.min(reconnectDelay * 2, 15000);
            connect();
          }, reconnectDelay);
        };
        socket.onerror = () => {
          socket?.close();
        };
      } catch {
        // WebSocket unavailable (e.g. backend offline) — polling continues.
      }
    };

    connect();
    return () => {
      disposed = true;
      if (reconnectTimer !== null) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [fetchMine]);

  const selected = useMemo(() => {
    if (selectedId) {
      const found = incidents.find((i) => i.incident_id === selectedId);
      if (found) return found;
    }
    return incidents[0] || null;
  }, [incidents, selectedId]);

  const progress = useMemo(() => citizenProgress(selected?.status), [selected?.status]);

  const handleCreated = (created: Incident) => {
    setIncidents((prev) => [created, ...prev.filter((i) => i.incident_id !== created.incident_id)]);
    setSelectedId(created.incident_id);
  };

  const openAssistant = (prompt?: string) => {
    setAssistantOpenRequest({ id: Date.now(), prompt });
  };

  return (
    <div className="citizen-portal" style={{ minHeight: '100vh', background: '#f1f5f9', fontFamily: 'Inter, sans-serif' }}>
      <OfflineStatus />
      <PortalHeader subtitle="Community Portal" accent="#0ea5e9" notificationRefreshKey={notificationRefreshKey} />

      <main className="citizen-portal-main" style={{ maxWidth: '1040px', margin: '0 auto', padding: '1.5rem 1rem 3rem' }}>
        {/* Hero / report action */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
            flexWrap: 'wrap',
            background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
            color: '#fff',
            borderRadius: '14px',
            padding: '1.25rem 1.5rem',
            marginBottom: '1.5rem',
          }}
        >
          <div>
            <h1 style={{ margin: 0, fontSize: '1.35rem', fontWeight: 800 }}>Stay safe in your community</h1>
            <p style={{ margin: '0.35rem 0 0', fontSize: '0.85rem', color: '#94a3b8' }}>
              Report an emergency and track its progress. Your reports are private to you and the
              community response team.
            </p>
          </div>
          <button
            onClick={() => setReportOpen(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.75rem 1.25rem',
              background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
              color: '#fff',
              border: 'none',
              borderRadius: '10px',
              fontWeight: 700,
              fontSize: '0.9rem',
              cursor: 'pointer',
              boxShadow: '0 6px 16px rgba(220, 38, 38, 0.35)',
            }}
          >
            <AlertTriangle size={18} />
            Report an Emergency
          </button>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.3fr)',
            gap: '1.25rem',
            alignItems: 'start',
          }}
        >
          {/* My reports */}
          <section
            style={{
              background: '#fff',
              border: '1px solid #e2e8f0',
              borderRadius: '12px',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                padding: '0.85rem 1rem',
                borderBottom: '1px solid #e2e8f0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <strong style={{ fontSize: '0.9rem', color: '#0f172a' }}>My Reports</strong>
              <button
                onClick={() => setReportOpen(true)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.3rem',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  color: '#0284c7',
                  background: 'transparent',
                  border: '1px solid #bae6fd',
                  borderRadius: '6px',
                  padding: '0.25rem 0.5rem',
                  cursor: 'pointer',
                }}
              >
                <Plus size={13} /> New
              </button>
            </div>

            <div style={{ maxHeight: '460px', overflowY: 'auto' }}>
              {loading ? (
                <div style={{ padding: '1.5rem', textAlign: 'center', color: '#94a3b8', fontSize: '0.85rem' }}>
                  Loading your reports…
                </div>
              ) : incidents.length === 0 ? (
                <div style={{ padding: '2rem 1.25rem', textAlign: 'center', color: '#64748b' }}>
                  <ShieldCheck size={28} color="#94a3b8" style={{ marginBottom: '0.5rem' }} />
                  <p style={{ margin: 0, fontSize: '0.85rem' }}>You haven't reported anything yet.</p>
                  <p style={{ margin: '0.25rem 0 0', fontSize: '0.78rem', color: '#94a3b8' }}>
                    If you see an emergency, use “Report an Emergency”.
                  </p>
                </div>
              ) : (
                incidents.map((inc) => {
                  const active = selected?.incident_id === inc.incident_id;
                  return (
                    <button
                      key={inc.incident_id}
                      onClick={() => setSelectedId(inc.incident_id)}
                      style={{
                        display: 'block',
                        width: '100%',
                        textAlign: 'left',
                        padding: '0.85rem 1rem',
                        border: 'none',
                        borderBottom: '1px solid #f1f5f9',
                        borderLeft: active ? '3px solid #0ea5e9' : '3px solid transparent',
                        background: active ? '#f0f9ff' : '#fff',
                        cursor: 'pointer',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#0f172a', textTransform: 'capitalize' }}>
                          {inc.incident_type} incident
                        </span>
                        <span
                          style={{
                            fontSize: '0.62rem',
                            fontWeight: 700,
                            color: '#fff',
                            background: severityColor(inc.severity),
                            padding: '0.1rem 0.45rem',
                            borderRadius: '999px',
                            textTransform: 'uppercase',
                          }}
                        >
                          {inc.severity}
                        </span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', marginTop: '0.3rem', color: '#64748b', fontSize: '0.75rem' }}>
                        <MapPin size={12} /> {inc.location}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', marginTop: '0.2rem', color: '#94a3b8', fontSize: '0.7rem' }}>
                        <Clock size={11} /> {formatTime(inc.created_at)}
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </section>

          {/* Right column: assistant + progress + previews */}
          <div style={{ display: 'grid', gap: '1.25rem' }}>
            <section className="citizen-assistant-card" aria-labelledby="citizen-assistant-title">
              <div className="citizen-assistant-card-glow" aria-hidden="true" />
              <div className="citizen-assistant-card-header">
                <div className="citizen-assistant-icon" aria-hidden="true"><Sparkles size={21} /></div>
                <div>
                  <div className="citizen-assistant-eyebrow">AITAM DISASTER RESPONSE AI</div>
                  <h2 id="citizen-assistant-title">Personal Safety Assistant</h2>
                </div>
                <span className="citizen-assistant-status"><span aria-hidden="true" /> Available</span>
              </div>

              <p className="citizen-assistant-description">
                Ask about community safety, emergency reporting, available resources, or preferences remembered for your account.
              </p>

              <div className="citizen-assistant-context" aria-label="Private assistant context">
                <ShieldCheck size={17} aria-hidden="true" />
                <div>
                  <strong>Recent conversation &amp; memory</strong>
                  <span>Continue your private conversation; preferences stay scoped to your authenticated member profile.</span>
                </div>
              </div>

              <button className="citizen-assistant-primary" type="button" onClick={() => openAssistant()}>
                Ask AITAM Safety AI <ArrowRight size={17} aria-hidden="true" />
              </button>

              <div className="citizen-assistant-quick-actions" aria-label="Assistant quick actions">
                <button type="button" onClick={() => openAssistant('I have a question about community safety.')}>
                  <MessageCircle size={15} aria-hidden="true" /> Ask a Safety Question
                </button>
                <button type="button" onClick={() => openAssistant('How do I report an emergency in my community?')}>
                  <AlertTriangle size={15} aria-hidden="true" /> How do I Report an Emergency?
                </button>
                <button type="button" onClick={() => openAssistant('Please share community safety information and available resources.')}>
                  <BookOpen size={15} aria-hidden="true" /> Community Safety Information
                </button>
              </div>

              <p className="citizen-assistant-disclaimer">
                For immediate danger, use <strong>Report an Emergency</strong>. This assistant supports your safety decisions but does not replace emergency services or response coordinators.
              </p>
            </section>

            <section style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.25rem' }}>
              <strong style={{ fontSize: '0.9rem', color: '#0f172a' }}>Progress</strong>
              {!selected ? (
                <p style={{ marginTop: '0.75rem', color: '#94a3b8', fontSize: '0.85rem' }}>
                  Select or file a report to see its progress here.
                </p>
              ) : (
                <>
                  <div
                    style={{
                      marginTop: '0.75rem',
                      padding: '0.75rem 0.9rem',
                      borderRadius: '10px',
                      background: progress.resolved ? '#f0fdf4' : progress.onHold ? '#fffbeb' : '#eff6ff',
                      border: `1px solid ${progress.resolved ? '#bbf7d0' : progress.onHold ? '#fde68a' : '#bfdbfe'}`,
                      color: '#0f172a',
                      fontSize: '0.83rem',
                      fontWeight: 600,
                    }}
                  >
                    {progress.headline}
                  </div>

                  <div style={{ marginTop: '0.4rem', fontSize: '0.72rem', color: '#94a3b8' }}>
                    Report ID <strong style={{ color: '#334155' }}>{selected.incident_id}</strong>
                  </div>

                  <ol style={{ listStyle: 'none', padding: 0, margin: '1rem 0 0' }}>
                    {progress.phases.map((phase, idx) => (
                      <li key={phase.key} style={{ display: 'flex', gap: '0.7rem', alignItems: 'flex-start' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                          <PhaseDot state={phase.state} />
                          {idx < progress.phases.length - 1 && (
                            <div
                              style={{
                                width: '2px',
                                height: '22px',
                                background: phase.state === 'done' ? '#16a34a' : '#e2e8f0',
                              }}
                            />
                          )}
                        </div>
                        <div style={{ paddingBottom: '0.6rem' }}>
                          <div
                            style={{
                              fontSize: '0.85rem',
                              fontWeight: phase.state === 'todo' ? 500 : 700,
                              color: phase.state === 'todo' ? '#94a3b8' : '#0f172a',
                            }}
                          >
                            {phase.label}
                          </div>
                        </div>
                      </li>
                    ))}
                  </ol>
                </>
              )}
            </section>

          <section style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1.1rem 1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Bell size={16} color="#0ea5e9" />
                <strong style={{ fontSize: '0.88rem', color: '#0f172a' }}>Notifications</strong>
              </div>
              <p style={{ margin: '0.6rem 0 0', fontSize: '0.8rem', color: '#64748b' }}>
                Status changes for your reports appear here in real time. Only safe updates for your
                own incidents are delivered.
              </p>
          </section>

        </div>
        </div>
        <CommunitySafetyPanel incidents={incidents} refreshKey={notificationRefreshKey} />
      </main>

      <ReportEmergencyModal
        isOpen={reportOpen}
        onClose={() => setReportOpen(false)}
        onIncidentCreated={handleCreated}
      />
      <PersonalAssistant openRequest={assistantOpenRequest} />
    </div>
  );
};
