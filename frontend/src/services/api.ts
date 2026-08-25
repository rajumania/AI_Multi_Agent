import {
  HealthResponse,
  Incident,
  IncidentAnalysisResponse,
  SupervisorAnalysisResult,
  MultiAgentOrchestrationResponse,
  AssignmentTeamPayload,
  DepartmentAssignment,
  NotificationItem,
  CampusLocation,
  TransportTracking,
} from '../types';

export interface ChatMessage {
  id: number;
  conversation_id: string;
  sender: 'user' | 'assistant';
  message: string;
  created_at: string;
}

export interface ChatHistory {
  conversation_id: string | null;
  messages: ChatMessage[];
}

export interface ChatReply {
  message: string;
  conversation_id: string;
  timestamp: string;
  memory_used: boolean;
}

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
  latitude?: number;
  longitude?: number;
}

export interface DepartmentRegistrationPayload {
  email: string;
  password: string;
  department: string;
  full_name: string;
  role: 'department' | 'department_head';
}

// ---------------------------------------------------------------------------
// Auth token plumbing (backward-compatible).
//
// The token is OPTIONAL. When absent, requests are anonymous exactly as they
// were before auth existed — while the backend has ALLOW_ANONYMOUS_ADMIN
// enabled, anonymous callers are treated as the legacy operator console, so the
// current demo keeps working with no login. Once a user logs in, the token is
// persisted (localStorage key `cf_token`, matching what LoginPage already
// writes) and attached to every REST request and the events WebSocket, letting
// the backend enforce real RBAC.
// ---------------------------------------------------------------------------
const AUTH_TOKEN_KEY = 'cf_token';
const AUTH_USER_KEY = 'cf_user';

export function getAuthToken(): string | null {
  try {
    return typeof localStorage !== 'undefined' ? localStorage.getItem(AUTH_TOKEN_KEY) : null;
  } catch {
    return null;
  }
}

export function setAuthToken(token: string | null): void {
  try {
    if (typeof localStorage === 'undefined') return;
    if (token) localStorage.setItem(AUTH_TOKEN_KEY, token);
    else localStorage.removeItem(AUTH_TOKEN_KEY);
  } catch {
    /* storage unavailable — requests simply stay anonymous */
  }
}

export function clearAuthToken(): void {
  setAuthToken(null);
  try {
    if (typeof localStorage !== 'undefined') localStorage.removeItem(AUTH_USER_KEY);
  } catch {
    /* ignore */
  }
}

// ---------------------------------------------------------------------------
// 401 (expired / invalid token) interception.
//
// AuthContext registers a handler here at startup. When a request that CARRIED
// a token comes back 401, the token is stale/expired: we notify the handler so
// the app can tear down the session and redirect to /login (requirement #9).
// Auth endpoints are exempt — a 401 from a login attempt is "bad credentials",
// handled by the calling page, not a session expiry. The handler must be
// idempotent (several in-flight requests may 401 together).
// ---------------------------------------------------------------------------
type UnauthorizedHandler = () => void;
let unauthorizedHandler: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(fn: UnauthorizedHandler | null): void {
  unauthorizedHandler = fn;
}

function isAuthEndpoint(url: string): boolean {
  return url.includes('/api/v1/auth/');
}

function authHeaders(base?: HeadersInit): Headers {
  const headers = new Headers(base || {});
  const token = getAuthToken();
  if (token) {
    // Send both so either a Bearer parser or the X-Auth-Token fallback works.
    headers.set('Authorization', `Bearer ${token}`);
    headers.set('X-Auth-Token', token);
  }
  return headers;
}

// Drop-in replacement for fetch that transparently attaches auth headers when a
// token is present. With no token it behaves identically to a bare fetch. If a
// tokened request is rejected with 401, the registered unauthorized handler is
// notified (expired/invalid session) — see setUnauthorizedHandler above.
async function authedFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const hadToken = !!getAuthToken();
  const response = await fetch(input, { ...init, headers: authHeaders(init.headers) });
  if (response.status === 401 && hadToken && !isAuthEndpoint(input) && unauthorizedHandler) {
    try {
      unauthorizedHandler();
    } catch {
      /* never let session teardown throw into a caller's request path */
    }
  }
  return response;
}

// Append the auth token to a WebSocket URL as a query parameter. Browsers cannot
// set Authorization headers on a WebSocket handshake, so the backend reads the
// token from `?token=`. With no token the URL is returned unchanged (anonymous).
export function appendWsToken(wsUrl: string): string {
  const token = getAuthToken();
  if (!token) return wsUrl;
  const sep = wsUrl.includes('?') ? '&' : '?';
  return `${wsUrl}${sep}token=${encodeURIComponent(token)}`;
}

// Canonical events WebSocket URL (token-scoped when logged in).
export function buildEventsWsUrl(): string {
  const httpBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
  const wsBase = httpBase.replace(/^http/, 'ws');
  return appendWsToken(`${wsBase}/api/v1/events/ws`);
}

