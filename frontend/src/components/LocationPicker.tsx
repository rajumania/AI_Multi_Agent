import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { LocateFixed, MapPin } from 'lucide-react';
import { CampusLocation } from '../types';

export interface SelectedLocation {
  latitude: number;
  longitude: number;
  label?: string;
}

interface LocationPickerProps {
  locations: CampusLocation[];
  value: SelectedLocation | null;
  onChange: (value: SelectedLocation) => void;
}

function nearestLabel(latitude: number, longitude: number, locations: CampusLocation[]): string | undefined {
  let closest: CampusLocation | undefined;
  let distance = Number.POSITIVE_INFINITY;
  for (const location of locations) {
    const current = Math.hypot(location.latitude - latitude, location.longitude - longitude) * 111000;
    if (current < distance) {
      closest = location;
      distance = current;
    }
  }
  return closest && distance <= 180 ? closest.name : undefined;
}

export const LocationPicker: React.FC<LocationPickerProps> = ({ locations, value, onChange }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.Marker | null>(null);

  const update = (latitude: number, longitude: number) => {
    onChange({ latitude, longitude, label: nearestLabel(latitude, longitude, locations) });
  };

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, { center: [16.2334, 80.5513], zoom: 16, zoomControl: true });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);
    locations.forEach((location) => {
      L.circleMarker([location.latitude, location.longitude], { radius: 5, color: '#0369a1', fillColor: '#38bdf8', fillOpacity: 0.85 })
        .addTo(map)
        .bindTooltip(location.name, { direction: 'top' });
    });
    map.on('click', (event) => update(event.latlng.lat, event.latlng.lng));
    mapRef.current = map;
    setTimeout(() => map.invalidateSize(), 0);
    return () => { map.remove(); mapRef.current = null; markerRef.current = null; };
  }, [locations]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !value) return;
    if (!markerRef.current) {
      markerRef.current = L.marker([value.latitude, value.longitude], { draggable: true }).addTo(map);
      markerRef.current.on('dragend', () => {
        const point = markerRef.current?.getLatLng();
        if (point) update(point.lat, point.lng);
      });
    } else {
      markerRef.current.setLatLng([value.latitude, value.longitude]);
    }
    markerRef.current.bindTooltip(value.label || 'Selected emergency location', { permanent: true, direction: 'top' }).openTooltip();
    map.panTo([value.latitude, value.longitude]);
  }, [value]);

  const useCurrentLocation = () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (position) => update(position.coords.latitude, position.coords.longitude),
      () => undefined,
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 },
    );
  };

  return (
    <div className="location-picker" style={{ border: '1px solid #bae6fd', borderRadius: 10, overflow: 'hidden', background: '#f8fafc' }}>
      <div className="location-picker-header" style={{ padding: '0.65rem 0.8rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <strong style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: '#0f172a' }}><MapPin size={15} color="#0284c7" /> SELECT EMERGENCY LOCATION</strong>
        <button type="button" onClick={useCurrentLocation} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, border: '1px solid #7dd3fc', borderRadius: 6, background: '#fff', color: '#0369a1', padding: '0.3rem 0.5rem', fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer' }}>
          <LocateFixed size={13} /> USE MY CURRENT LOCATION
        </button>
      </div>
      <div className="location-picker-map" ref={containerRef} style={{ height: 260, width: '100%' }} />
      <div style={{ padding: '0.65rem 0.8rem', background: '#fff', fontSize: '0.72rem', color: '#475569' }}>
        {value ? <><strong>Selected location:</strong> {value.label || 'Exact map point'}<br />Latitude: {value.latitude.toFixed(6)} · Longitude: {value.longitude.toFixed(6)}</> : 'Click the map or drag the marker to select an exact point. GPS is optional.'}
      </div>
    </div>
  );
};
