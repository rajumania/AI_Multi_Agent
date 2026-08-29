import React, { useEffect, useState } from 'react';
import { Activity, AlertTriangle, CheckCircle2, Clock3 } from 'lucide-react';
import { api } from '../services/api';
import { RiskSummary } from '../types';

const levelColor: Record<string, string> = { low: '#16a34a', medium: '#ca8a04', high: '#ea580c', critical: '#dc2626' };

export const RiskPanel: React.FC<{ refreshKey?: number }> = ({ refreshKey = 0 }) => {
  const [summary, setSummary] = useState<RiskSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    api.getRiskSummary().then((data) => { if (active) { setSummary(data); setError(null); } }).catch(() => { if (active) setError('Risk service is temporarily unavailable.'); });
    return () => { active = false; };
  }, [refreshKey]);
  const latest = summary?.latest;
  const color = levelColor[latest?.risk_level || 'low'] || '#64748b';
  return <section className="panel-card" aria-label="Disaster risk and early warning">
    <div className="panel-header"><div className="panel-title"><Activity size={16} /> AITAM DISASTER RISK</div><span className="panel-tag">{latest ? (latest.stale ? 'STALE DATA' : `${latest.data_status} DATA`) : 'NO PREDICTION'}</span></div>
    {!latest ? <div className="empty-timeline">{error || 'No risk prediction is available yet. Run a prediction or the DEMO flood scenario.'}</div> : <div style={{ padding: '18px 20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}><div><small>DISASTER / ZONE</small><h3 style={{ margin: '5px 0' }}>{latest.disaster_type.replace('_', ' ').toUpperCase()} — {latest.zone}</h3><span style={{ color: '#64748b' }}>{latest.explanation}</span></div><div style={{ minWidth: 150, textAlign: 'right' }}><small>RISK SCORE</small><div style={{ color, fontSize: 34, fontWeight: 800 }}>{Math.round(latest.risk_score)} <small>/ 100</small></div></div></div>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', margin: '18px 0' }}><span className="workflow-chip" style={{ color, borderColor: color }}>RISK {latest.risk_level.toUpperCase()}</span><span className="workflow-chip">CONFIDENCE {Math.round(latest.confidence)}%</span>{latest.stale ? <span className="workflow-chip"><Clock3 size={13} /> DATA STALE</span> : <span className="workflow-chip"><CheckCircle2 size={13} /> FRESHNESS OK</span>}{summary?.warning_status === 'CRITICAL' || summary?.warning_status === 'WARNING' ? <span className="workflow-chip" style={{ color: '#dc2626', borderColor: '#dc2626' }}><AlertTriangle size={13} /> EARLY WARNING ACTIVE</span> : null}</div>
      <div className="command-center-grid" style={{ gridTemplateColumns: '1fr 1fr', margin: 0 }}><div><small>CONTRIBUTING FACTORS</small>{latest.contributing_factors.map((factor) => <div key={factor} style={{ marginTop: 8 }}>• {factor}</div>)}</div><div><small>RECOMMENDED ACTIONS</small>{latest.recommendations.map((action) => <div key={action} style={{ marginTop: 8 }}>• {action}</div>)}</div></div>
      <div style={{ marginTop: 18 }}><small>RISK TREND</small><div style={{ display: 'flex', alignItems: 'end', gap: 5, height: 55, marginTop: 8 }}>{(summary?.trend || []).map((point) => <div key={point.prediction_id} title={`${point.risk_score}/100`} style={{ flex: 1, minWidth: 8, height: `${Math.max(8, point.risk_score)}%`, background: levelColor[point.risk_level] || '#64748b', borderRadius: '3px 3px 0 0' }} />)}</div></div>
    </div>}
  </section>;
};
