import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { MapPin, Clock, Users, RefreshCw, Inbox, Activity, CheckCircle2, Check, X, Truck, CircleCheck } from 'lucide-react';
import { PortalHeader } from '../components/PortalHeader';
import { api, appendWsToken } from '../services/api';
import { DepartmentAlert, DepartmentVoiceAlerts } from '../components/DepartmentVoiceAlerts';
import { DepartmentAssignment, Incident, IncidentStatus, TransportTracking } from '../types';
import { DepartmentCode, departmentLabel } from '../auth/roles';
import { TransportResponseMap } from '../components/TransportResponseMap';

// Per-department accent (purely cosmetic; keeps the six portals distinguishable).
const DEPT_ACCENTS: Record<DepartmentCode, string> = {
  SECURITY: '#6366f1',
  MEDICAL: '#dc2626',
  TRANSPORT: '#0891b2',
  COMMUNICATION: '#7c3aed',
  FIRE: '#ea580c',
  FACILITIES: '#0d9488',
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#dc2626',
  high: '#ea580c',
  medium: '#ca8a04',
  low: '#0284c7',
  unknown: '#64748b',
};

// Mirror of the operator dashboard's status vocabulary so departments and the
// command center speak the same language (labels/colors kept consistent).
function statusDisplay(status: string): { label: string; color: string } {
  switch (status as IncidentStatus) {
    case 'reported':
      return { label: 'REPORTED', color: '#64748b' };
    case 'analyzing':
    case 'assessing':
      return { label: 'UNDER ASSESSMENT', color: '#0284c7' };
    case 'classified':
      return { label: 'ASSESSED', color: '#0284c7' };
    case 'response_planning':
    case 'planning':
      return { label: 'RESPONSE PLANNING', color: '#8b5cf6' };
    case 'awaiting_approval':
      return { label: 'AWAITING AUTHORIZATION', color: '#f59e0b' };
    case 'approved':
    case 'authorized':
      return { label: 'RESPONSE AUTHORIZED', color: '#10b981' };
    case 'in_progress':
    case 'response_in_progress':
    case 'dispatched':
      return { label: 'RESPONSE IN PROGRESS', color: '#dc2626' };
    case 'monitoring':
      return { label: 'MONITORING', color: '#0d9488' };
    case 'resolved':
      return { label: 'RESOLVED', color: '#16a34a' };
    case 'closed':
      return { label: 'CLOSED', color: '#475569' };
    case 'rejected':
      return { label: 'PLAN REJECTED', color: '#dc2626' };
    default:
      return { label: String(status || 'UNKNOWN').toUpperCase(), color: '#64748b' };
  }
}

function isResolved(status: string): boolean {
  return status === 'resolved' || status === 'closed';
}

function formatTime(value?: string): string {
  if (!value) return '';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString();
}

interface DepartmentPortalProps {
  department: DepartmentCode;
}

