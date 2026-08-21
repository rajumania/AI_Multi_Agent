export type IncidentType =
  | 'fire'
  | 'medical'
  | 'security'
  | 'accident'
  | 'weather'
  | 'crowd'
  | 'facility'
  | 'other'
  | 'unknown';

export type SeverityLevel =
  | 'low'
  | 'medium'
  | 'high'
  | 'critical'
  | 'unknown';

export type IncidentStatus =
  | 'reported'
  | 'analyzing'
  | 'classified'
  | 'response_planning'
  | 'awaiting_approval'
  | 'approved'
  | 'rejected'
  | 'resolved';

export interface Incident {
  incident_id: string;
  description: string;
  incident_type: IncidentType;
  location: string;
  severity: SeverityLevel;
  injured_count: number | null; // Strict null for unknown
  evidence_source?: string;
  reported_by?: string;
  status: IncidentStatus;
  summary?: string;
  confidence?: number;
  created_at: string;
  updated_at: string;
}

export interface SupervisorAnalysisResult {
  incident_type: IncidentType;
  severity: SeverityLevel;
  location: string;
  injured_count: number | null;
  summary: string;
  confidence: number;
  recommended_agents: string[];
  key_observations: string[];
}

export interface IncidentAnalysisResponse {
  incident: Incident;
  analysis: SupervisorAnalysisResult;
}

export interface SecurityAgentResult {
  agent_name: string;
  threat_level: string;
  actions: string[];
  recommended_security_units?: number;
  perimeter_lockdown_required?: boolean;
  notes?: string;
}

export interface MedicalAgentResult {
  agent_name: string;
  triage_priority: string;
  actions: string[];
  recommended_ambulances?: number;
  first_aid_units_required?: number;
  medical_center_alert?: boolean;
  casualty_assessment?: string;
}

export interface TransportAgentResult {
  agent_name: string;
  route_status: string;
  actions: string[];
  recommended_vehicles?: number;
  evacuation_shuttles_required?: number;
  traffic_rerouting_active?: boolean;
}

export interface CommunicationAgentResult {
  agent_name: string;
  broadcast_priority: string;
  alert_headline: string;
  broadcast_channels: string[];
  recommended_message: string;
  actions: string[];
}

export interface MultiAgentOrchestrationResponse {
  incident: Incident;
  delegated_agents: string[];
  security_result?: SecurityAgentResult | null;
  medical_result?: MedicalAgentResult | null;
  transport_result?: TransportAgentResult | null;
  communication_result?: CommunicationAgentResult | null;
  mcp_resources: CampusResource[];
  all_recommendations: string[];
  required_approvals: string[];
  audit_trail: string[];
  execution_status: string;
}




export type ResourceType =
  | 'ambulance'
  | 'security'
  | 'first_aid'
  | 'shelter'
  | 'vehicle'
  | 'medical_center'
  | 'facility'
  | 'fire_response'
  | 'other';

export type AvailabilityStatus =
  | 'available'
  | 'busy'
  | 'unavailable'
  | 'maintenance'
  | 'unknown';

export interface CampusResource {
  id?: number;
  resource_id: string;
  name: string;
  resource_type: ResourceType;
  location: string;
  latitude?: number;
  longitude?: number;
  availability_status: AvailabilityStatus;
  capacity?: number;
  quantity: number;
  contact?: string;
  last_updated?: string;
}

export type ApprovalStatus = 'pending' | 'approved' | 'rejected';

export interface ResponsePlan {
  plan_id: string;
  incident_id: string;
  title: string;
  severity: string;
  location: string;
  recommended_actions: string[];
  allocated_resources: string[];
  requires_approval: boolean;
  approval_status: ApprovalStatus;
  approved_by?: string | null;
  approval_notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApprovalDecisionPayload {
  decision: 'approve' | 'reject';
  operator_name: string;
  notes?: string;
}

export interface AuditLog {
  id: number;
  incident_id?: string | null;
  plan_id?: string | null;
  action_type: string;
  actor: string;
  description: string;
  details?: any;
  timestamp: string;
}

export interface BroadcastNotification {
  channel: string;
  recipient_group: string;
  headline: string;
  message: string;
  timestamp: string;
  status: string;
}

export interface DispatchExecutionResult {
  plan_id: string;
  incident_id: string;
  execution_status: string;
  dispatched_resources: string[];
  broadcast_alerts: BroadcastNotification[];
  executed_at: string;
  execution_notes: string;
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'error';
  service: string;
  environment: string;
  database: string;
  seeded_resources: number;
  timestamp: string;
}


