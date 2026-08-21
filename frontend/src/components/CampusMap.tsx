import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { Navigation, RefreshCw } from 'lucide-react';
import { CampusResource, Incident } from '../types';
import { api } from '../services/api';


interface CampusMapProps {
  incidents: Incident[];
  onSelectIncident?: (incident: Incident) => void;
}

export const CampusMap: React.FC<CampusMapProps> = ({ incidents, onSelectIncident }) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);

  const [resources, setResources] = useState<CampusResource[]>([]);
  const [filterType, setFilterType] = useState<string>('all');
  const [loadingResources, setLoadingResources] = useState<boolean>(true);
  const [mouseCoords, setMouseCoords] = useState<{ lat: number; lng: number }>({ lat: 17.5448, lng: 78.5718 });

  const fetchResources = async () => {
    setLoadingResources(true);
    try {
      const data = await api.getResources();
      setResources(data);
    } catch (e) {
      console.error('Failed to load map resources', e);
    } finally {
      setLoadingResources(false);
    }
  };

  useEffect(() => {
    fetchResources();
  }, []);

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    // Campus default center (approx 17.5448, 78.5718)
    const map = L.map(mapContainerRef.current, {
      center: [17.5448, 78.5718],
      zoom: 16,
      zoomControl: true,
    });

    // Light-themed tiles
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; OpenStreetMap',
      maxZoom: 19,
    }).addTo(map);

    const layerGroup = L.layerGroup().addTo(map);
    markersLayerRef.current = layerGroup;
    mapInstanceRef.current = map;

    map.on('mousemove', (e) => {
      setMouseCoords({ lat: Number(e.latlng.lat.toFixed(4)), lng: Number(e.latlng.lng.toFixed(4)) });
    });

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Render Markers on Map
  useEffect(() => {
    if (!mapInstanceRef.current || !markersLayerRef.current) return;

    const layer = markersLayerRef.current;
    layer.clearLayers();

    // 1. Plot Incidents
    if (filterType === 'all' || filterType === 'incidents') {
      incidents.forEach((inc) => {
        // Approximate location coords heuristic based on incident location name
        let lat = 17.5448;
        let lng = 78.5718;

        const loc = inc.location.toLowerCase();
        if (loc.includes('cse') || loc.includes('tech')) {
          lat = 17.5460; lng = 78.5725;
        } else if (loc.includes('science') || loc.includes('lab') || loc.includes('chem')) {
          lat = 17.5465; lng = 78.5710;
        } else if (loc.includes('library') || loc.includes('transformer')) {
          lat = 17.5450; lng = 78.5700;
        } else if (loc.includes('gate') || loc.includes('entrance') || loc.includes('east')) {
          lat = 17.5420; lng = 78.5700;
        } else if (loc.includes('residential') || loc.includes('hostel') || loc.includes('south')) {
          lat = 17.5410; lng = 78.5735;
        } else if (loc.includes('sports') || loc.includes('complex')) {
          lat = 17.5470; lng = 78.5730;
        } else if (loc.includes('mechanical') || loc.includes('workshop')) {
          lat = 17.5435; lng = 78.5740;
        }

        const isCritical = inc.severity === 'critical' || inc.severity === 'high';
        const markerHtml = `
          <div style="
            background: ${isCritical ? '#dc2626' : '#f59e0b'};
            color: #ffffff;
            border: 2px solid #ffffff;
            box-shadow: 0 0 10px rgba(220, 38, 38, 0.6);
            border-radius: 50%;
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
            animation: ${isCritical ? 'pulse 1.5s infinite' : 'none'};
          ">
            🚨
          </div>
        `;

        const icon = L.divIcon({
          html: markerHtml,
          className: 'custom-incident-pin',
          iconSize: [32, 32],
          iconAnchor: [16, 16],
        });

        const marker = L.marker([lat, lng], { icon }).addTo(layer);

        // Safety perimeter circle for high/critical incidents
        if (isCritical) {
          L.circle([lat, lng], {
            radius: 80,
            color: '#dc2626',
            fillColor: '#fee2e2',
            fillOpacity: 0.25,
            weight: 1.5,
            dashArray: '4, 6',
          }).addTo(layer);
        }

        marker.bindPopup(`
          <div style="font-family: sans-serif; min-width: 180px; padding: 2px;">
            <div style="font-weight: 700; font-size: 0.875rem; color: #0f172a; margin-bottom: 2px;">${inc.incident_id}</div>
            <div style="color: #dc2626; font-size: 0.75rem; font-weight: 600; text-transform: uppercase;">${inc.incident_type} • ${inc.severity}</div>
            <div style="font-size: 0.75rem; color: #475569; margin: 4px 0;">📍 ${inc.location}</div>
            <div style="font-size: 0.75rem; color: #334155; margin-bottom: 6px;">${inc.description.slice(0, 70)}...</div>
            <div style="font-size: 0.7rem; color: #0284c7; font-weight: 600;">Status: ${inc.status.toUpperCase()}</div>
          </div>
        `);

        if (onSelectIncident) {
          marker.on('click', () => onSelectIncident(inc));
        }
      });
    }

    // 2. Plot Physical Campus Resources
    resources.forEach((res) => {
      if (!res.latitude || !res.longitude) return;

      // Category filter check
      if (filterType === 'ambulances' && res.resource_type !== 'ambulance') return;
      if (filterType === 'security' && res.resource_type !== 'security') return;
      if (filterType === 'shelters' && res.resource_type !== 'shelter') return;
      if (filterType === 'vehicles' && res.resource_type !== 'vehicle') return;

      const isAvailable = res.availability_status === 'available';
      let iconEmoji = '📍';
      if (res.resource_type === 'ambulance') iconEmoji = '🚑';
      else if (res.resource_type === 'security') iconEmoji = '🛡️';
      else if (res.resource_type === 'first_aid') iconEmoji = '🩹';
      else if (res.resource_type === 'shelter') iconEmoji = '🏛️';
      else if (res.resource_type === 'vehicle') iconEmoji = '🚐';
      else if (res.resource_type === 'fire_response') iconEmoji = '🚒';

      const resMarkerHtml = `
        <div style="
          background: #ffffff;
          border: 2px solid ${isAvailable ? '#16a34a' : '#dc2626'};
          box-shadow: 0 2px 5px rgba(0,0,0,0.15);
          border-radius: 50%;
          width: 28px;
          height: 28px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 13px;
          cursor: pointer;
        ">
          ${iconEmoji}
        </div>
      `;

      const resIcon = L.divIcon({
        html: resMarkerHtml,
        className: 'custom-resource-pin',
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      });

      const resMarker = L.marker([res.latitude, res.longitude], { icon: resIcon }).addTo(layer);

      resMarker.bindPopup(`
        <div style="font-family: sans-serif; min-width: 170px; padding: 2px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
            <span style="font-weight: 700; font-size: 0.8125rem; color: #0f172a;">${res.resource_id}</span>
            <span style="font-size: 0.65rem; background: ${isAvailable ? '#dcfce7' : '#fee2e2'}; color: ${isAvailable ? '#166534' : '#991b1b'}; padding: 1px 4px; border-radius: 4px; font-weight: 600;">
              ${res.availability_status.toUpperCase()}
            </span>
          </div>
          <div style="font-size: 0.75rem; font-weight: 600; color: #334155;">${res.name}</div>
          <div style="font-size: 0.7rem; color: #64748b; margin-top: 3px;">📍 ${res.location}</div>
          ${res.contact ? `<div style="font-size: 0.7rem; color: #0284c7; margin-top: 2px;">📻 ${res.contact}</div>` : ''}
          ${res.capacity ? `<div style="font-size: 0.7rem; color: #475569;">Capacity: ${res.capacity}</div>` : ''}
        </div>
      `);
    });
  }, [incidents, resources, filterType, onSelectIncident]);

  return (
    <div className="panel-card" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div className="panel-header" style={{ padding: '0.65rem 1rem' }}>
        <div className="panel-title">
          <Navigation size={18} color="#0284c7" />
          <span>Interactive Campus Command Map</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <button
            className="btn btn-outline"
            style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
            onClick={fetchResources}
            disabled={loadingResources}
            title="Refresh GPS Assets"
          >
            <RefreshCw size={12} className={loadingResources ? 'spin' : ''} />
            <span>Sync</span>
          </button>
          <span className="panel-tag" style={{ fontSize: '0.7rem' }}>Live GPS Grid</span>
        </div>
      </div>

      {/* Filter Chips Toolbar */}
      <div style={{ display: 'flex', gap: '0.35rem', padding: '0.5rem 0.85rem', background: '#f8fafc', borderBottom: '1px solid #e2e8f0', flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-muted)', marginRight: '0.2rem' }}>Layer:</span>
        <button
          className={`filter-chip ${filterType === 'all' ? 'active' : ''}`}
          style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
          onClick={() => setFilterType('all')}
        >
          All Layers
        </button>
        <button
          className={`filter-chip ${filterType === 'incidents' ? 'active' : ''}`}
          style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
          onClick={() => setFilterType('incidents')}
        >
          🚨 Incidents ({incidents.length})
        </button>
        <button
          className={`filter-chip ${filterType === 'ambulances' ? 'active' : ''}`}
          style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
          onClick={() => setFilterType('ambulances')}
        >
          🚑 Ambulances
        </button>
        <button
          className={`filter-chip ${filterType === 'security' ? 'active' : ''}`}
          style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
          onClick={() => setFilterType('security')}
        >
          🛡️ Security
        </button>
        <button
          className={`filter-chip ${filterType === 'shelters' ? 'active' : ''}`}
          style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
          onClick={() => setFilterType('shelters')}
        >
          🏛️ Shelters
        </button>
        <button
          className={`filter-chip ${filterType === 'vehicles' ? 'active' : ''}`}
          style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
          onClick={() => setFilterType('vehicles')}
        >
          🚐 Shuttles
        </button>
      </div>

      <div className="panel-body" style={{ padding: 0, flex: 1, position: 'relative', minHeight: '340px' }}>
        <div ref={mapContainerRef} style={{ width: '100%', height: '100%', minHeight: '340px', zIndex: 1 }} />

        {/* Live Coordinate Display Widget */}
        <div style={{
          position: 'absolute',
          bottom: '8px',
          left: '8px',
          background: 'rgba(255, 255, 255, 0.92)',
          backdropFilter: 'blur(4px)',
          border: '1px solid #cbd5e1',
          borderRadius: '4px',
          padding: '2px 6px',
          fontSize: '0.6875rem',
          color: '#334155',
          zIndex: 1000,
          fontFamily: 'monospace',
        }}>
          LAT: {mouseCoords.lat.toFixed(4)} • LNG: {mouseCoords.lng.toFixed(4)} • EPSG:4326
        </div>
      </div>
    </div>
  );
};