// ---------------------------------------------------------------------------
// DepartmentPortal (Increment 2) — one shared, parameterized portal for all six
// departments (SECURITY / MEDICAL / TRANSPORT / COMMUNICATION / FIRE /
// FACILITIES). Route guards + backend scoping guarantee a department only ever
// sees incidents routed to it: GET /incidents is scoped server-side by the
// verified token, so this list is NEVER client-filtered from a global feed.
//
// This is a responder FEED, not the operator command console: it shows the
// operational detail a responding team needs (status, severity, location,
// casualties, latest step) but exposes NO privileged command actions
// (approve / dispatch / resolve remain operator-only in the command center).
// ---------------------------------------------------------------------------
export const DepartmentPortal: React.FC<DepartmentPortalProps> = ({ department }) => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [assignments, setAssignments] = useState<DepartmentAssignment[]>([]);
  const [assignmentLoading, setAssignmentLoading] = useState<string | null>(null);
  const [teamInputs, setTeamInputs] = useState<Record<string, string>>({});
  const [transportResources, setTransportResources] = useState<any[]>([]);
  const [trackingByAssignment, setTrackingByAssignment] = useState<Record<number, TransportTracking | null>>({});
  const [notificationRefreshKey, setNotificationRefreshKey] = useState(0);
  const [urgentAlert, setUrgentAlert] = useState<DepartmentAlert | null>(null);

  const accent = DEPT_ACCENTS[department] || '#6366f1';
  const label = departmentLabel(department);

  const fetchScoped = useCallback(async () => {
    setRefreshing(true);
    try {
      const [rows, assignmentRows] = await Promise.all([api.getIncidents(), api.getMyAssignments()]);
      setIncidents(Array.isArray(rows) ? rows : []);
      setAssignments(Array.isArray(assignmentRows) ? assignmentRows : []);
      if (department === 'TRANSPORT') {
        const [resources, trackingEntries] = await Promise.all([
          api.getResources('vehicle').catch(() => []),
          Promise.all((Array.isArray(assignmentRows) ? assignmentRows : []).map(async (assignment) => {
            try {
              return [assignment.id, await api.getTransportTracking(assignment.id)] as const;
            } catch {
              return [assignment.id, null] as const;
            }
          })),
        ]);
        setTransportResources(Array.isArray(resources) ? resources.filter((resource) => String(resource.department || '').toUpperCase() === 'TRANSPORT') : []);
        setTrackingByAssignment(Object.fromEntries(trackingEntries));
      } else {
        setTransportResources([]);
        setTrackingByAssignment({});
      }
      setError(null);
    } catch {
      setError('Unable to load the incident feed. Retrying automatically…');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const assignmentFor = useCallback((incidentId: string) => assignments.find((item) => item.incident_id === incidentId), [assignments]);

  const handleAssignmentAction = useCallback(async (assignment: DepartmentAssignment, action: 'accept' | 'decline' | 'en-route' | 'on-scene' | 'completed') => {
    setAssignmentLoading(`${assignment.incident_id}:${action}`);
    setError(null);
    try {
      await api.updateAssignment(assignment.incident_id, department, action);
      await fetchScoped();
    } catch (err: any) {
      setError(err.message || 'Assignment action failed. The backend rejected the transition.');
    } finally {
      setAssignmentLoading(null);
    }
  }, [department, fetchScoped]);

  const handleTeamAssignment = useCallback(async (assignment: DepartmentAssignment) => {
    const rawTeam = (teamInputs[assignment.incident_id] || '').trim();
    const resourceIds = rawTeam.split(',').map((value) => value.trim()).filter(Boolean);
    if (!rawTeam) {
      setError('Enter a team name or resource IDs before assigning the team.');
      return;
    }
    setAssignmentLoading(`${assignment.incident_id}:team-assigned`);
    setError(null);
    try {
      const useResourceIds = resourceIds.length > 1 || rawTeam.includes(',') || /^[A-Za-z]+-\d+$/.test(rawTeam);
      await api.assignDepartmentTeam(assignment.incident_id, department, { resource_ids: useResourceIds ? resourceIds : [], team_name: useResourceIds ? undefined : rawTeam });
      await fetchScoped();
    } catch (err: any) {
      setError(err.message || 'Team assignment failed.');
    } finally {
      setAssignmentLoading(null);
    }
  }, [department, fetchScoped, teamInputs]);

  // Real backend-driven feed: poll so newly-routed incidents and status changes
  // appear without a manual reload (no simulated/fake progress).
  useEffect(() => {
    fetchScoped();
    const interval = setInterval(fetchScoped, 10000);
    return () => clearInterval(interval);
  }, [fetchScoped]);

  // The portal uses the existing authenticated event socket. Assignment and
  // targeted notification frames refresh persisted state immediately; the
  // ten-second poll remains only as reconciliation when a browser reconnects.
  useEffect(() => {
    const base = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/^http/, 'ws');
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let disposed = false;
    const connect = () => {
      if (disposed) return;
      socket = new WebSocket(appendWsToken(`${base}/api/v1/events/ws`));
      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data);
          const eventName = event.event_name || event.event || '';
          const eventDepartment = String(event.department || '').toUpperCase();
          if (eventName === 'notification_created' && event.recipient_type === 'department' && eventDepartment === department) {
            setNotificationRefreshKey((value) => value + 1);
            if (['critical', 'alert'].includes(String(event.level).toLowerCase())) {
              setUrgentAlert({ notificationId: event.notification_id, title: event.title || 'Department assignment received', message: event.message || 'Please review the new emergency assignment.', level: event.level || 'alert', incidentId: event.incident_id, department: eventDepartment });
            }
          }
          if (['department_notified', 'dept_assignment_accepted', 'dept_assignment_declined', 'dept_team_assigned', 'dept_en_route', 'dept_on_scene', 'dept_assignment_completed', 'transport_location_updated', 'transport_route_created', 'transport_route_updated', 'transport_eta_updated', 'transport_arrived'].includes(eventName) && eventDepartment === department) {
            void fetchScoped();
          }
        } catch { /* malformed frames are ignored; polling remains active */ }
      };
      socket.onclose = () => { if (!disposed) reconnectTimer = setTimeout(connect, 2000); };
      socket.onerror = () => socket?.close();
    };
    connect();
    return () => { disposed = true; if (reconnectTimer) clearTimeout(reconnectTimer); socket?.close(); };
  }, [department, fetchScoped]);

  const acknowledgeAlert = useCallback(() => {
    const notificationId = urgentAlert?.notificationId;
    setUrgentAlert(null);
    if (notificationId) void api.markNotificationRead(notificationId).catch(() => undefined);
  }, [urgentAlert]);

  const { active, resolved } = useMemo(() => {
    let a = 0;
    let r = 0;
    for (const inc of incidents) {
      if (isResolved(inc.status)) r += 1;
      else a += 1;
    }
    return { active: a, resolved: r };
  }, [incidents]);

  // Active incidents first, then most-recent first within each group.
  const ordered = useMemo(() => {
    return [...incidents].sort((x, y) => {
      const xr = isResolved(x.status) ? 1 : 0;
      const yr = isResolved(y.status) ? 1 : 0;
      if (xr !== yr) return xr - yr;
      return (y.created_at || '').localeCompare(x.created_at || '');
    });
  }, [incidents]);

  return (
    <div style={{ minHeight: '100vh', background: '#f1f5f9', fontFamily: 'Inter, sans-serif' }}>
      <PortalHeader subtitle={`${label} Portal`} accent={accent} badge={department} notificationRefreshKey={notificationRefreshKey} />

      <main className="department-portal-main" style={{ maxWidth: '1080px', margin: '0 auto', padding: '1.5rem 1rem 3rem' }}>
        <DepartmentVoiceAlerts alert={urgentAlert} onAcknowledge={acknowledgeAlert} />
        {/* Overview strip */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
            flexWrap: 'wrap',
            marginBottom: '1.25rem',
          }}
        >
          <div>
            <h1 style={{ margin: 0, fontSize: '1.3rem', fontWeight: 800, color: '#0f172a' }}>
              {label} — Incident Feed
            </h1>
            <p style={{ margin: '0.3rem 0 0', fontSize: '0.82rem', color: '#64748b' }}>
              Incidents routed to your department. You see only what your team is assigned to.
            </p>
          </div>
          <button
            onClick={fetchScoped}
            disabled={refreshing}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.5rem 0.9rem',
              background: '#fff',
              border: '1px solid #cbd5e1',
              borderRadius: '8px',
              color: '#334155',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: refreshing ? 'wait' : 'pointer',
            }}
          >
            <RefreshCw size={14} className={refreshing ? 'spin' : undefined} />
            Refresh
          </button>
        </div>

        {/* Stat cards */}
        <div className="department-stat-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.85rem', marginBottom: '1.5rem' }}>
          <StatCard icon={<Activity size={16} />} tone="#dc2626" label="Active" value={active} />
          <StatCard icon={<CheckCircle2 size={16} />} tone="#16a34a" label="Resolved" value={resolved} />
          <StatCard icon={<Inbox size={16} />} tone={accent} label="Total Assigned" value={incidents.length} />
        </div>

        {error && (
          <div
            style={{
              padding: '0.7rem 0.9rem',
              background: '#fef2f2',
              border: '1px solid #fecaca',
              borderRadius: '8px',
              color: '#b91c1c',
              fontSize: '0.8rem',
              marginBottom: '1rem',
            }}
          >
            {error}
          </div>
        )}

        {/* Incident feed */}
        {loading ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#94a3b8', fontSize: '0.9rem' }}>
            Loading your department feed…
          </div>
        ) : ordered.length === 0 ? (
          <div
            style={{
              padding: '3rem 1.5rem',
              textAlign: 'center',
              background: '#fff',
              border: '1px dashed #cbd5e1',
              borderRadius: '12px',
              color: '#64748b',
            }}
          >
            <Inbox size={32} color="#94a3b8" style={{ marginBottom: '0.6rem' }} />
            <p style={{ margin: 0, fontSize: '0.9rem', fontWeight: 600, color: '#334155' }}>
              No incidents routed to {label} right now.
            </p>
            <p style={{ margin: '0.3rem 0 0', fontSize: '0.8rem' }}>
              New incidents assigned to your department will appear here automatically.
            </p>
          </div>
        ) : (
          <div className="department-incident-list" style={{ display: 'grid', gap: '0.85rem' }}>
            {ordered.map((inc) => {
              const st = statusDisplay(inc.status);
              const sev = SEVERITY_COLORS[(inc.severity || 'unknown').toLowerCase()] || '#64748b';
              const done = isResolved(inc.status);
              const detail = inc.current_step || inc.summary || inc.next_action;
              const assignment = assignmentFor(inc.incident_id);
              return (
                <article className="department-incident-card"
                  key={inc.incident_id}
                  style={{
                    background: '#fff',
                    border: '1px solid #e2e8f0',
                    borderLeft: `4px solid ${done ? '#cbd5e1' : sev}`,
                    borderRadius: '12px',
                    padding: '1rem 1.15rem',
                    opacity: done ? 0.85 : 1,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.75rem', flexWrap: 'wrap' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.95rem', fontWeight: 800, color: '#0f172a', textTransform: 'capitalize' }}>
                        {inc.incident_type}
                      </span>
                      <span
                        style={{
                          fontSize: '0.6rem',
                          fontWeight: 700,
                          color: '#fff',
                          background: sev,
                          padding: '0.12rem 0.5rem',
                          borderRadius: '999px',
                          textTransform: 'uppercase',
                        }}
                      >
                        {inc.severity}
                      </span>
                    </div>
                    <span
                      style={{
                        fontSize: '0.62rem',
                        fontWeight: 800,
                        color: st.color,
                        background: `${st.color}18`,
                        border: `1px solid ${st.color}55`,
                        padding: '0.15rem 0.55rem',
                        borderRadius: '999px',
                        letterSpacing: '0.02em',
                      }}
                    >
                      {st.label}
                    </span>
                  </div>

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', marginTop: '0.6rem', color: '#475569', fontSize: '0.78rem' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                      <MapPin size={13} /> {inc.location}
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                      <Users size={13} /> {inc.injured_count === null || inc.injured_count === undefined ? 'Casualties unknown' : `${inc.injured_count} injured`}
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: '#94a3b8' }}>
                      <Clock size={12} /> {formatTime(inc.created_at)}
                    </span>
                  </div>

                  {inc.description && (
                    <p style={{ margin: '0.6rem 0 0', fontSize: '0.82rem', color: '#334155', lineHeight: 1.45 }}>
                      {inc.description}
                    </p>
                  )}

                  {detail && (
                    <div
                      style={{
                        marginTop: '0.6rem',
                        padding: '0.5rem 0.7rem',
                        background: '#f8fafc',
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px',
                        fontSize: '0.75rem',
                        color: '#475569',
                      }}
                    >
                      <span style={{ fontWeight: 700, color: '#334155' }}>Latest: </span>
                      {detail}
                    </div>
                  )}

                  {assignment && (
                    <>
                      <DepartmentAssignmentCard
                        assignment={assignment}
                        department={department}
                        transportResources={transportResources}
                        loadingAction={assignmentLoading}
                        teamValue={teamInputs[assignment.incident_id] || ''}
                        onTeamValueChange={(value) => setTeamInputs((previous) => ({ ...previous, [assignment.incident_id]: value }))}
                        onAction={handleAssignmentAction}
                        onAssignTeam={handleTeamAssignment}
                      />
                      {department === 'TRANSPORT' && (
                        <TransportResponseMap
                          assignment={assignment}
                          incident={inc}
                          tracking={trackingByAssignment[assignment.id] || null}
                        />
                      )}
                    </>
                  )}

                  <div style={{ marginTop: '0.6rem', fontSize: '0.65rem', color: '#94a3b8', letterSpacing: '0.02em' }}>
                    ID {inc.incident_id}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
};

function DepartmentAssignmentCard({
  assignment,
  department,
  transportResources,
  loadingAction,
  teamValue,
  onTeamValueChange,
  onAction,
  onAssignTeam,
}: {
  assignment: DepartmentAssignment;
  department: DepartmentCode;
  transportResources: any[];
  loadingAction: string | null;
  teamValue: string;
  onTeamValueChange: (value: string) => void;
  onAction: (assignment: DepartmentAssignment, action: 'accept' | 'decline' | 'en-route' | 'on-scene' | 'completed') => void;
  onAssignTeam: (assignment: DepartmentAssignment) => void;
}) {
  const busy = (action: string) => loadingAction === `${assignment.incident_id}:${action}`;
  const buttonStyle = (color: string) => ({ border: `1px solid ${color}66`, background: `${color}12`, color, borderRadius: 7, padding: '0.35rem 0.6rem', fontSize: '0.7rem', fontWeight: 700, cursor: 'pointer' });
  return (
    <div style={{ marginTop: '0.8rem', padding: '0.75rem', border: '1px solid #cbd5e1', borderRadius: 9, background: '#f8fafc' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.6rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Truck size={14} color="#334155" />
          <strong style={{ fontSize: '0.75rem', color: '#334155' }}>Department assignment</strong>
        </div>
        <span style={{ fontSize: '0.68rem', fontWeight: 800, color: assignment.status === 'DECLINED' ? '#dc2626' : assignment.status === 'COMPLETED' ? '#16a34a' : '#0369a1' }}>
          {assignment.status}
        </span>
      </div>
      <div style={{ marginTop: '0.35rem', fontSize: '0.68rem', color: '#64748b' }}>
        Last update: {formatTime(assignment.updated_at)}{assignment.responder ? ` · ${assignment.responder}` : ''}
      </div>
      {assignment.assigned_resources.length > 0 && (
        <div style={{ marginTop: '0.35rem', fontSize: '0.7rem', color: '#475569' }}>Team/resources: {assignment.assigned_resources.join(', ')}</div>
      )}
      <div className="department-assignment-actions" style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', flexWrap: 'wrap', marginTop: '0.6rem' }}>
        {assignment.status === 'NOTIFIED' && <>
          <button disabled={!!loadingAction} onClick={() => onAction(assignment, 'accept')} style={buttonStyle('#16a34a')}><Check size={12} /> {busy('accept') ? 'Accepting…' : 'ACCEPT'}</button>
          <button disabled={!!loadingAction} onClick={() => onAction(assignment, 'decline')} style={buttonStyle('#dc2626')}><X size={12} /> {busy('decline') ? 'Declining…' : 'DECLINE'}</button>
        </>}
        {assignment.status === 'ACCEPTED' && <>
          {department === 'TRANSPORT' ? (
            <select value={teamValue} onChange={(event) => onTeamValueChange(event.target.value)} aria-label="Assigned transport resource" style={{ flex: '1 1 190px', minWidth: 180, padding: '0.35rem 0.5rem', border: '1px solid #cbd5e1', borderRadius: 7, fontSize: '0.7rem', background: '#fff' }}>
              <option value="">Select assigned vehicle/resource</option>
              {transportResources.map((resource) => <option key={resource.resource_id} value={resource.resource_id}>{resource.resource_id} — {resource.name || 'Transport resource'}</option>)}
            </select>
          ) : (
            <input value={teamValue} onChange={(event) => onTeamValueChange(event.target.value)} placeholder="Team name or resource IDs" style={{ flex: '1 1 190px', minWidth: 180, padding: '0.35rem 0.5rem', border: '1px solid #cbd5e1', borderRadius: 7, fontSize: '0.7rem' }} />
          )}
          <button disabled={!!loadingAction} onClick={() => onAssignTeam(assignment)} style={buttonStyle('#7c3aed')}>{busy('team-assigned') ? 'Assigning…' : 'ASSIGN TEAM'}</button>
        </>}
        {assignment.status === 'TEAM_ASSIGNED' && <button disabled={!!loadingAction} onClick={() => onAction(assignment, 'en-route')} style={buttonStyle('#0284c7')}>{busy('en-route') ? 'Updating…' : 'SET EN ROUTE'}</button>}
        {assignment.status === 'EN_ROUTE' && <button disabled={!!loadingAction} onClick={() => onAction(assignment, 'on-scene')} style={buttonStyle('#0891b2')}>{busy('on-scene') ? 'Updating…' : 'SET ON SCENE'}</button>}
        {assignment.status === 'ON_SCENE' && <button disabled={!!loadingAction} onClick={() => onAction(assignment, 'completed')} style={buttonStyle('#16a34a')}><CircleCheck size={12} /> {busy('completed') ? 'Completing…' : 'COMPLETE'}</button>}
        {assignment.status === 'COMPLETED' && <span style={{ color: '#16a34a', fontSize: '0.72rem', fontWeight: 700 }}><CheckCircle2 size={13} style={{ verticalAlign: 'middle' }} /> Completed</span>}
        {assignment.status === 'DECLINED' && <span style={{ color: '#dc2626', fontSize: '0.72rem', fontWeight: 700 }}>Declined by department</span>}
      </div>
    </div>
  );
}

function StatCard({ icon, tone, label, value }: { icon: React.ReactNode; tone: string; label: string; value: number }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '0.9rem 1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: tone }}>
        {icon}
        <span style={{ fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.03em', color: '#64748b' }}>
          {label}
        </span>
      </div>
      <div style={{ marginTop: '0.35rem', fontSize: '1.6rem', fontWeight: 800, color: '#0f172a', lineHeight: 1 }}>
        {value}
      </div>
    </div>
  );
}
