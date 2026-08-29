import React, { useState } from 'react';
import { AlertTriangle, CheckCircle2, Compass, RefreshCw, ShieldAlert } from 'lucide-react';
import { api } from '../services/api';
import { TravelSafetyResponse } from '../types';

export const TravelSafetyPage: React.FC = () => {
  const [destination, setDestination] = useState('AITAM institutional location');
  const [currentLocation, setCurrentLocation] = useState('');
  const [latitude, setLatitude] = useState('18.56517');
  const [longitude, setLongitude] = useState('84.19587');
  const [result, setResult] = useState<TravelSafetyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const check = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const parsedLatitude = latitude.trim() ? Number(latitude) : undefined;
      const parsedLongitude = longitude.trim() ? Number(longitude) : undefined;
      if ((parsedLatitude == null) !== (parsedLongitude == null) || (parsedLatitude != null && (!Number.isFinite(parsedLatitude) || !Number.isFinite(parsedLongitude)))) throw new Error('Enter both valid destination coordinates or leave both blank.');
      setResult(await api.checkTravelSafety(destination.trim(), currentLocation.trim() || undefined, parsedLatitude, parsedLongitude));
    } catch (err: any) {
      setError(err?.message || 'Unable to evaluate destination safety.');
    } finally {
      setLoading(false);
    }
  };

  const riskColor = result?.recommendation === 'SAFE' ? '#047857' : result?.recommendation === 'CAUTION' ? '#b45309' : '#b91c1c';

  return (
    <div className="app-content">
      <div className="dashboard-title-row">
        <div>
          <h2>Destination Safety</h2>
          <p>Decision-support travel guidance based on current evidence, active warnings, weather, and route conditions.</p>
        </div>
        <span className="demo-label">LIVE API · DEMO DATA CLEARLY LABELLED</span>
      </div>
      <section className="panel-card" style={{ padding: '1.25rem', maxWidth: 920 }}>
        <form onSubmit={check} style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr .7fr .7fr auto', gap: '.75rem', alignItems: 'end' }}>
          <label className="form-label">Destination<input className="form-input" value={destination} onChange={(e) => setDestination(e.target.value)} placeholder="Zone or region" required /></label>
          <label className="form-label">Current location (optional)<input className="form-input" value={currentLocation} onChange={(e) => setCurrentLocation(e.target.value)} placeholder="For route context" /></label>
          <label className="form-label">Latitude<input className="form-input" value={latitude} onChange={(e) => setLatitude(e.target.value)} placeholder="18.56517" inputMode="decimal" /></label>
          <label className="form-label">Longitude<input className="form-input" value={longitude} onChange={(e) => setLongitude(e.target.value)} placeholder="84.19587" inputMode="decimal" /></label>
          <button className="btn btn-primary" type="submit" disabled={loading}><RefreshCw size={15} className={loading ? 'spin' : ''} /> Check safety</button>
        </form>
        {error && <p style={{ color: '#b91c1c', marginTop: '1rem' }}><AlertTriangle size={15} style={{ verticalAlign: 'middle' }} /> {error}</p>}
      </section>
      {result && (
        <section className="panel-card" style={{ padding: '1.25rem', maxWidth: 920, marginTop: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
            <div><div className="panel-title"><Compass size={18} /> {result.destination}</div><small>Last updated {new Date(result.last_updated).toLocaleString()} · {result.data_status || 'UNKNOWN'} · {(result.data_sources || []).join(', ') || 'No provider source'}</small></div>
            <div style={{ color: riskColor, fontWeight: 800, letterSpacing: '.05em' }}><ShieldAlert size={18} style={{ verticalAlign: 'middle' }} /> {result.recommendation}</div>
          </div>
          <div className="stats-grid" style={{ marginTop: '1rem' }}>
            <div className="stat-card"><span>Risk score</span><strong>{Math.round(result.risk_score)} / 100</strong><small>{result.risk_level}</small></div>
            <div className="stat-card"><span>Route status</span><strong>{result.route_status}</strong></div>
            <div className="stat-card"><span>Active alerts</span><strong>{result.active_alerts.length}</strong></div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '1rem' }}>
            <div><h3>Why?</h3><ul>{result.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></div>
            <div><h3>Hazards & conditions</h3><p>{result.hazards.length ? result.hazards.join(' · ') : 'No specific hazard signal returned.'}</p><p style={{ marginTop: '.5rem' }}>{result.weather_summary}</p>{result.recommendation === 'SAFE' ? <p><CheckCircle2 size={15} /> Continue to monitor updates.</p> : <p style={{ color: '#b91c1c' }}><AlertTriangle size={15} /> Conditions can change; follow verified local guidance.</p>}</div>
          </div>
        </section>
      )}
    </div>
  );
};
