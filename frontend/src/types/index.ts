export type IncidentType =
  | 'fire'
  | 'chemical'
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
  | 'assessing'
  | 'classified'
  | 'planning'
  | 'response_planning'
  | 'awaiting_approval'
  | 'approved'
  | 'authorized'
  | 'rejected'
  | 'in_progress'
  | 'response_in_progress'
  | 'dispatched'
  | 'monitoring'
  | 'resolved'
  | 'closed'
  | 'cancelled'
  | 'action_failed';

export interface Incident {
  incident_id: string;
  description: string;
  incident_type: IncidentType;
  location: string;
  severity: SeverityLevel;
  injured_count: number | null; // Strict null for unknown
  evidence_source?: string;
  reported_by?: string;
  latitude?: number | null;
  longitude?: number | null;
  status: IncidentStatus;
  ai_provider_status?: string | null;
  current_step?: string;
  next_action?: string;
  summary?: string;
  confidence?: number;
  resolved_at?: string;
  closed_at?: string;
  resolution_note?: string;
  required_departments?: string[];
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

export interface CampusLocation {
  location_id: string;
  name: string;
  kind: string;
  latitude: number;
  longitude: number;
  aliases: string[];
  coordinate_source: string;
  verification_status: string;
}

export interface LiveEvent {
  event_name: string;
  incident_id?: string;
  timestamp: string;
  time_display?: string;
  description?: string;
  [key: string]: any;
}

export type DepartmentAssignmentStatus =
  | 'NOTIFIED'
  | 'ACCEPTED'
  | 'DECLINED'
  | 'TEAM_ASSIGNED'
  | 'EN_ROUTE'
  | 'ON_SCENE'
  | 'COMPLETED';

export interface DepartmentAssignment {
  id: number;
  incident_id: string;
  department: string;
  status: DepartmentAssignmentStatus | string;
  accepted: number;
  message?: string | null;
  responder?: string | null;
  assigned_resources: string[];
  created_at: string;
  updated_at: string;
}

export interface TransportTracking {
  assignment_id: number;
  incident_id: string;
  department: string;
  resource_id?: string | null;
  team_identity?: string | null;
  status: string;
  incident_location: string;
  incident_latitude?: number | null;
  incident_longitude?: number | null;
  current_latitude?: number | null;
  current_longitude?: number | null;
  last_gps_update?: string | null;
  gps_source: 'REAL' | 'UNAVAILABLE' | string;
  route?: {
    coordinates?: [number, number][];
    route_version?: number;
    distance_meters?: number;
    eta_seconds?: number;
    geometry_source?: string;
    status?: string;
    updated_at?: string | null;
  } | null;
  eta_seconds?: number | null;
  route_warning?: string | null;
}

export interface AssignmentTeamPayload {
  resource_ids: string[];
  team_name?: string;
}

export interface NotificationItem {
  id: number;
  recipient_type: string;
  department?: string | null;
  incident_id?: string | null;
  title: string;
  message: string;
  level: string;
  read: number;
  created_at: string;
}


