import {
  HealthResponse,
  Incident,
  IncidentAnalysisResponse,
  SupervisorAnalysisResult,
  MultiAgentOrchestrationResponse,
} from '../types';

// Keep the backend host explicit for local demos; VITE_API_BASE_URL remains the override.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export interface CreateIncidentPayload {
  description: string;
  incident_type: string;
  location: string;
  severity: string;
  injured_count: number | null; // Strict null for unknown
  evidence_source?: string;
  reported_by?: string;
}

export const api = {
  async getHealth(): Promise<HealthResponse> {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) {
      throw new Error(`Health check failed with HTTP status ${response.status}`);
    }
    return response.json();
  },

  async getIncidents(): Promise<Incident[]> {
    const response = await fetch(`${API_BASE_URL}/api/v1/incidents`);
    if (!response.ok) {
      throw new Error(`Failed to fetch incidents: ${response.status}`);
    }
    return response.json();
  },

  async getIncidentById(incidentId: string): Promise<Incident> {
    const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch incident ${incidentId}: ${response.status}`);
    }
    return response.json();
  },

  async createIncident(payload: CreateIncidentPayload): Promise<Incident> {
    const response = await fetch(`${API_BASE_URL}/api/v1/incidents`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(errData.detail || `Failed to create incident: ${response.status}`);
    }
    return response.json();
  },

  async analyzeIncident(incidentId: string): Promise<IncidentAnalysisResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: 'Analysis failed' }));
      throw new Error(errData.detail || `Failed to analyze incident: ${response.status}`);
    }
    return response.json();
  },

  async analyzeRawText(payload: CreateIncidentPayload): Promise<SupervisorAnalysisResult> {
    const response = await fetch(`${API_BASE_URL}/api/v1/incidents/analyze-raw`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: 'Raw text analysis failed' }));
      throw new Error(errData.detail || `Failed to analyze text: ${response.status}`);
    }
    return response.json();
  },

  async orchestrateIncident(incidentId: string): Promise<MultiAgentOrchestrationResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/orchestrate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: 'Orchestration failed' }));
      throw new Error(errData.detail || `Failed to orchestrate incident: ${response.status}`);
    }
    return response.json();
  },

  async getResources(type?: string, status?: string): Promise<any[]> {
    const params = new URLSearchParams();
    if (type) params.append('type', type);
    if (status) params.append('status', status);
    const qs = params.toString() ? `?${params.toString()}` : '';
    const response = await fetch(`${API_BASE_URL}/api/v1/resources${qs}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch resources: ${response.status}`);
    }
    return response.json();
  },

  async searchAvailableResources(type?: string, location?: string): Promise<any[]> {
    const params = new URLSearchParams();
    if (type) params.append('type', type);
    if (location) params.append('location', location);
    const qs = params.toString() ? `?${params.toString()}` : '';
    const response = await fetch(`${API_BASE_URL}/api/v1/resources/search/available${qs}`);
    if (!response.ok) {
      throw new Error(`Failed to search resources: ${response.status}`);
    }
    return response.json();
  },

  async generateResponsePlan(incidentId: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/response-plans/generate/${incidentId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Failed to generate response plan' }));
      throw new Error(err.detail || `Response plan generation failed: ${response.status}`);
    }
    return response.json();
  },

  async getResponsePlans(incidentId?: string): Promise<any[]> {
    const qs = incidentId ? `?incident_id=${incidentId}` : '';
    const response = await fetch(`${API_BASE_URL}/api/v1/response-plans${qs}`);
    if (!response.ok) throw new Error(`Failed to fetch response plans: ${response.status}`);
    return response.json();
  },

  async getPendingApprovals(): Promise<any[]> {
    const response = await fetch(`${API_BASE_URL}/api/v1/approvals/pending`);
    if (!response.ok) throw new Error(`Failed to fetch pending approvals: ${response.status}`);
    return response.json();
  },

  async decideApproval(planId: string, payload: { decision: 'approve' | 'reject'; operator_name: string; notes?: string }): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/approvals/${planId}/decide`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Approval action failed' }));
      throw new Error(err.detail || `Approval decision failed: ${response.status}`);
    }
    return response.json();
  },

  async getActivityLogs(incidentId?: string, limit: number = 30): Promise<any[]> {
    const url = incidentId
      ? `${API_BASE_URL}/api/v1/activity/${incidentId}?limit=${limit}`
      : `${API_BASE_URL}/api/v1/activity?limit=${limit}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Failed to fetch activity logs: ${response.status}`);
    return response.json();
  },

  async executeDispatch(planId: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/dispatch/${planId}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Dispatch execution failed' }));
      throw new Error(err.detail || `Dispatch execution failed: ${response.status}`);
    }
    return response.json();
  },

  async resolveIncident(incidentId: string, notes: string, resolvedBy: string = 'Campus Safety Commander'): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resolution_notes: notes, resolved_by: resolvedBy }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Incident resolution failed' }));
      throw new Error(err.detail || `Incident resolution failed: ${response.status}`);
    }
    return response.json();
  },

  async confirmResponse(incidentId: string, notes?: string, confirmedBy: string = 'Authorized Campus Operator'): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/confirm-response`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes: notes || 'Response team confirmed on-scene and active handling underway.', confirmed_by: confirmedBy }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Confirm response failed' }));
      throw new Error(err.detail || `Confirm response failed: ${response.status}`);
    }
    return response.json();
  },

  async closeIncident(incidentId: string, closingNotes?: string, closedBy: string = 'Authorized Campus Operator'): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/close`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ closing_notes: closingNotes || 'Incident record administratively finalized and archived.', closed_by: closedBy }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Close incident failed' }));
      throw new Error(err.detail || `Close incident failed: ${response.status}`);
    }
    return response.json();
  },

  async startSimulation(scenarioKey: string = 'ublock_fire'): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/simulation/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_key: scenarioKey }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Simulation start failed' }));
      throw new Error(err.detail || `Simulation start failed: ${response.status}`);
    }
    return response.json();
  },

  async injectResourceFailure(incidentId: string, failedResourceId: string = 'AMB-001'): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/simulation/fail-resource`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ incident_id: incidentId, failed_resource_id: failedResourceId }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Failure injection failed' }));
      throw new Error(err.detail || `Failure injection failed: ${response.status}`);
    }
    return response.json();
  },

  async getDecisionTrace(incidentId: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/simulation/trace/${incidentId}`);
    if (!response.ok) {
      return { incident_id: incidentId, trace: [], count: 0 };
    }
    return response.json();
  },

  async blockRoad(nodeA: string, nodeB: string, blocked: boolean = true): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/simulation/block-road`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_a: nodeA, node_b: nodeB, blocked }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Failed to block road' }));
      throw new Error(err.detail || `Block road failed: ${response.status}`);
    }
    return response.json();
  },

  async calculateRoute(origin: string, destination: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/routes/calculate?origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}`);
    if (!response.ok) {
      throw new Error(`Failed to calculate route: ${response.status}`);
    }
    return response.json();
  },

  async login(username: string, password: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(err.detail || `Login failed: ${response.status}`);
    }
    return response.json();
  },

  async signup(payload: any): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Signup failed' }));
      throw new Error(err.detail || `Signup failed: ${response.status}`);
    }
    return response.json();
  },

  async getSystemStatus(): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/system/status`);
    if (!response.ok) {
      throw new Error(`Failed to fetch system status: ${response.status}`);
    }
    return response.json();
  },

  async sendTelemetry(payload: { vehicle_id: string; latitude: number; longitude: number; speed?: number; heading?: number; accuracy?: number; timestamp?: string }, deviceToken: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/telemetry/location`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-GPS-Device-Token': deviceToken }, body: JSON.stringify(payload) });
    if (!response.ok) throw new Error('Telemetry rejected');
    return response.json();
  },

  async generateVoiceAudio(text: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/v1/voice/generate-audio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    if (!response.ok) {
      throw new Error(`Failed to generate voice audio: ${response.status}`);
    }
    return response.json();
  }
};






