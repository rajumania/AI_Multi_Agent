import React from 'react';
import { Layers, Truck, Shield, HeartPulse, Home, Wrench } from 'lucide-react';

export const ResourceBreakdownWidget: React.FC = () => {
  const resourceCategories = [
    { label: 'Ambulance Units', count: 2, icon: HeartPulse, note: 'AMB-001, AMB-002 Available' },
    { label: 'Security Units', count: 3, icon: Shield, note: '2 Available, 1 On Patrol' },
    { label: 'First Aid Response', count: 2, icon: HeartPulse, note: 'SAC & Sports Base' },
    { label: 'Emergency Shelters', count: 2, icon: Home, note: '1,500 Total Capacity' },
    { label: 'Evacuation Vehicles', count: 2, icon: Truck, note: 'Van & 50-Passenger Bus' },
    { label: 'Hazard & Facility Teams', count: 2, icon: Wrench, note: 'Hazmat & Fire Suppress' },
  ];

  return (
    <div className="panel-card" style={{ marginTop: '1.5rem' }}>
      <div className="panel-header">
        <div className="panel-title">
          <Layers size={18} color="#0284c7" />
          <span>Response Resources Summary</span>
        </div>
        <span className="panel-tag">Seeded Registry</span>
      </div>

      <div className="panel-body">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.75rem' }}>
          {resourceCategories.map((cat, idx) => {
            const Icon = cat.icon;
            return (
              <div key={idx} className="resource-pill-row">
                <div className="resource-pill-left">
                  <Icon size={16} color="#0369a1" />
                  <div>
                    <div>{cat.label}</div>
                    <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>{cat.note}</div>
                  </div>
                </div>
                <div className="resource-pill-count">{cat.count} Units</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
