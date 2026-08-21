import React from 'react';
import { MapPin, Navigation, Eye, CheckCircle } from 'lucide-react';

export const CampusMapPlaceholder: React.FC = () => {
  const campusZones = [
    { name: 'CSE & Tech Hub', code: 'CSE-01', resource: 'SEC-002 Bravo on site', status: 'normal' },
    { name: 'Central Medical Center', code: 'MED-CTR', resource: 'AMB-001 Primary Ready', status: 'active' },
    { name: 'Main Security Gate', code: 'GATE-01', resource: 'SEC-001 Alpha Ready', status: 'normal' },
    { name: 'Sports Complex Arena', code: 'SHTR-02', resource: 'Shelter Cap: 900', status: 'normal' },
    { name: 'North Auditorium', code: 'SHTR-01', resource: 'Shelter Cap: 600', status: 'normal' },
    { name: 'Transport Parking Hub', code: 'DEPOT-1', resource: 'VEH-001 Transit Van', status: 'normal' },
  ];

  return (
    <div className="panel-card" style={{ height: '100%' }}>
      <div className="panel-header">
        <div className="panel-title">
          <Navigation size={18} color="#0284c7" />
          <span>Campus Geographic Operations Map</span>
        </div>
        <span className="panel-tag">GPS Zone 44N • Live Grid</span>
      </div>

      <div className="panel-body">
        <div className="map-canvas-container">
          <div className="campus-grid-overlay"></div>

          <div className="map-pins-container">
            {campusZones.map((zone) => (
              <div
                key={zone.code}
                className={`map-zone-node ${zone.status === 'active' ? 'highlight' : ''}`}
              >
                <MapPin
                  size={14}
                  color={zone.status === 'active' ? '#0284c7' : '#0d9488'}
                />
                <div>
                  <div>{zone.name}</div>
                  <div style={{ fontSize: '0.6875rem', color: '#64748b', fontWeight: 'normal' }}>
                    {zone.resource}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="map-footer-legend">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Eye size={13} />
              <span>Full Interactive Map Engine (Leaflet/OSM) ready for Step 7</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: '#16a34a' }}>
              <CheckCircle size={13} />
              <span>All 6 campus sectors mapped</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
