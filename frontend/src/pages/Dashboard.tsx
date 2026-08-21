import React from 'react';
import {
  AlertTriangle,
  Flame,
  Layers,
  Bot,
  PlusCircle,
  RotateCcw,
  Clock,
  HeartPulse,
  ArrowRight
} from 'lucide-react';
import { HealthResponse, Incident } from '../types';
import { MetricCard } from '../components/MetricCard';
import { CampusMap } from '../components/CampusMap';
import { RecentActivityPlaceholder } from '../components/RecentActivityPlaceholder';
import { ResourceBreakdownWidget } from '../components/ResourceBreakdownWidget';


interface DashboardProps {
  health: HealthResponse | null;
  incidents: Incident[];
  loading: boolean;
  onRefresh: () => void;
  onOpenReportModal: () => void;
  onNavigateToIncidents: () => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  health,
  incidents,
  loading,
  onRefresh,
  onOpenReportModal,
  onNavigateToIncidents,
}) => {
  const resourceCount = health?.seeded_resources ?? 13;
  const activeIncidents = incidents.filter((i) => i.status !== 'resolved');
  const criticalIncidents = incidents.filter((i) => i.severity === 'critical');

  return (
    <div className="app-content">
      <div className="dashboard-title-row">
        <div>
          <h2>Campus Operations Command Center</h2>
          <p>Real-time emergency monitoring, intelligent agent readiness, and campus resource orchestration.</p>
        </div>

        <div className="quick-actions-group">
          <button
            className="btn btn-outline"
            onClick={onRefresh}
            disabled={loading}
          >
            <RotateCcw size={15} />
            <span>Refresh Telemetry</span>
          </button>

          <button
            className="btn btn-danger"
            onClick={onOpenReportModal}
            style={{ backgroundColor: 'var(--danger-600)', color: '#ffffff' }}
          >
            <PlusCircle size={16} />
            <span>Report Emergency</span>
          </button>
        </div>
      </div>

      {/* Top Level Metric Cards */}
      <div className="metrics-grid">
        <MetricCard
          label="Active Incidents"
          value={activeIncidents.length}
          subtext={
            activeIncidents.length > 0
              ? `${activeIncidents.length} active emergency stream(s)`
              : 'Intake pipeline active & ready'
          }
          icon={AlertTriangle}
          variant={activeIncidents.length > 0 ? 'red' : 'blue'}
        />

        <MetricCard
          label="Critical Severity"
          value={criticalIncidents.length}
          subtext={
            criticalIncidents.length > 0
              ? `${criticalIncidents.length} high priority threat(s)`
              : 'No active Level 4 escalations'
          }
          icon={Flame}
          variant="red"
        />

        <MetricCard
          label="Available Resources"
          value={resourceCount}
          subtext={`${resourceCount} emergency assets seeded in DB`}
          icon={Layers}
          variant="teal"
        />

        <MetricCard
          label="AI Agent Readiness"
          value="5 Agents"
          subtext="Supervisor, Security, Medical, Transport, Comms"
          icon={Bot}
          variant="green"
        />
      </div>

      {/* If incidents exist, show an Active Emergency Banner / Quick Preview */}
      {incidents.length > 0 && (
        <div className="panel-card" style={{ marginBottom: '1.5rem', borderLeft: '4px solid var(--danger-600)' }}>
          <div className="panel-header" style={{ background: '#fef2f2' }}>
            <div className="panel-title" style={{ color: 'var(--danger-text)' }}>
              <AlertTriangle size={18} />
              <span>Latest Reported Incident Stream</span>
            </div>
            <button
              className="btn btn-outline"
              style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
              onClick={onNavigateToIncidents}
            >
              <span>View All ({incidents.length})</span>
              <ArrowRight size={13} />
            </button>
          </div>
          <div className="panel-body" style={{ padding: '0.875rem 1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                  <span className="incident-id-tag">{incidents[0].incident_id}</span>
                  <strong style={{ fontSize: '0.9375rem', color: 'var(--text-primary)' }}>
                    {incidents[0].location}
                  </strong>
                  <span className="badge badge-high">{incidents[0].severity.toUpperCase()}</span>
                </div>
                <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                  {incidents[0].description}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <HeartPulse size={14} color="#0d9488" />
                  <span>
                    Injured:{' '}
                    {incidents[0].injured_count === null ? (
                      <strong>Unknown (null)</strong>
                    ) : (
                      `${incidents[0].injured_count} confirmed`
                    )}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <Clock size={14} />
                  <span>{new Date(incidents[0].created_at).toLocaleTimeString()}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main 2-Column Section: Map & Activity Feed */}
      <div className="dashboard-columns">
        <CampusMap incidents={incidents} onSelectIncident={onNavigateToIncidents} />
        <RecentActivityPlaceholder />
      </div>


      {/* Resource Breakdown Table/Cards */}
      <ResourceBreakdownWidget />
    </div>
  );
};
