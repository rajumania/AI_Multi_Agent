import React, { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import { AlertTriangle, Crosshair, Filter, Layers, MapPin, RefreshCw } from 'lucide-react';
import { Incident, LiveEvent, MapAlert, MapOverview, MapResource, MapRisk, MapSensor, MapZone } from '../types';
import { api } from '../services/api';
import { OperatorLocation } from './RealOperationsControls';
import { isValidGeoJSONGeometry } from './geojson';
import { readOfflineSnapshot, saveOfflineSnapshot } from '../services/offlineStore';

interface DisasterRiskMapProps {
  incidents?: Incident[];
  activeIncidentId?: string;
  onSelectIncident?: (incident: Incident) => void;
  liveEvents?: LiveEvent[];
  operatorLocation?: OperatorLocation | null;
}

const layerLabels: Record<string, string> = {
  risks: 'Disaster Risk', zones: 'Vulnerable Zones', hazards: 'Hazard Zones', sensors: 'Sensors',
  incidents: 'Incidents', rescue_requests: 'Rescue Requests', resources: 'Emergency Resources', shelters: 'Shelters',
  hospitals: 'Hospitals', emergency_services: 'Emergency Services', rescue_teams: 'Rescue Teams', vehicles: 'Vehicles',
  safe_routes: 'Safe Routes', blocked_routes: 'Blocked Routes', alerts: 'Community Alert Areas', tourist_safety: 'Tourist Safety',
};

const riskColor = (level: string) => ({ low: '#16a34a', medium: '#d97706', high: '#ea580c', critical: '#dc2626' }[String(level).toLowerCase()] || '#64748b');
const resourceColor = (type: string) => ({ shelter: '#0d9488', hospital: '#dc2626', ambulance: '#e11d48', rescue_team: '#2563eb', vehicle: '#7c3aed', boat: '#0891b2' }[type] || '#475569');
const escapeHtml = (value: unknown) => String(value ?? '—').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char] || char));
const point = (latitude?: number | null, longitude?: number | null): [number, number] | null => latitude != null && longitude != null && Number.isFinite(latitude) && Number.isFinite(longitude) ? [latitude, longitude] : null;

const popup = (title: string, rows: Record<string, unknown>) => `<strong>${escapeHtml(title)}</strong><div class="map-popup-details">${Object.entries(rows).map(([key, value]) => `<div><span>${escapeHtml(key.replace(/_/g, ' '))}</span><b>${escapeHtml(value)}</b></div>`).join('')}</div>`;

