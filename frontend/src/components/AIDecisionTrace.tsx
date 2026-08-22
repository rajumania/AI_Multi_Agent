import React from 'react';
import { Brain, Cpu, ShieldCheck, HeartPulse, Truck, AlertCircle, Wrench, CheckCircle2, Clock } from 'lucide-react';

export interface DecisionTraceItem {
  timestamp: string;
  time_display: string;
  agent: string;
  action: string;
  thought?: string;
  task?: string;
  status?: string;
  result?: string;
  verified_resources?: string[] | string;
  recommendation?: string;
  tool_call?: any;
  confidence?: number;
  why?: string;
}

interface AIDecisionTraceProps {
  trace: DecisionTraceItem[];
  incidentId?: string;
}

export const AIDecisionTrace: React.FC<AIDecisionTraceProps> = ({ trace, incidentId }) => {
  const getAgentIcon = (agent: string) => {
    const a = agent.toLowerCase();
    if (a.includes('security')) return <ShieldCheck size={16} color="#3b82f6" />;
    if (a.includes('medical')) return <HeartPulse size={16} color="#10b981" />;
    if (a.includes('transport')) return <Truck size={16} color="#f59e0b" />;
    if (a.includes('supervisor')) return <Brain size={16} color="#a855f7" />;
    if (a.includes('severity') || a.includes('triage')) return <AlertCircle size={16} color="#ef4444" />;
    if (a.includes('monitoring')) return <Cpu size={16} color="#06b6d4" />;
    return <Cpu size={16} color="#64748b" />;
  };

  const normalizeAgentName = (name: string): string => {
    const uppercase = name.toUpperCase();
    if (!uppercase.includes('AGENT') && !uppercase.includes('ENGINE')) {
      return `${uppercase} AGENT`;
    }
    return uppercase;
  };

  const parseOperationalFields = (item: DecisionTraceItem) => {
    const agent = normalizeAgentName(item.agent || 'SYSTEM AGENT');
    const status = item.status ? item.status.toUpperCase() : 'COMPLETED';
    const task = item.task || item.action?.replace(/_/g, ' ') || 'Operational Assessment';

    // Build operational result from result field, or extract clean summary from thought
    let result = item.result;
    if (!result && item.thought) {
      // Filter out private chain-of-thought and convert to operational statement
      const cleanThought = item.thought
        .replace(/Querying MCP resource layer for closest guard squad to .*/, 'Queried MCP layer for closest guard squad.')
        .replace(/Assessing casualty risk and reserving nearest medical unit for triage.*/, 'Assessed casualty risk and reserved medical unit.')
        .replace(/Computing clear ingress corridor for dispatched emergency vehicles.*/, 'Computed ingress corridor for emergency transit.')
        .replace(/Received emergency intake at .*/, 'Received and validated incident intake parameters.')
        .replace(/Calculated threat score: .*/, 'Deterministic threat score evaluated and applied.');
      result = cleanThought;
    }

    // Extract verified resources if available
    let verifiedResources: string[] = [];
    if (item.verified_resources) {
      verifiedResources = Array.isArray(item.verified_resources)
        ? item.verified_resources
        : [item.verified_resources];
    } else if (item.tool_call) {
      const tc = item.tool_call;
      if (tc.result && typeof tc.result === 'object') {
        const rName = tc.result.name || tc.result.resource_id;
        const rStatus = tc.result.availability_status || 'AVAILABLE';
        if (rName) {
          verifiedResources.push(`${rName} (${rStatus.toUpperCase()})`);
        }
      } else if (tc.substituted_unit) {
        verifiedResources.push(`${tc.substituted_unit} AVAILABLE (Substituted for ${tc.replaced_unit})`);
      }
    }

    // Extract operational recommendation
    let recommendation = item.recommendation;
    if (!recommendation && item.why) {
      recommendation = item.why;
    }

    return {
      agent,
      status,
      task,
      result: result || 'Action executed successfully.',
      verifiedResources,
      recommendation,
      timeDisplay: item.time_display || (item.timestamp ? item.timestamp.split('T')[1]?.slice(0, 8) : ''),
      toolCall: item.tool_call
    };
  };

  return (
    <div style={{
      background: '#0f172a',
      color: '#f8fafc',
      borderRadius: '10px',
      padding: '1rem 1.25rem',
      boxShadow: '0 4px 16px rgba(15, 23, 42, 0.3)',
      fontFamily: 'Inter, system-ui, -apple-system, sans-serif'
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem', borderBottom: '1px solid #334155', paddingBottom: '0.65rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Brain size={18} color="#a855f7" />
          <span style={{ fontSize: '0.85rem', fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: '#f1f5f9' }}>
            LIVE AI AGENT ACTIVITY {incidentId ? `(${incidentId})` : ''}
          </span>
        </div>
        <span style={{ fontSize: '0.7rem', color: '#38bdf8', background: '#1e293b', border: '1px solid #334155', padding: '3px 10px', borderRadius: '12px', fontWeight: 600 }}>
          {trace.length} OPERATIONAL ACTIONS
        </span>
      </div>

      {trace.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '1.5rem 0', color: '#64748b', fontSize: '0.8rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem' }}>
          <Clock size={15} />
          <span>Awaiting real-time agent execution stream...</span>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '320px', overflowY: 'auto', paddingRight: '4px' }}>
          {trace.map((rawItem, idx) => {
            const op = parseOperationalFields(rawItem);
            const isCompleted = op.status === 'COMPLETED';
            const isFailed = op.status === 'FAILED';

            return (
              <div key={idx} style={{
                background: '#1e293b',
                borderRadius: '8px',
                padding: '0.75rem 0.85rem',
                borderLeft: `4px solid ${isCompleted ? '#10b981' : isFailed ? '#ef4444' : '#f59e0b'}`,
                fontSize: '0.78rem',
                lineHeight: 1.45,
                boxShadow: '0 2px 6px rgba(0,0,0,0.15)'
              }}>
                {/* Agent Header Row */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '0.35rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 700, color: '#f8fafc', letterSpacing: '0.02em' }}>
                    {getAgentIcon(op.agent)}
                    <span>{op.agent}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{
                      fontSize: '0.65rem',
                      fontWeight: 800,
                      padding: '2px 6px',
                      borderRadius: '4px',
                      background: isCompleted ? 'rgba(16, 185, 129, 0.15)' : isFailed ? 'rgba(239, 68, 68, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                      color: isCompleted ? '#34d399' : isFailed ? '#f87171' : '#fbbf24',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '3px'
                    }}>
                      {isCompleted && <CheckCircle2 size={11} />}
                      ✓ {op.status}
                    </span>
                    <span style={{ fontSize: '0.68rem', color: '#94a3b8', fontFamily: 'monospace' }}>
                      {op.timeDisplay}
                    </span>
                  </div>
                </div>

                {/* Task / Action */}
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.25rem', textTransform: 'capitalize' }}>
                  📋 <strong>Task:</strong> {op.task}
                </div>

                {/* Operational Result */}
                <div style={{ color: '#e2e8f0', marginBottom: '0.35rem', background: '#0f172a', padding: '0.4rem 0.6rem', borderRadius: '4px', border: '1px solid #334155' }}>
                  <strong>Result:</strong> {op.result}
                </div>

                {/* Verified Resources (if any) */}
                {op.verifiedResources.length > 0 && (
                  <div style={{ marginBottom: '0.35rem', background: 'rgba(16, 185, 129, 0.08)', padding: '0.35rem 0.6rem', borderRadius: '4px', border: '1px solid rgba(16, 185, 129, 0.2)', fontSize: '0.72rem', color: '#6ee7b7' }}>
                    <strong>Verified Resources:</strong>
                    <ul style={{ margin: '3px 0 0 1rem', padding: 0 }}>
                      {op.verifiedResources.map((res, i) => (
                        <li key={i}>{res}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Operational Recommendation */}
                {op.recommendation && (
                  <div style={{ fontSize: '0.72rem', color: '#38bdf8', background: 'rgba(14, 165, 233, 0.08)', padding: '0.35rem 0.6rem', borderRadius: '4px', border: '1px solid rgba(56, 189, 248, 0.2)' }}>
                    <strong>Recommendation:</strong> {op.recommendation}
                  </div>
                )}

                {/* Tool Activity */}
                {op.toolCall && (
                  <div style={{ marginTop: '0.35rem', background: '#090d16', padding: '0.3rem 0.5rem', borderRadius: '4px', border: '1px dashed #475569', fontSize: '0.68rem', color: '#a7f3d0', fontFamily: 'monospace' }}>
                    <Wrench size={11} style={{ display: 'inline', marginRight: '4px' }} />
                    <strong>MCP Tool:</strong> {op.toolCall.tool || op.toolCall.substituted_unit ? JSON.stringify(op.toolCall) : 'Executed'}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

