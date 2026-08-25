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

import { useEffect, useMemo, useRef, useState } from 'react';
import { AgentCard } from './AgentCard';
import { APPROVAL_AGENT_KEY, HUMAN_RESPONSE_TEAMS, VISUAL_AGENTS } from './agentCatalog';
import { STATUS_VISUALS, deriveAgentDisplayStatus, humanTeamVisual } from './agentStatus';
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

export interface CommandCenter3DProps {
  /** The REAL, currently-focused incident workflow state (from Phase 2). */
  incident?: IncidentWorkflowState;
  /** Whether the operator's live WebSocket is connected (for the status dot). */
  connected?: boolean;
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

export default function CommandCenter3D({ incident, connected }: CommandCenter3DProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<CommandCenterSceneHandle | null>(null);
  const [webglOk, setWebglOk] = useState<boolean>(() => isWebGLAvailable());
  const [selectedAgentKey, setSelectedAgentKey] = useState<string | null>(null);

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

  const humanCards = useMemo(() => HUMAN_RESPONSE_TEAMS.map((team) => {
    const assignment = incident?.assignments?.[team.department];
    const visual = humanTeamVisual(assignment?.status, team.accent);
    return {
      ...team,
      status: visual.status,
      message: assignment ? `${assignment.status}${assignment.assignedResources.length ? ` · ${assignment.assignedResources.join(', ')}` : ''}` : 'No assignment yet',
      active: ['WORKING', 'COMPLETED'].includes(visual.status) && assignment?.status !== 'COMPLETED',
    };
  }), [incident]);

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
          <div style={{ width: '100%', marginTop: '0.6rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.6rem' }}>
            {humanCards.map((team) => (
              <div key={team.key} style={{ pointerEvents: 'auto' }}>
                <AgentCard
                  title={team.title}
                  subtitle={team.subtitle}
                  accent={team.accent}
                  status={team.status}
                  message={team.message}
                  active={team.active}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