export const DisasterRiskMap: React.FC<DisasterRiskMapProps> = ({ incidents = [], activeIncidentId, onSelectIncident, liveEvents = [], operatorLocation }) => {
  const mapElement = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const groupsRef = useRef<Record<string, L.LayerGroup>>({});
  const userGroupRef = useRef<L.LayerGroup | null>(null);
  const [overview, setOverview] = useState<MapOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cachedAt, setCachedAt] = useState<string | null>(null);
  const [localUserLocation, setLocalUserLocation] = useState<OperatorLocation | null>(null);
  const [selected, setSelected] = useState<{ title: string; details: Record<string, unknown> } | null>(null);
  const [visible, setVisible] = useState<Record<string, boolean>>(() => Object.keys(layerLabels).reduce((acc, key) => ({ ...acc, [key]: true }), {}));
  const [filters, setFilters] = useState({ disaster_type: '', risk_level: '', region_id: '', zone_id: '', resource_status: '', sensor_status: '', alert_status: '' });

  const loadOverview = async () => {
    setLoading(true);
    const cacheKey = `map-overview:${JSON.stringify(filters)}`;
    try {
      const fresh = await api.getMapOverview(filters);
      setOverview(fresh);
      setCachedAt(null);
      setError(null);
      await saveOfflineSnapshot(cacheKey, fresh);
    } catch (err: any) {
      const cached = await readOfflineSnapshot<MapOverview>(cacheKey);
      if (cached) {
        setOverview(cached.value);
        setCachedAt(cached.cachedAt);
        setError(`Offline — showing map data saved ${new Date(cached.cachedAt).toLocaleString()}.`);
      } else setError(err?.message || 'Map data unavailable.');
    } finally { setLoading(false); }
  };

  useEffect(() => { void loadOverview(); }, [filters.disaster_type, filters.risk_level, filters.region_id, filters.zone_id, filters.resource_status, filters.sensor_status, filters.alert_status]);

  const latestMapEvent = liveEvents.find((event) => ['sensor_update', 'environment_anomaly', 'disaster_detected', 'risk_updated', 'resource_updated', 'community_alert', 'response_plan_updated', 'travel_risk_updated', 'replan_triggered'].includes(event.event_name));
  useEffect(() => { if (latestMapEvent) void loadOverview(); }, [latestMapEvent?.timestamp]);

  useEffect(() => {
    if (!mapElement.current || mapRef.current) return;
    const map = L.map(mapElement.current, { center: [0, 0], zoom: 2, zoomControl: true });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap contributors', maxZoom: 19 }).addTo(map);
    Object.keys(layerLabels).forEach((key) => { groupsRef.current[key] = L.layerGroup().addTo(map); });
    userGroupRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    window.setTimeout(() => map.invalidateSize(), 0);
    return () => { map.remove(); mapRef.current = null; groupsRef.current = {}; userGroupRef.current = null; };
  }, []);

  useEffect(() => {
    if (!mapRef.current || !overview) return;
    const candidate = [...incidents, ...(overview.incidents || [])].find((item: any) => Number.isFinite(Number(item.latitude)) && Number.isFinite(Number(item.longitude)));
    if (candidate) mapRef.current.setView([Number(candidate.latitude), Number(candidate.longitude)], 13);
  }, [overview, incidents]);

  useEffect(() => {
    const map = mapRef.current;
    const groups = groupsRef.current;
    if (!map || !overview) return;
    Object.values(groups).forEach((group) => group.clearLayers());
    const add = (key: string, layer: L.Layer) => { if (visible[key]) groups[key]?.addLayer(layer); };
    const addGeometry = (key: string, geometry: any, style: L.PathOptions, detail: Record<string, unknown>) => {
      if (!isValidGeoJSONGeometry(geometry)) return;
      const layer = L.geoJSON(geometry, { style }).bindPopup(popup(String(detail.name || detail.zone || key), detail));
      add(key, layer);
    };
    overview.risks.forEach((risk: MapRisk) => addGeometry('risks', risk.geometry, { color: riskColor(risk.risk_level), fillColor: riskColor(risk.risk_level), fillOpacity: .32, weight: 2 }, { zone: risk.zone, disaster_type: risk.disaster_type, risk: `${Math.round(risk.risk_score)}/100`, level: risk.risk_level, confidence: `${Math.round(risk.confidence)}%`, freshness: risk.stale ? 'STALE' : risk.data_freshness_seconds != null ? `${Math.round(risk.data_freshness_seconds / 60)} min` : 'unknown', evidence: risk.contributing_factors.join(', ') || 'No factors returned', source: risk.data_status || 'LIVE' }));
    overview.risks.forEach((risk: MapRisk) => addGeometry('tourist_safety', risk.geometry, { color: riskColor(risk.risk_level), fill: false, weight: 3, dashArray: '2 6' }, { zone: risk.zone, risk: `${Math.round(risk.risk_score)}/100`, level: risk.risk_level, guidance: risk.risk_level === 'critical' ? 'NOT RECOMMENDED' : 'Check current conditions' }));
    overview.zones.forEach((zone: MapZone) => addGeometry('zones', zone.geometry, { color: '#7c3aed', fillColor: '#a78bfa', fillOpacity: .08, weight: 1, dashArray: '4 4' }, { name: zone.name, population: zone.population, elevation: zone.elevation_m ? `${zone.elevation_m} m` : '—', slope: zone.slope_deg ? `${zone.slope_deg}°` : '—', vulnerability: zone.vulnerability_score, hazard: zone.hazard_classification, source: zone.geometry_source }));
    overview.hazards.forEach((hazard) => addGeometry('hazards', hazard.geometry, { color: '#be123c', fillColor: '#fb7185', fillOpacity: .15, weight: 2, dashArray: '6 4' }, { name: hazard.name, hazard_type: hazard.hazard_type, population: hazard.population, source: hazard.geometry_source }));
    overview.alerts.forEach((alert: MapAlert) => addGeometry('alerts', alert.geometry, { color: alert.level === 'critical' ? '#991b1b' : '#d97706', fillColor: alert.level === 'critical' ? '#ef4444' : '#fbbf24', fillOpacity: .12, weight: 2, dashArray: '3 5' }, { title: alert.title, level: alert.level, message: alert.message, created: alert.created_at, source: alert.is_demo ? 'DEMO/SIMULATION' : 'LIVE' }));
    overview.sensors.forEach((sensor: MapSensor) => { const p = point(sensor.latitude, sensor.longitude); if (!p) return; const marker = L.circleMarker(p, { radius: 8, color: sensor.status === 'CRITICAL' ? '#dc2626' : '#2563eb', fillColor: sensor.status === 'CRITICAL' ? '#ef4444' : '#60a5fa', fillOpacity: .9, weight: 2 }).bindPopup(popup(`Sensor ${sensor.sensor_id}`, { type: sensor.type, status: sensor.status, current: `${sensor.value} ${sensor.unit || ''}`, previous: sensor.previous_value == null ? '—' : sensor.previous_value, trend: sensor.trend, location: sensor.location, updated: sensor.last_update, source: sensor.source })); add('sensors', marker); });
    overview.incidents.forEach((incident) => { const p = point(incident.latitude, incident.longitude); if (!p) return; const marker = L.circleMarker(p, { radius: 9, color: riskColor(incident.risk_level), fillColor: riskColor(incident.risk_level), fillOpacity: .9 }).bindPopup(popup(incident.incident_id, { disaster_type: incident.disaster_type, risk: incident.risk_level, priority: incident.priority ?? '—', people_affected: incident.people_affected ?? '—', location: incident.location, status: incident.status, created: incident.created_at })); marker.on('click', () => { setSelected({ title: incident.incident_id, details: { disaster_type: incident.disaster_type, risk: incident.risk_level, location: incident.location, status: incident.status } }); const existing = incidents.find((item) => item.incident_id === incident.incident_id); if (existing) onSelectIncident?.(existing); }); add('incidents', marker); });
    overview.rescue_requests.forEach((request) => { const p = point(request.latitude, request.longitude); if (!p) return; const marker = L.circleMarker(p, { radius: 7, color: '#f97316', fillColor: '#fb923c', fillOpacity: .9 }).bindPopup(popup(request.request_id, { priority: `${request.priority_level} (${Math.round(request.priority_score || 0)})`, people: request.people_count, injured: request.injured_count, status: request.status, location: request.location })); add('rescue_requests', marker); });
    overview.resources.forEach((resource: MapResource) => { const p = point(resource.latitude, resource.longitude); if (!p) return; const marker = L.circleMarker(p, { radius: 7, color: resourceColor(resource.type), fillColor: resourceColor(resource.type), fillOpacity: .9, weight: 2 }).bindPopup(popup(resource.name, { type: resource.type, status: resource.status, capacity: resource.capacity ?? '—', occupied: resource.occupied ?? 'Not reported', assignment: resource.current_assignment || 'Unassigned', location: resource.location, contact: resource.contact || '—', source: resource.is_demo ? 'DEMO/SIMULATION' : 'LIVE' })); const resourceLayer = resource.type === 'shelter' ? 'shelters' : resource.type === 'hospital' || resource.type === 'clinic' || resource.type === 'medical_center' ? 'hospitals' : resource.type === 'rescue_team' ? 'rescue_teams' : resource.type === 'vehicle' || resource.type === 'ambulance' || resource.type === 'boat' ? 'vehicles' : resource.type === 'fire_service' || resource.type === 'fire_response' || resource.type === 'police' || resource.type === 'emergency_service' ? 'emergency_services' : 'resources'; add(resourceLayer, marker); });
    overview.routes.forEach((route) => { if (!isValidGeoJSONGeometry(route.geometry)) return; const color = route.status === 'blocked' ? '#dc2626' : '#16a34a'; const layer = L.geoJSON(route.geometry, { style: { color, weight: 5, dashArray: route.status === 'blocked' ? '8 7' : undefined, opacity: .88 } }).bindPopup(popup(route.status === 'blocked' ? 'Blocked Hazardous Route' : 'Verified Safe Route', { origin: route.origin, destination: route.destination, status: route.status, distance: route.distance_m ? `${Math.round(route.distance_m)} m` : '—', eta: route.eta_seconds ? `${Math.round(route.eta_seconds / 60)} min` : '—', source: route.geometry_source || 'LIVE' })); add(route.status === 'blocked' ? 'blocked_routes' : 'safe_routes', layer); });
    const boundsPoints: [number, number][] = [...overview.zones, ...overview.sensors, ...overview.resources].map((item: any) => point(item.latitude, item.longitude)).filter(Boolean) as [number, number][];
    if (activeIncidentId) { const active = overview.incidents.find((item) => item.incident_id === activeIncidentId); const activePoint = active && point(active.latitude, active.longitude); if (activePoint) map.setView(activePoint, 14); }
    else if (boundsPoints.length && !mapRef.current?.getBounds().isValid()) map.fitBounds(L.latLngBounds(boundsPoints), { padding: [30, 30], maxZoom: 12 });
  }, [overview, visible, activeIncidentId, incidents, onSelectIncident]);

  useEffect(() => { const group = userGroupRef.current; if (!group) return; group.clearLayers(); const current = operatorLocation || localUserLocation; const p = point(current?.latitude, current?.longitude); if (p) L.circleMarker(p, { radius: 8, color: '#111827', fillColor: '#facc15', fillOpacity: 1, weight: 3 }).bindPopup('Your current location (consent-based)').addTo(group); }, [operatorLocation, localUserLocation]);

  const activeRisks = useMemo(() => (overview?.risks || []).filter((risk) => ['high', 'critical'].includes(risk.risk_level.toLowerCase())).sort((a, b) => b.risk_score - a.risk_score), [overview]);
  const selectZone = (zone: MapZone) => { const p = point(zone.latitude, zone.longitude); if (p) mapRef.current?.setView(p, 12); };
  const useLocation = () => { if (!navigator.geolocation) { setError('Location is not supported by this browser.'); return; } navigator.geolocation.getCurrentPosition((position) => { const p: [number, number] = [position.coords.latitude, position.coords.longitude]; setLocalUserLocation({ latitude: p[0], longitude: p[1], timestamp: new Date().toISOString(), source: 'REAL' }); mapRef.current?.setView(p, 14); }, () => setError('Location permission was not granted.')); };

  return <section className="panel-card disaster-risk-map-card" style={{ overflow: 'hidden' }}>
    <div className="panel-header" style={{ flexWrap: 'wrap', gap: '.6rem' }}><div className="panel-title"><Layers size={18} /> DISASTER RISK MAP <span className="demo-label">{cachedAt ? 'CACHED / STALE' : overview?.data_status || 'LOADING'}</span></div><div style={{ display: 'flex', gap: '.45rem' }}><button className="btn btn-outline" onClick={() => void loadOverview()} disabled={loading}><RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh</button><button className="btn btn-outline" onClick={useLocation}><Crosshair size={14} /> Use my location</button></div></div>
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 270px' }}>
      <div className="disaster-risk-map-canvas" ref={mapElement} style={{ minHeight: 560, background: '#dbeafe' }} />
      <aside style={{ padding: '.8rem', background: '#f8fafc', borderLeft: '1px solid #e2e8f0', maxHeight: 560, overflowY: 'auto' }}>
        <div className="map-filter-heading"><Filter size={15} /> MAP FILTERS</div>
        {([['disaster_type', 'Disaster type'], ['risk_level', 'Risk level'], ['region_id', 'Region'], ['zone_id', 'Zone'], ['resource_status', 'Resource status'], ['sensor_status', 'Sensor status'], ['alert_status', 'Alert status']] as const).map(([key, label]) => <label className="form-label map-filter" key={key}>{label}<select className="form-select-sm" value={filters[key]} onChange={(e) => setFilters((current) => ({ ...current, [key]: e.target.value }))}><option value="">All</option>{key === 'disaster_type' && ['flood', 'urban_flood', 'cyclone', 'landslide', 'heatwave', 'severe_weather'].map((value) => <option key={value} value={value}>{value.replace('_', ' ')}</option>)}{key === 'risk_level' && ['low', 'medium', 'high', 'critical'].map((value) => <option key={value} value={value}>{value}</option>)}{key === 'region_id' && [...new Set((overview?.zones || []).map((zone) => zone.region_id))].map((value) => <option key={value} value={value}>{value}</option>)}{key === 'zone_id' && (overview?.zones || []).map((zone) => <option key={zone.id} value={zone.id}>{zone.name}</option>)}{key === 'resource_status' && ['available', 'assigned', 'busy', 'unavailable', 'maintenance'].map((value) => <option key={value} value={value}>{value}</option>)}{key === 'sensor_status' && ['NORMAL', 'ELEVATED', 'CRITICAL'].map((value) => <option key={value} value={value}>{value}</option>)}{key === 'alert_status' && ['info', 'warning', 'critical'].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>)}
        <div className="map-filter-heading" style={{ marginTop: '1rem' }}>ACTIVE DISASTERS</div>{activeRisks.length === 0 && <small>No high/critical zones in the current filter.</small>}{activeRisks.map((risk) => <button key={`${risk.zone_id}-${risk.disaster_type}`} type="button" className="map-disaster-item" onClick={() => { const zone = overview?.zones.find((item) => item.id === risk.zone_id); if (zone) selectZone(zone); }}><span style={{ color: riskColor(risk.risk_level) }}><AlertTriangle size={14} /> {risk.zone}</span><strong>{risk.disaster_type.replace('_', ' ')} · {Math.round(risk.risk_score)}</strong><small>{risk.risk_level.toUpperCase()} · {Math.round(risk.confidence)}% confidence</small></button>)}
        <div className="map-filter-heading" style={{ marginTop: '1rem' }}>LAYERS</div>{Object.entries(layerLabels).map(([key, label]) => <label key={key} className="map-layer-toggle"><input type="checkbox" checked={visible[key]} onChange={(e) => setVisible((current) => ({ ...current, [key]: e.target.checked }))} /> {label}</label>)}
        <div className="map-filter-heading" style={{ marginTop: '1rem' }}>LEGEND</div><div className="map-legend-grid">{[['#16a34a', 'LOW'], ['#d97706', 'MEDIUM'], ['#ea580c', 'HIGH'], ['#dc2626', 'CRITICAL']].map(([color, label]) => <span key={label}><i style={{ background: color }} />{label}</span>)}<span><i style={{ background: '#0d9488' }} />Shelter</span><span><i style={{ background: '#dc2626' }} />Hospital</span><span><i style={{ background: '#2563eb' }} />Rescue team</span><span><i style={{ background: '#16a34a' }} />Safe route</span><span><i style={{ background: '#dc2626' }} />Blocked route</span></div>
        {overview && <div className="map-summary"><strong>CURRENT REGION</strong>{(activeRisks[0] || overview.risks[0]) ? <><span>Risk: {Math.round((activeRisks[0] || overview.risks[0]).risk_score)}/100 · {(activeRisks[0] || overview.risks[0]).risk_level.toUpperCase()}</span><span>Confidence: {Math.round((activeRisks[0] || overview.risks[0]).confidence)}%</span><span>Hazard: {(activeRisks[0] || overview.risks[0]).disaster_type.replace('_', ' ')}</span><span>Evidence: {(activeRisks[0] || overview.risks[0]).contributing_factors.slice(0, 3).join(', ') || 'No factors returned'}</span></> : <span>No risk prediction available.</span>}<span>{overview.affected_population.toLocaleString()} exposed population · {overview.sensors.length} sensor(s)</span><small>Generated {new Date(overview.generated_at).toLocaleTimeString()}</small></div>}
        {selected && <div className="map-summary"><strong>{selected.title}</strong>{Object.entries(selected.details).map(([key, value]) => <span key={key}>{key}: {String(value)}</span>)}</div>}
        {error && <small style={{ color: '#b91c1c' }}>{error}</small>}
      </aside>
    </div>
    <div style={{ padding: '.55rem .8rem', borderTop: '1px solid #e2e8f0', color: '#64748b', fontSize: '.68rem' }}><MapPin size={12} /> GeoJSON geometry and map records are backend-provided. DEMO/SIMULATION values are clearly labelled; offline state must not be interpreted as live updates.</div>
  </section>;
};
