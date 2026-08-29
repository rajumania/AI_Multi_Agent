import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, MapPin, Navigation, Send, ShieldCheck } from 'lucide-react';
import { api } from '../services/api';
import { Incident, RiskSummary, TravelSafetyResponse } from '../types';
import { DisasterRiskMap } from './DisasterRiskMap';

export const CommunitySafetyPanel: React.FC<{ incidents: Incident[]; refreshKey?: number }> = ({ incidents, refreshKey = 0 }) => {
  const [risk, setRisk] = useState<RiskSummary | null>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [destination, setDestination] = useState('');
  const [travel, setTravel] = useState<TravelSafetyResponse | null>(null);
  const [rescue, setRescue] = useState({ location: '', description: '', people_count: 1, injured_count: 0 });
  const [rescueStatus, setRescueStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const [riskData, alertData] = await Promise.all([api.getRiskSummary(), api.getNearbyAlerts()]);
      setRisk(riskData);
      setAlerts(alertData);
      setError(null);
    } catch (err: any) {
      setError(err?.message || 'Community safety data is unavailable.');
    }
  };

  useEffect(() => { void load(); }, [refreshKey]);

  const submitRescue = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!rescue.description.trim()) { setRescueStatus('Describe who needs help and what is happening.'); return; }
    try {
      const created = await api.createRescueRequest({ ...rescue, hazard_level: 'unknown' });
      setRescueStatus(`Rescue request ${created.request_id} received. Priority will be calculated by the response service.`);
      setRescue((current) => ({ ...current, description: '' }));
    } catch (err: any) { setRescueStatus(err?.message || 'Rescue request could not be submitted.'); }
  };

  const checkTravel = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!destination.trim()) { setError('Enter a destination or exact coordinates before checking travel safety.'); return; }
    try { setTravel(await api.checkTravelSafety(destination)); setError(null); } catch (err: any) { setError(err?.message || 'Travel safety check failed.'); }
  };

  const latest = risk?.latest;
  return <div style={{ display: 'grid', gap: '1rem', marginTop: '1.25rem' }}>
    {error && <div className="alert-banner error"><AlertTriangle size={16} /> {error}</div>}
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
      <section className="panel-card" style={{ padding: '1rem' }}><div className="panel-title"><ShieldCheck size={16} /> Nearby risk</div>{latest ? <><strong style={{ fontSize: '1.5rem' }}>{latest.risk_score.toFixed(2)} / 100</strong><div style={{ color: latest.risk_level === 'critical' ? '#dc2626' : '#d97706', fontWeight: 800 }}>{latest.risk_level.toUpperCase()}</div><small>Confidence {latest.confidence}% · {latest.stale ? 'STALE' : latest.data_status}</small></> : <p>No risk prediction available.</p>}</section>
      <section className="panel-card" style={{ padding: '1rem' }}><div className="panel-title"><AlertTriangle size={16} /> Zone alerts</div>{alerts.length ? alerts.slice(0, 4).map((alert) => <div className="data-row" key={alert.id}><AlertTriangle size={13} /> {alert.title}</div>) : <p>No current community alerts.</p>}</section>
      <section className="panel-card" style={{ padding: '1rem' }}><div className="panel-title"><Navigation size={16} /> Tourist Safety</div><form onSubmit={checkTravel} style={{ display: 'flex', gap: '.4rem', marginTop: '.65rem' }}><input className="form-input" value={destination} onChange={(event) => setDestination(event.target.value)} aria-label="Travel destination" /><button className="btn btn-primary" type="submit">Check</button></form>{travel && <div style={{ marginTop: '.6rem', color: travel.recommendation === 'CRITICAL' ? '#dc2626' : '#334155' }}><strong>{travel.recommendation}</strong> · {travel.risk_score}/100<p style={{ margin: '.25rem 0', fontSize: '.78rem' }}>{travel.reasons.join(' ')}</p></div>}</section>
    </div>
    <section className="panel-card" style={{ padding: '1rem' }}><div className="panel-title"><Send size={16} /> Rescue Request</div><form onSubmit={submitRescue} style={{ display: 'grid', gridTemplateColumns: 'minmax(160px, 1fr) 90px 90px', gap: '.55rem', marginTop: '.7rem' }}><input className="form-input" value={rescue.location} onChange={(event) => setRescue({ ...rescue, location: event.target.value })} aria-label="Rescue location" placeholder="Location" /><input className="form-input" type="number" min="1" value={rescue.people_count} onChange={(event) => setRescue({ ...rescue, people_count: Number(event.target.value) })} aria-label="People affected" /><input className="form-input" type="number" min="0" value={rescue.injured_count} onChange={(event) => setRescue({ ...rescue, injured_count: Number(event.target.value) })} aria-label="Injured people" /><textarea className="form-textarea" style={{ gridColumn: '1 / -1' }} value={rescue.description} onChange={(event) => setRescue({ ...rescue, description: event.target.value })} placeholder="Who needs rescue? Include any medical or vulnerability details." required /><button className="btn btn-danger" type="submit" style={{ justifySelf: 'start' }}>Send Rescue Request</button></form>{rescueStatus && <div style={{ marginTop: '.6rem', color: '#334155' }}><CheckCircle2 size={14} /> {rescueStatus}</div>}</section>
    <section><div className="panel-title" style={{ marginBottom: '.6rem' }}><MapPin size={16} /> Live disaster map</div><DisasterRiskMap incidents={incidents} /></section>
  </div>;
};
