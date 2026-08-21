import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './pages/Dashboard';
import { IncidentsPage } from './pages/IncidentsPage';
import { ResourcesPage } from './pages/ResourcesPage';
import { AgentsPage } from './pages/AgentsPage';
import { ResponsesPage } from './pages/ResponsesPage';
import { ActivityPage } from './pages/ActivityPage';
import { ReportEmergencyModal } from './components/ReportEmergencyModal';
import { api } from './services/api';
import { HealthResponse, Incident } from './types';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isReportModalOpen, setIsReportModalOpen] = useState<boolean>(false);

  const fetchTelemetry = useCallback(async () => {
    setLoading(true);
    try {
      const [healthData, incidentsData] = await Promise.all([
        api.getHealth().catch((err) => {
          console.warn('Backend /health unreachable:', err);
          return null;
        }),
        api.getIncidents().catch((err) => {
          console.warn('Incidents fetch failed:', err);
          return [];
        }),
      ]);
      setHealth(healthData);
      setIncidents(incidentsData);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 10000);
    return () => clearInterval(interval);
  }, [fetchTelemetry]);

  const handleIncidentCreated = (newIncident: Incident) => {
    setIncidents((prev) => [newIncident, ...prev]);
    setActiveTab('incidents');
  };

  return (
    <div className="app-container">
      <Header
        health={health}
        loading={loading}
        onRefresh={fetchTelemetry}
      />

      <div className="main-body">
        <Sidebar
          activeTab={activeTab}
          onTabChange={(tab) => setActiveTab(tab)}
        />

        <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          {activeTab === 'overview' && (
            <Dashboard
              health={health}
              incidents={incidents}
              loading={loading}
              onRefresh={fetchTelemetry}
              onOpenReportModal={() => setIsReportModalOpen(true)}
              onNavigateToIncidents={() => setActiveTab('incidents')}
            />
          )}

          {activeTab === 'incidents' && (
            <IncidentsPage
              incidents={incidents}
              loading={loading}
              onOpenReportModal={() => setIsReportModalOpen(true)}
              onRefresh={fetchTelemetry}
            />
          )}

          {activeTab === 'resources' && (
            <ResourcesPage />
          )}

          {activeTab === 'agents' && (
            <AgentsPage />
          )}

          {activeTab === 'responses' && (
            <ResponsesPage />
          )}

          {activeTab === 'activity' && (
            <ActivityPage />
          )}
        </main>
      </div>


      <ReportEmergencyModal
        isOpen={isReportModalOpen}
        onClose={() => setIsReportModalOpen(false)}
        onIncidentCreated={handleIncidentCreated}
      />
    </div>
  );
};

export default App;
