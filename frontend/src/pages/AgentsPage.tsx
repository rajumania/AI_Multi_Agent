import React from 'react';
import { Bot, Shield, HeartPulse, Truck, MessageSquare, CheckCircle2, Cpu, ArrowRight } from 'lucide-react';


export const AgentsPage: React.FC = () => {
  const agents = [
    {
      name: 'Supervisor AI Agent',
      icon: Bot,
      color: '#0284c7',
      role: 'Central Incident Classifier & Router',
      desc: 'Extracts incident type, severity, location, and preserves strict null casualty truth. Determines sub-agent delegation graph.',
      safeguard: 'Zero hallucination constraint: never defaults missing casualty data to 0.'
    },
    {
      name: 'Security Agent',
      icon: Shield,
      color: '#0284c7',
      role: 'Perimeter Lockdown & Threat Containment',
      desc: 'Calculates security perimeter radius, road lane closures, and CCTV isolation. Discovers active guards via MCP.',
      safeguard: 'Queries real SQLite security posts (e.g., SEC-001, SEC-002) and rejects busy units.'
    },
    {
      name: 'Medical Agent',
      icon: HeartPulse,
      color: '#0d9488',
      role: 'Triage Evaluation & Ambulance Staging',
      desc: 'Evaluates casualty count, alerts emergency rooms, and stages trauma responders near the incident perimeter.',
      safeguard: 'Strict casualty safety rule: unknown casualties trigger precautionary standby without inventing figures.'
    },
    {
      name: 'Transport Agent',
      icon: Truck,
      color: '#8b5cf6',
      role: 'Evacuation Logistics & Shuttle Dispatch',
      desc: 'Calculates transit rerouting, selects safe muster shelters (e.g. North Auditorium), and allocates evacuation vans.',
      safeguard: 'Grounds vehicle capacity in real MCP records (VEH-001, VEH-002).'
    },
    {
      name: 'Communication Agent',
      icon: MessageSquare,
      color: '#f59e0b',
      role: 'Multi-Channel Alert Dissemination',
      desc: 'Generates calibrated broadcast alerts for SMS, Mobile App Push, and public-address audio & digital signage.',
      safeguard: 'All high-priority broadcasts require human commander authorization before transmission.'
    },
  ];

  return (
    <div className="app-content">
      <div className="dashboard-title-row">
        <div>
          <h2>AI Multi-Agent Architecture & LangGraph Pipeline</h2>
          <p>Autonomous specialized emergency coordination governed by deterministic safety gates and zero-hallucination protocols.</p>
        </div>
      </div>

      {/* Architecture Flow Banner */}
      <div className="panel-card" style={{ marginBottom: '1.5rem', background: '#f8fafc', border: '1px solid #bae6fd' }}>
        <div className="panel-header" style={{ background: '#f0f9ff' }}>
          <div className="panel-title" style={{ color: '#0369a1' }}>
            <Cpu size={18} color="#0284c7" />
            <span>LangGraph Multi-Agent Execution State Machine</span>
          </div>
          <span className="panel-tag" style={{ background: '#e0f2fe', color: '#0369a1' }}>Deterministic Workflow</span>
        </div>
        <div className="panel-body" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', fontSize: '0.8125rem' }}>
            <div style={{ background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: '6px', padding: '0.5rem 0.75rem', fontWeight: 600, color: '#0284c7' }}>
              1. Incident Intake
            </div>
            <ArrowRight size={16} color="#94a3b8" />
            <div style={{ background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: '6px', padding: '0.5rem 0.75rem', fontWeight: 600, color: '#0284c7' }}>
              2. Supervisor AI
            </div>
            <ArrowRight size={16} color="#94a3b8" />
            <div style={{ background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: '6px', padding: '0.5rem 0.75rem', fontWeight: 600, color: '#0d9488' }}>
              3. Specialized Agents (Parallel)
            </div>
            <ArrowRight size={16} color="#94a3b8" />
            <div style={{ background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: '6px', padding: '0.5rem 0.75rem', fontWeight: 600, color: '#8b5cf6' }}>
              4. MCP Resource Grounding
            </div>
            <ArrowRight size={16} color="#94a3b8" />
            <div style={{ background: '#ffffff', border: '1px solid #cbd5e1', borderRadius: '6px', padding: '0.5rem 0.75rem', fontWeight: 600, color: '#16a34a' }}>
              5. Human Approval Gate
            </div>
          </div>
        </div>
      </div>

      {/* Agents Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.25rem' }}>
        {agents.map((ag) => {
          const Icon = ag.icon;
          return (
            <div key={ag.name} className="panel-card" style={{ display: 'flex', flexDirection: 'column' }}>
              <div className="panel-header" style={{ padding: '0.85rem 1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <div style={{ background: `${ag.color}15`, padding: '0.4rem', borderRadius: '6px', color: ag.color }}>
                    <Icon size={18} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: '0.9375rem', margin: 0, color: 'var(--text-primary)' }}>{ag.name}</h3>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{ag.role}</span>
                  </div>
                </div>
              </div>

              <div className="panel-body" style={{ padding: '1rem', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: 1.5, margin: '0 0 0.85rem' }}>
                  {ag.desc}
                </p>

                <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '4px', padding: '0.5rem', fontSize: '0.75rem', color: '#334155' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontWeight: 600, color: '#16a34a', marginBottom: '0.15rem' }}>
                    <CheckCircle2 size={13} />
                    <span>Safety Constraint:</span>
                  </div>
                  {ag.safeguard}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
