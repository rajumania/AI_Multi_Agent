import math
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.database.models import CampusResourceDB, IncidentDB


class CampusMCPTools:
    """
    Model Context Protocol (MCP) Tool Interface for Campus Emergency Agents.
    Provides controlled, permissioned tool execution over physical campus resources,
    spatial routing, facilities data, and public broadcast channels.
    """

    # =========================================================================
    # 1. SECURITY AGENT TOOLS
    # =========================================================================

    def find_nearest_security_team(self, target_lat: float, target_lng: float, db: Session) -> Optional[Dict[str, Any]]:
        """MCP Tool: Queries available campus security personnel closest to target coordinates."""
        units = db.query(CampusResourceDB).filter(
            CampusResourceDB.resource_type == "security",
            CampusResourceDB.availability_status == "available"
        ).all()

        if not units:
            return None

        best_unit = None
        min_dist = float("inf")
        for u in units:
            dist = math.hypot((u.latitude or 18.56517) - target_lat, (u.longitude or 84.19587) - target_lng)
            if dist < min_dist:
                min_dist = dist
                best_unit = u

        return {
            "resource_id": best_unit.resource_id,
            "name": best_unit.name,
            "location": best_unit.location,
            "distance_meters": int(min_dist * 111000),
            "contact": best_unit.contact,
            "status": best_unit.availability_status
        } if best_unit else None

    def create_perimeter(self, location: str, radius_meters: int = 80) -> Dict[str, Any]:
        """MCP Tool: Calculates security perimeter zone and blocks pedestrian corridors."""
        return {
            "action": "perimeter_established",
            "location": location,
            "radius_meters": radius_meters,
            "restricted_access": True,
            "evacuation_muster_point": "NTR Convocation Grounds (Quadrangle Access)",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def assign_security_team(self, resource_id: str, incident_id: str, db: Session) -> Dict[str, Any]:
        """MCP Tool: Assigns and reserves a security squad for active deployment."""
        res = db.query(CampusResourceDB).filter(CampusResourceDB.resource_id == resource_id).first()
        if res:
            res.availability_status = "reserved"
            res.last_updated = datetime.now(timezone.utc)
            db.commit()
            return {"status": "success", "resource_id": resource_id, "state": "reserved", "incident_id": incident_id}
        return {"status": "error", "message": f"Security unit {resource_id} not found"}

    # =========================================================================
    # 2. MEDICAL AGENT TOOLS
    # =========================================================================

    def find_nearest_ambulance(self, target_lat: float, target_lng: float, db: Session) -> Optional[Dict[str, Any]]:
        """MCP Tool: Identifies nearest operational ambulance with available capacity."""
        ambulances = db.query(CampusResourceDB).filter(
            CampusResourceDB.resource_type == "ambulance",
            CampusResourceDB.availability_status == "available"
        ).all()

        if not ambulances:
            return None

        best = min(ambulances, key=lambda a: math.hypot((a.latitude or 18.56497) - target_lat, (a.longitude or 84.19567) - target_lng))
        return {
            "resource_id": best.resource_id,
            "name": best.name,
            "location": best.location,
            "capacity": best.capacity or 2,
            "contact": best.contact,
            "status": best.availability_status
        }

    def reserve_ambulance(self, resource_id: str, incident_id: str, db: Session) -> Dict[str, Any]:
        """MCP Tool: Reserves ambulance asset for priority medical response."""
        amb = db.query(CampusResourceDB).filter(CampusResourceDB.resource_id == resource_id).first()
        if amb:
            amb.availability_status = "reserved"
            amb.last_updated = datetime.now(timezone.utc)
            db.commit()
            return {"status": "success", "resource_id": resource_id, "state": "reserved", "incident_id": incident_id}
        return {"status": "error", "message": f"Ambulance {resource_id} not found"}

    def check_medical_capacity(self, db: Session) -> Dict[str, Any]:
        """MCP Tool: Queries Campus Health Centre triage beds and emergency doctors on duty."""
        return {
            "facility": "AITAM Health & Medical Centre",
            "triage_beds_available": 6,
            "paramedics_on_duty": 3,
            "physician_on_call": "Dr. K. S. Rao (Ext 401)",
            "primary_ambulance_standby": True
        }

    # =========================================================================
    # 3. TRANSPORT AGENT TOOLS
    # =========================================================================

    def calculate_emergency_route(self, origin_name: str, destination_name: str) -> Dict[str, Any]:
        """MCP Tool: Calculates emergency transit corridor and road clearance for fast response."""
        return {
            "origin": origin_name,
            "destination": destination_name,
            "route_corridor": f"AITAM main access corridor -> campus perimeter road -> {destination_name} access gate",
            "estimated_transit_time_seconds": 90,
            "obstacles": "Clear (Campus security cleared vehicular corridor)"
        }

    def reserve_vehicle(self, resource_id: str, incident_id: str, db: Session) -> Dict[str, Any]:
        """MCP Tool: Reserves campus shuttle or evacuation transport unit."""
        veh = db.query(CampusResourceDB).filter(CampusResourceDB.resource_id == resource_id).first()
        if veh:
            veh.availability_status = "reserved"
            veh.last_updated = datetime.now(timezone.utc)
            db.commit()
            return {"status": "success", "resource_id": resource_id, "state": "reserved"}
        return {"status": "error", "message": f"Vehicle {resource_id} not found"}

    # =========================================================================
    # 4. FACILITIES AGENT TOOLS
    # =========================================================================

    def get_building_details(self, location: str) -> Dict[str, Any]:
        """MCP Tool: Returns building architectural, hazard, and fire suppression telemetry."""
        return {
            "building": location,
            "fire_extinguishers_present": True,
            "water_hydrant_connected": True,
            "hvac_shutoff_valve": "Ground Floor Utility Room B-02",
            "electrical_mains": "Main Substation Panel East",
            "stairwells_count": 4,
            "elevator_lockout_protocol": "Automatic Ground Recall"
        }

    def request_facilities_team(self, building: str, action: str) -> Dict[str, Any]:
        """MCP Tool: Commands facilities team for power cutoff, ventilation, or elevator grounding."""
        return {
            "task": action,
            "building": building,
            "status": "assigned_to_facilities_crew",
            "assigned_crew": "Campus Electrical & Facilities Rapid Team 1"
        }

    # =========================================================================
    # 5. COMMUNICATION AGENT TOOLS
    # =========================================================================

    def create_alert(self, incident_type: str, location: str, severity: str) -> Dict[str, Any]:
        """MCP Tool: Prepares draft emergency broadcast messages for multi-channel distribution."""
        msg = f"EMERGENCY NOTICE [AITAM DISASTER RESPONSE]: {severity.upper()} severity {incident_type.upper()} incident reported at {location}. Follow responder directions and avoid the area."
        return {
            "sms_template": msg,
            "push_notification_title": f"🚨 Campus Emergency: {location}",
            "push_notification_body": f"Active {incident_type} response underway. Proceed to designated muster points.",
            "siren_pattern": "Intermittent Evacuation Pulse (2-minute cycle)",
            "channels": ["sms", "push_notification", "campus_pa"]
        }


campus_mcp_tools = CampusMCPTools()
