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

export type DisasterType =
  | 'flood'
  | 'urban_flood'
  | 'cyclone'
  | 'landslide'
  | 'severe_weather'
  | 'heatwave'
  | 'earthquake'
  | 'fire'
  | 'other';

export interface IntelligencePreview {
  location: string;
  latitude: number;
  longitude: number;
  reverse_geocode?: { label?: string; status?: string; source?: string } | null;
  weather: Record<string, any>;
  environmental: Record<string, any>[];
  earthquakes: Record<string, any>[];
  earthquake_status: string;
  severe_weather: Record<string, any>[];
  severe_weather_status: string;
  routes: Record<string, any>[];
  evidence: Record<string, any>;
  risk: { score: number; level: string; confidence: number; contributing_factors: string[]; explanation: string; data_status: string; [key: string]: any };
  departments: { department: string; reason: string }[];
  image_analysis: Record<string, any>;
  provider_status: Record<string, any>[];
  data_status: string;
}

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
  disaster_type?: DisasterType | null;
  location: string;
  severity: SeverityLevel;
  injured_count: number | null; // Strict null for unknown
  evidence_source?: string;
  reported_by?: string;
  latitude?: number | null;
  longitude?: number | null;
  image_url?: string | null;
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
  region_id?: string | null;
  zone_id?: string | null;
  community_id?: string | null;
  client_operation_id?: string | null;
  detection_evidence?: Record<string, unknown> | null;
  sync_state?: 'queued' | 'synced';
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
  | 'hospital'
  | 'clinic'
  | 'rescue_team'
  | 'fire_service'
  | 'police'
  | 'emergency_service'
  | 'boat'
  | 'food'
  | 'water'
  | 'emergency_kit'
  | 'other';

export type AvailabilityStatus =
  | 'available'
  | 'assigned'
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
  current_assignment?: string | null;
  department?: string | null;
  emergency_beds?: number | null;
  is_demo?: boolean | number;
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
  priority?: string;
  lifecycle_status?: string;
  delivered_at?: string | null;
  read_at?: string | null;
  details?: Record<string, unknown>;
}

export interface RiskPrediction {
  prediction_id: string;
  disaster_type: string;
  zone_id?: string | null;
  zone: string;
  region_id?: string | null;
  risk_score: number;
  risk_level: string;
  confidence: number;
  contributing_factors: string[];
  recommendations: string[];
  explanation: string;
  features: Record<string, number>;
  data_status: string;
  data_freshness_seconds?: number | null;
  stale: boolean;
  created_at: string;
}

export interface RiskSummary {
  latest: RiskPrediction | null;
  trend: RiskPrediction[];
  warning_status: string;
  updated_at?: string | null;
}

export interface TravelSafetyResponse {
  destination: string;
  latitude?: number | null;
  longitude?: number | null;
  risk_score: number;
  risk_level: string;
  hazards: string[];
  weather_summary: string;
  active_alerts: string[];
  route_status: string;
  recommendation: 'SAFE' | 'CAUTION' | 'NOT_RECOMMENDED' | 'CRITICAL' | string;
  reasons: string[];
  safer_alternatives: string[];
  last_updated: string;
  data_status?: string;
  data_sources?: string[];
  freshness_seconds?: number | null;
}

export interface MapOverview {
  generated_at: string;
  data_status: string;
  affected_population: number;
  risks: MapRisk[];
  zones: MapZone[];
  hazards: MapHazard[];
  sensors: MapSensor[];
  incidents: MapIncident[];
  rescue_requests: MapRescueRequest[];
  resources: MapResource[];
  routes: MapRoute[];
  alerts: MapAlert[];
}

export interface MapRisk { id: string; zone_id: string; zone: string; disaster_type: string; risk_score: number; risk_level: string; confidence: number; timestamp?: string; data_freshness_seconds?: number | null; stale: boolean; contributing_factors: string[]; geometry?: GeoJSONGeometry | null; data_status?: string; is_demo?: boolean; }
export interface MapZone { id: string; region_id: string; name: string; population?: number | null; latitude?: number | null; longitude?: number | null; elevation_m?: number | null; slope_deg?: number | null; vulnerability_score?: number | null; hazard_classification?: string | null; geometry?: GeoJSONGeometry | null; geometry_source?: string; is_demo?: boolean; }
export interface MapHazard { id: string; zone_id: string; name: string; hazard_type: string; population?: number | null; geometry?: GeoJSONGeometry | null; geometry_source?: string; is_demo?: boolean; }
export interface MapSensor { id: string; sensor_id: string; type: string; zone_id?: string | null; location?: string | null; latitude?: number | null; longitude?: number | null; value: number; previous_value?: number | null; trend: string; status: string; unit?: string | null; last_update?: string; source: string; is_demo?: boolean; }
export interface MapIncident { id: string; incident_id: string; disaster_type: string; risk_level: string; priority?: number | null; people_affected?: number | null; location: string; status: string; created_at?: string; latitude?: number | null; longitude?: number | null; source?: string; is_demo?: boolean; }
export interface MapRescueRequest { id: string; request_id: string; zone_id?: string | null; location: string; latitude?: number | null; longitude?: number | null; people_count: number; injured_count: number; priority_score?: number | null; priority_level: string; status: string; created_at?: string; }
export interface MapResource { id: string; name: string; type: string; location: string; latitude?: number | null; longitude?: number | null; status: string; capacity?: number | null; occupied?: number | null; current_assignment?: string | null; contact?: string | null; last_updated?: string; is_demo?: boolean; }
export interface MapRoute { id: number; incident_id: string; resource_id?: string | null; origin?: string | null; destination?: string | null; status: string; distance_m?: number | null; eta_seconds?: number | null; route_version?: number; geometry_source?: string | null; geometry: GeoJSONGeometry; }
export interface MapAlert { id: number; zone_id?: string | null; region_id?: string | null; title: string; message: string; level: string; alert_type?: string | null; created_at?: string; geometry?: GeoJSONGeometry | null; is_demo?: boolean; }
export type GeoJSONGeometry = { type: 'Point' | 'LineString' | 'Polygon'; coordinates: any; };


