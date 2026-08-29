import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { LocateFixed, Route, ShieldAlert } from 'lucide-react';
import { DepartmentAssignment, Incident, TransportTracking } from '../types';
import { api } from '../services/api';

interface Props {
  assignment: DepartmentAssignment;
  incident: Incident;
  tracking: TransportTracking | null;
}

export const TransportResponseMap: React.FC<Props> = ({ assignment, incident, tracking }) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const watchRef = useRef<number | null>(null);
  const [gpsState, setGpsState] = useState<'OFFLINE' | 'STARTING' | 'LIVE' | 'BLOCKED'>('OFFLINE');
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;
    const center: [number, number] = [incident.latitude ?? 18.56517, incident.longitude ?? 84.19587];
    const map = L.map(mapContainer.current, { center, zoom: 16, zoomControl: true });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap contributors', maxZoom: 19 }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    setTimeout(() => map.invalidateSize(), 0);
    return () => { if (watchRef.current !== null) navigator.geolocation?.clearWatch(watchRef.current); map.remove(); mapRef.current = null; layerRef.current = null; };
  }, [incident.latitude, incident.longitude]);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();
    const incidentPoint: [number, number] | null = incident.latitude != null && incident.longitude != null ? [incident.latitude, incident.longitude] : null;
    const currentPoint: [number, number] | null = tracking?.current_latitude != null && tracking.current_longitude != null ? [tracking.current_latitude, tracking.current_longitude] : null;
    if (incidentPoint) {
      L.marker(incidentPoint, { icon: L.divIcon({ html: '<div style="background:#dc2626;color:#fff;border:2px solid #fff;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center">!</div>', className: 'transport-incident-pin', iconSize: [28, 28], iconAnchor: [14, 14] }) }).addTo(layer).bindTooltip(`Emergency: ${incident.location}`, { permanent: true, direction: 'top' });
    }
    if (currentPoint) {
      L.marker(currentPoint, { icon: L.divIcon({ html: '<div style="background:#0284c7;color:#fff;border:2px solid #fff;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center">GPS</div>', className: 'transport-gps-pin', iconSize: [28, 28], iconAnchor: [14, 14] }) }).addTo(layer).bindTooltip(`${tracking?.resource_id || 'Assigned transport'} · REAL GPS`, { permanent: true, direction: 'bottom' });
    }
    const coordinates = tracking?.route?.coordinates || [];
    if (coordinates.length > 1) {
      L.polyline(coordinates, { color: '#10b981', weight: 5, opacity: 0.85 }).addTo(layer);
      const bounds = L.latLngBounds(coordinates);
      if (incidentPoint) bounds.extend(incidentPoint);
      if (currentPoint) bounds.extend(currentPoint);
      map.fitBounds(bounds, { padding: [30, 30], maxZoom: 18 });
    } else if (incidentPoint) {
      map.setView(incidentPoint, 17);
    }
  }, [incident, tracking]);

  useEffect(() => () => { if (watchRef.current !== null) navigator.geolocation?.clearWatch(watchRef.current); }, []);

  const startGps = () => {
    const resourceId = assignment.assigned_resources[0];
    const deviceToken = import.meta.env.VITE_GPS_DEVICE_TOKEN;
    if (!resourceId || !deviceToken) {
      setGpsState('BLOCKED');
      setNotice('REAL GPS is unavailable until an assigned resource and device token are configured.');
      return;
    }
    if (!navigator.geolocation) {
      setGpsState('BLOCKED');
      setNotice('This browser does not provide GPS.');
      return;
    }
    if (watchRef.current !== null) navigator.geolocation.clearWatch(watchRef.current);
    setGpsState('STARTING');
    watchRef.current = navigator.geolocation.watchPosition(async (position) => {
      const timestamp = new Date(position.timestamp || Date.now()).toISOString();
      try {
        await api.sendTelemetry({
          vehicle_id: resourceId,
          assignment_id: assignment.id,
          incident_id: assignment.incident_id,
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
          heading: position.coords.heading || 0,
          speed: position.coords.speed || 0,
          timestamp,
        }, deviceToken);
        setGpsState('LIVE');
        setNotice('REAL GPS telemetry is being sent for this assigned resource.');
      } catch {
        setGpsState('BLOCKED');
        setNotice('The backend rejected this GPS update. Verify the assignment and device authorization.');
      }
    }, () => {
      setGpsState('BLOCKED');
      setNotice('GPS permission was denied or unavailable.');
    }, { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 });
  };

  const active = assignment.status === 'EN_ROUTE' || assignment.status === 'ON_SCENE';
  return (
    <section className="transport-response-map" style={{ marginTop: '0.8rem', border: '1px solid #99f6e4', borderRadius: 9, background: '#f0fdfa', overflow: 'hidden' }}>
      <div style={{ padding: '0.7rem 0.8rem', display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <strong style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#134e4a', fontSize: '0.78rem' }}><Route size={15} /> TRANSPORT RESPONSE</strong>
        {active && <button type="button" onClick={startGps} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, border: '1px solid #0f766e', borderRadius: 6, background: '#fff', color: '#115e59', padding: '0.3rem 0.5rem', fontSize: '0.68rem', fontWeight: 800, cursor: 'pointer' }}><LocateFixed size={13} /> ENABLE LIVE GPS</button>}
      </div>
      <div className="transport-response-map-canvas" ref={mapContainer} style={{ height: 290, width: '100%' }} />
      <div style={{ padding: '0.7rem 0.8rem', background: '#fff', display: 'grid', gap: 4, fontSize: '0.72rem', color: '#475569' }}>
        <div><strong>Incident:</strong> {incident.location}</div>
        <div><strong>Vehicle:</strong> {tracking?.resource_id || assignment.assigned_resources[0] || 'Not assigned'}</div>
        <div><strong>Status:</strong> {assignment.status} · <strong>GPS:</strong> {tracking?.gps_source || gpsState}</div>
        <div><strong>ETA:</strong> {tracking?.eta_seconds != null ? `${Math.ceil(tracking.eta_seconds / 60)} min` : 'ETA unavailable'}</div>
        {tracking?.route?.geometry_source && <div><strong>Route source:</strong> {tracking.route.geometry_source}</div>}
        {(tracking?.route_warning || notice) && <div style={{ color: '#b45309', display: 'flex', gap: 5, alignItems: 'flex-start' }}><ShieldAlert size={14} /> {tracking?.route_warning || notice}</div>}
      </div>
    </section>
  );
};
