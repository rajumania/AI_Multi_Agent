import React, { useState } from 'react';
import { Play, AlertTriangle, Cpu } from 'lucide-react';
import { api } from '../services/api';
import { Incident } from '../types';

interface SimulationControlsProps {
  onScenarioStarted: (incident: Incident) => void;
  activeIncidentId?: string;
  onRefresh: () => void;
}

export const SimulationControls: React.FC<SimulationControlsProps> = ({
  onScenarioStarted,
  activeIncidentId,
  onRefresh
}) => {
  const [selectedScenario, setSelectedScenario] = useState<string>('ublock_fire');
  const [loadingSim, setLoadingSim] = useState<boolean>(false);
  const [injectingFailure, setInjectingFailure] = useState<boolean>(false);
  const [simMessage, setSimMessage] = useState<string | null>(null);

  const handleStartSimulation = async () => {
    setLoadingSim(true);
    setSimMessage(null);
    try {
      const result = await api.startSimulation(selectedScenario);
      setSimMessage(`Scenario '${selectedScenario}' initiated successfully. Incident ${result.incident_id} created.`);
      onScenarioStarted(result.incident);
      onRefresh();
    } catch (e: any) {
      setSimMessage(`Simulation failed: ${e.message}`);
    } finally {
      setLoadingSim(false);
    }
  };

  const handleInjectFailure = async () => {
    if (!activeIncidentId) {
      setSimMessage('Please select or start an active incident first to simulate resource failure.');
      return;
    }
    setInjectingFailure(true);
    setSimMessage(null);
    try {
      const result = await api.injectResourceFailure(activeIncidentId, 'AMB-001');
      setSimMessage(`⚠️ Breakdown injected for AMB-001. Monitoring Agent autonomously substituted ${result.substitute_resource}!`);
      onRefresh();
    } catch (e: any) {
      setSimMessage(`Failure injection failed: ${e.message}`);
    } finally {
      setInjectingFailure(false);
    }
  };

  return (
    <div style={{
      background: 'linear-gradient(90deg, #0f172a 0%, #1e1b4b 100%)',
      color: '#ffffff',
      borderRadius: '10px',
      padding: '0.75rem 1.25rem',
      marginBottom: '1.25rem',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      flexWrap: 'wrap',
      gap: '0.75rem',
      boxShadow: '0 4px 10px rgba(0,0,0,0.15)',
      border: '1px solid #334155'
    }}>
      {/* Title & Tag */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
        <div style={{ background: '#6366f1', padding: '0.4rem', borderRadius: '6px', display: 'flex', alignItems: 'center' }}>
          <Cpu size={18} color="#ffffff" />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <strong style={{ fontSize: '0.875rem' }}>Digital Twin Autonomous Simulation Mode</strong>
            <span style={{ fontSize: '0.65rem', background: '#312e81', color: '#c7d2fe', padding: '1px 6px', borderRadius: '4px', fontWeight: 700 }}>
              AUTO-PILOT READY
            </span>
          </div>
          <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
            Run live end-to-end multi-agent emergency scenarios or inject equipment breakdowns
          </div>
        </div>
      </div>

      {/* Action Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
        <select
          className="form-select-sm"
          style={{ background: '#1e293b', color: '#ffffff', borderColor: '#475569', fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
          value={selectedScenario}
          onChange={(e) => setSelectedScenario(e.target.value)}
        >
          <option value="ublock_fire">🔥 Scenario: U-Block 2nd Floor Fire</option>
          <option value="hostel_medical">🏥 Scenario: Hostel Medical Emergency</option>
          <option value="gate_security">🚨 Scenario: Main Gate Security Breach</option>
        </select>

        <button
          className="btn"
          style={{ background: '#6366f1', color: '#ffffff', border: 'none', padding: '0.35rem 0.85rem', fontSize: '0.75rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.3rem' }}
          onClick={handleStartSimulation}
          disabled={loadingSim}
        >
          <Play size={13} fill="#ffffff" />
          <span>{loadingSim ? 'Launching...' : 'RUN SCENARIO'}</span>
        </button>

        <button
          className="btn"
          style={{ background: '#dc2626', color: '#ffffff', border: 'none', padding: '0.35rem 0.85rem', fontSize: '0.75rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.3rem' }}
          onClick={handleInjectFailure}
          disabled={injectingFailure}
          title="Simulates vehicle failure to showcase live agent re-planning"
        >
          <AlertTriangle size={13} />
          <span>{injectingFailure ? 'Failing Unit...' : 'SIMULATE AMB-001 BREAKDOWN'}</span>
        </button>
      </div>

      {/* Simulation Feedback Alert */}
      {simMessage && (
        <div style={{ width: '100%', fontSize: '0.75rem', background: '#334155', padding: '0.35rem 0.65rem', borderRadius: '4px', color: '#38bdf8', marginTop: '0.25rem' }}>
          ⚡ {simMessage}
        </div>
      )}
    </div>
  );
};