export const api = {
  async getHealth(): Promise<HealthResponse> {
    const response = await authedFetch(`${API_BASE_URL}/health`);
    if (!response.ok) {
      throw new Error(`Health check failed with HTTP status ${response.status}`);
    }
    return response.json();
  },

  async getIncidents(): Promise<Incident[]> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/incidents`);
    if (!response.ok) {
      throw new Error(`Failed to fetch incidents: ${response.status}`);
    }
    return response.json();
  },

  async getIncidentAssignments(incidentId: string): Promise<DepartmentAssignment[]> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/assignments`);
    if (!response.ok) throw new Error(`Failed to fetch department assignments: ${response.status}`);
    return response.json();
  },

  async getMyAssignments(): Promise<DepartmentAssignment[]> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/portal/my-assignments`);
    if (!response.ok) throw new Error(`Failed to fetch department assignments: ${response.status}`);
    return response.json();
  },

  async updateAssignment(incidentId: string, department: string, action: 'accept' | 'decline' | 'en-route' | 'on-scene' | 'completed', message?: string): Promise<DepartmentAssignment> {
    const payload = message ? { accepted: action === 'accept', message } : undefined;
    const response = await authedFetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/assignments/${department}/${action}`, {
      method: 'POST',
      headers: payload ? { 'Content-Type': 'application/json' } : undefined,
      body: payload ? JSON.stringify(payload) : undefined,
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Assignment action failed' }));
      throw new Error(err.detail || `Assignment action failed: ${response.status}`);
    }
    return response.json();
  },

  async assignDepartmentTeam(incidentId: string, department: string, payload: AssignmentTeamPayload): Promise<DepartmentAssignment> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/assignments/${department}/team-assigned`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Team assignment failed' }));
      throw new Error(err.detail || `Team assignment failed: ${response.status}`);
    }
    return response.json();
  },

  async getNotifications(): Promise<NotificationItem[]> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/notifications`);
    if (!response.ok) throw new Error(`Failed to fetch notifications: ${response.status}`);
    return response.json();
  },

  async markNotificationRead(id: number): Promise<NotificationItem> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/notifications/${id}/read`, { method: 'POST' });
    if (!response.ok) throw new Error(`Failed to mark notification read: ${response.status}`);
    return response.json();
  },

  async markAllNotificationsRead(): Promise<NotificationItem[]> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/notifications/read-all`, { method: 'POST' });
    if (!response.ok) throw new Error(`Failed to mark notifications read: ${response.status}`);
    return response.json();
  },

  async getChatHistory(): Promise<ChatHistory> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/chat/history`);
    if (!response.ok) throw new Error(`Failed to load assistant history: ${response.status}`);
    return response.json();
  },

  async sendChatMessage(message: string, conversationId?: string): Promise<ChatReply> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/chat/message`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, conversation_id: conversationId }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Assistant request failed: ${response.status}`);
    return data;
  },

  async clearChatHistory(): Promise<void> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/chat/history`, { method: 'DELETE' });
    if (!response.ok) throw new Error(`Failed to clear assistant history: ${response.status}`);
  },

  async getIncidentById(incidentId: string): Promise<Incident> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch incident ${incidentId}: ${response.status}`);
    }
    return response.json();
  },

  async createIncident(payload: CreateIncidentPayload): Promise<Incident> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/incidents`, {
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
    const response = await authedFetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/analyze`, {
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
    const response = await authedFetch(`${API_BASE_URL}/api/v1/incidents/analyze-raw`, {
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
    const response = await authedFetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/orchestrate`, {
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
    const response = await authedFetch(`${API_BASE_URL}/api/v1/resources${qs}`);
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
    const response = await authedFetch(`${API_BASE_URL}/api/v1/resources/search/available${qs}`);
    if (!response.ok) {
      throw new Error(`Failed to search resources: ${response.status}`);
    }
    return response.json();
  },

  async generateResponsePlan(incidentId: string): Promise<any> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/response-plans/generate/${incidentId}`, {
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
    const response = await authedFetch(`${API_BASE_URL}/api/v1/response-plans${qs}`);
    if (!response.ok) throw new Error(`Failed to fetch response plans: ${response.status}`);
    return response.json();
  },

  async getPendingApprovals(): Promise<any[]> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/approvals/pending`);
    if (!response.ok) throw new Error(`Failed to fetch pending approvals: ${response.status}`);
    return response.json();
  },

  async decideApproval(planId: string, payload: { decision: 'approve' | 'reject'; operator_name: string; notes?: string }): Promise<any> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/approvals/${planId}/decide`, {
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
    const response = await authedFetch(url);
    if (!response.ok) throw new Error(`Failed to fetch activity logs: ${response.status}`);
    return response.json();
  },

  async executeDispatch(planId: string): Promise<any> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/dispatch/${planId}/execute`, {
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
    const response = await authedFetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/resolve`, {
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
    const response = await authedFetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/confirm-response`, {
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
    const response = await authedFetch(`${API_BASE_URL}/api/v1/incidents/${incidentId}/close`, {
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
    const response = await authedFetch(`${API_BASE_URL}/api/v1/simulation/start`, {
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
    const response = await authedFetch(`${API_BASE_URL}/api/v1/simulation/fail-resource`, {
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
    const response = await authedFetch(`${API_BASE_URL}/api/v1/simulation/trace/${incidentId}`);
    if (!response.ok) {
      return { incident_id: incidentId, trace: [], count: 0 };
    }
    return response.json();
  },

  async blockRoad(nodeA: string, nodeB: string, blocked: boolean = true): Promise<any> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/simulation/block-road`, {
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
    const response = await authedFetch(`${API_BASE_URL}/api/v1/routes/calculate?origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}`);
    if (!response.ok) {
      throw new Error(`Failed to calculate route: ${response.status}`);
    }
    return response.json();
  },

  async calculateCoordinateRoute(params: { origin: string; destination: string; origin_lat: number; origin_lng: number; destination_lat: number; destination_lng: number }): Promise<any> {
    const query = new URLSearchParams({
      origin: params.origin,
      destination: params.destination,
      origin_lat: String(params.origin_lat),
      origin_lng: String(params.origin_lng),
      destination_lat: String(params.destination_lat),
      destination_lng: String(params.destination_lng),
    });
    const response = await authedFetch(`${API_BASE_URL}/api/v1/routes/calculate?${query.toString()}`);
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Reliable route unavailable' }));
      throw new Error(error.detail || `Failed to calculate route: ${response.status}`);
    }
    return response.json();
  },

  async login(username: string, password: string): Promise<any> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(err.detail || `Login failed: ${response.status}`);
    }
    const data = await response.json();
    if (data?.token) setAuthToken(data.token);
    return data;
  },

  async userLogin(email: string, phone: string): Promise<any> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/auth/user/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, phone }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(err.detail || `User login failed: ${response.status}`);
    }
    const data = await response.json();
    if (data?.token) setAuthToken(data.token);
    return data;
  },

  async userRegister(payload: { email: string; phone: string; full_name?: string }): Promise<any> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/auth/user/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Registration failed' }));
      throw new Error(err.detail || `User registration failed: ${response.status}`);
    }
    const data = await response.json();
    if (data?.token) setAuthToken(data.token);
    return data;
  },

  async departmentLogin(email: string, password: string, department: string): Promise<any> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/auth/department/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, department }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(err.detail || `Department login failed: ${response.status}`);
    }
    const data = await response.json();
    if (data?.token) setAuthToken(data.token);
    return data;
  },

  async registerDepartment(payload: DepartmentRegistrationPayload): Promise<any> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/auth/department/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: '' }));
      const detail = Array.isArray(err?.detail)
        ? err.detail.map((item: any) => item?.msg || 'Invalid request.').join(' ')
        : typeof err?.detail === 'string' ? err.detail : '';
      if (response.status === 401) {
        throw new Error(detail || 'Your operator session is no longer valid. Please sign in again.');
      }
      if (response.status === 403) {
        throw new Error(detail || 'Only an administrator or operator can create department accounts.');
      }
      if (response.status === 409) {
        throw new Error(detail || 'An account with this email already exists.');
      }
      throw new Error(detail || `Department account creation failed (${response.status}).`);
    }
    return response.json();
  },

  async getCampusLocations(): Promise<CampusLocation[]> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/campus-locations`);
    if (!response.ok) throw new Error(`Failed to fetch campus locations: ${response.status}`);
    return response.json();
  },

  async getMe(): Promise<any> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/auth/me`);
    if (!response.ok) {
      throw new Error(`Failed to fetch current user: ${response.status}`);
    }
    return response.json();
  },

  logout(): void {
    clearAuthToken();
  },

  async signup(payload: any): Promise<any> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Signup failed' }));
      throw new Error(err.detail || `Signup failed: ${response.status}`);
    }
    const data = await response.json();
    if (data?.token) setAuthToken(data.token);
    return data;
  },

  async getSystemStatus(): Promise<any> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/system/status`);
    if (!response.ok) {
      throw new Error(`Failed to fetch system status: ${response.status}`);
    }
    return response.json();
  },

  async sendTelemetry(payload: { vehicle_id: string; latitude: number; longitude: number; speed?: number; heading?: number; accuracy?: number; timestamp?: string; assignment_id?: number; incident_id?: string }, deviceToken: string): Promise<any> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/telemetry/location`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-GPS-Device-Token': deviceToken }, body: JSON.stringify(payload) });
    if (!response.ok) throw new Error('Telemetry rejected');
    return response.json();
  },

  async getTransportTracking(assignmentId: number): Promise<TransportTracking> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/transport/assignments/${assignmentId}/tracking`);
    if (!response.ok) throw new Error(`Failed to fetch transport tracking: ${response.status}`);
    return response.json();
  },

  async reportRoadCondition(payload: { node_a: string; node_b: string; status: 'blocked' | 'cleared'; reason: string; incident_id?: string }): Promise<any> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/road-conditions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Road condition rejected' }));
      throw new Error(error.detail || `Road condition failed: ${response.status}`);
    }
    return response.json();
  },

  async generateVoiceAudio(text: string): Promise<any> {
    const response = await authedFetch(`${API_BASE_URL}/api/v1/voice/generate-audio`, {
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






