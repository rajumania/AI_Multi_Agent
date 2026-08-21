import React, { useEffect, useState } from 'react';
import { Layers, RefreshCw, MapPin, Radio, Shield, HeartPulse, Truck, Filter, AlertTriangle } from 'lucide-react';

import { CampusResource } from '../types';
import { api } from '../services/api';

export const ResourcesPage: React.FC = () => {
  const [resources, setResources] = useState<CampusResource[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const fetchResources = async () => {
    setLoading(true);
    try {
      const data = await api.getResources();
      setResources(data);
    } catch (e) {
      console.error('Failed to load resources', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResources();
  }, []);

  const filtered = resources.filter((r) => {
    if (typeFilter !== 'all' && r.resource_type !== typeFilter) return false;
    if (statusFilter !== 'all' && r.availability_status !== statusFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        r.name.toLowerCase().includes(q) ||
        r.resource_id.toLowerCase().includes(q) ||
        r.location.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const getResourceIcon = (type: string) => {
    switch (type) {
      case 'ambulance':
        return <HeartPulse size={18} color="#dc2626" />;
      case 'security':
        return <Shield size={18} color="#0284c7" />;
      case 'first_aid':
        return <HeartPulse size={18} color="#0d9488" />;
      case 'vehicle':
        return <Truck size={18} color="#8b5cf6" />;
      default:
        return <Layers size={18} color="#0284c7" />;
    }
  };

  return (
    <div className="app-content">
      <div className="dashboard-title-row">
        <div>
          <h2>Campus Emergency Resource Inventory</h2>
          <p>Real-time physical asset coordination backed by Model Context Protocol (MCP) and SQLite database.</p>
        </div>

        <div className="quick-actions-group">
          <button className="btn btn-outline" onClick={fetchResources} disabled={loading}>
            <RefreshCw size={15} className={loading ? 'spin' : ''} />
            <span>Sync Assets</span>
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="filter-bar" style={{ marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap', flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>
            <Filter size={15} />
            <span>Filters:</span>
          </div>

          <input
            type="text"
            className="form-input"
            style={{ width: '220px', padding: '0.35rem 0.6rem', fontSize: '0.8125rem' }}
            placeholder="Search by ID, name, location..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />

          <select
            className="form-select-sm"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option value="all">All Resource Types</option>
            <option value="ambulance">Ambulances</option>
            <option value="security">Security Units</option>
            <option value="first_aid">First Aid Teams</option>
            <option value="shelter">Emergency Shelters</option>
            <option value="vehicle">Evacuation Vehicles</option>
            <option value="facility">Facility & Fire</option>
          </select>

          <select
            className="form-select-sm"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All Statuses</option>
            <option value="available">Available / Ready</option>
            <option value="busy">Busy / Dispatched</option>
            <option value="unavailable">Unavailable</option>
          </select>
        </div>

        <div style={{ marginLeft: 'auto', fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
          Showing <strong>{filtered.length}</strong> of {resources.length} campus assets
        </div>
      </div>

      {/* Grid of Resources */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
          Loading campus resource records from SQLite...
        </div>
      ) : filtered.length === 0 ? (
        <div className="panel-card" style={{ padding: '3rem', textAlign: 'center' }}>
          <AlertTriangle size={32} color="#94a3b8" style={{ margin: '0 auto 0.5rem' }} />
          <h3>No Matching Resources Found</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Try adjusting your search query or filter criteria.
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem' }}>
          {filtered.map((res) => {
            const isAvail = res.availability_status === 'available';
            return (
              <div key={res.resource_id} className="panel-card" style={{ borderTop: `3px solid ${isAvail ? '#16a34a' : '#dc2626'}` }}>
                <div className="panel-header" style={{ padding: '0.75rem 1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    {getResourceIcon(res.resource_type)}
                    <div>
                      <span style={{ fontWeight: 700, fontSize: '0.875rem', color: 'var(--text-primary)' }}>
                        {res.resource_id}
                      </span>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                        {res.resource_type.replace(/_/g, ' ')}
                      </div>
                    </div>
                  </div>

                  <span className={`status-pill ${isAvail ? 'status-approved' : 'status-reported'}`} style={{ fontSize: '0.7rem' }}>
                    {res.availability_status.toUpperCase()}
                  </span>
                </div>

                <div className="panel-body" style={{ padding: '0.85rem 1rem' }}>
                  <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                    {res.name}
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontSize: '0.78125rem', color: 'var(--text-secondary)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <MapPin size={14} color="#0284c7" />
                      <span>{res.location}</span>
                    </div>

                    {res.contact && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                        <Radio size={14} color="#0d9488" />
                        <span>Radio: <strong>{res.contact}</strong></span>
                      </div>
                    )}

                    {res.capacity && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        Capacity: <strong>{res.capacity} occupants/units</strong>
                      </div>
                    )}

                    {res.latitude && res.longitude && (
                      <div style={{ fontSize: '0.7rem', color: '#64748b', fontFamily: 'monospace', marginTop: '0.25rem' }}>
                        GPS: {res.latitude.toFixed(4)}, {res.longitude.toFixed(4)}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
