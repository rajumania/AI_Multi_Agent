import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.database.models import IncidentDB, CampusResourceDB, ResponsePlanDB
from backend.services.event_engine import event_engine
from backend.services.severity_engine import severity_engine
from backend.mcp.campus_tools import campus_mcp_tools
from backend.services.response_service import response_service
from backend.services.dispatch_service import dispatch_service


class SimulationService:
    """
    Digital Twin Autonomous Emergency Simulation Engine.
    Executes autonomous emergency scenarios and handles live resource failure injection
    to showcase dynamic agentic re-planning.
    """

    SCENARIOS = {
        "ublock_fire": {
            "title": "🔥 Active Fire & Smoke in U-Block (CSE & IT)",
            "description": "Dense smoke and active flames observed on 2nd floor CSE lab in U-Block. Occupants initiating stairwell evacuation.",
            "location": "U-Block (CSE & IT)",
            "incident_type": "fire",
            "injured_count": None,
            "primary_ambulance": "AMB-001",
            "fallback_ambulance": "AMB-002",
            "security_unit": "SEC-002",
            "target_lat": 16.2340,
            "target_lng": 80.5520
        },
        "hostel_medical": {
            "title": "🏥 Acute Medical Emergency in Mahalakshmi Hostel",
            "description": "Community member in 3rd floor room collapsed with acute respiratory distress. First aid volunteer on scene.",
            "location": "Mahalakshmi & Vasishta Hostels",
            "incident_type": "medical",
            "injured_count": 1,
            "primary_ambulance": "AMB-002",
            "fallback_ambulance": "AMB-001",
            "security_unit": "SEC-001",
            "target_lat": 16.2315,
            "target_lng": 80.5535
        },
        "gate_security": {
            "title": "🚨 Security Perimeter Breach at Main Gate",
            "description": "Unauthorized speeding vehicle bypassed the Main Response Gate barricade heading towards Academic Quad.",
            "location": "Main Response Gate",
            "incident_type": "security",
            "injured_count": 0,
            "primary_ambulance": "AMB-001",
            "fallback_ambulance": "AMB-002",
            "security_unit": "SEC-001",
            "target_lat": 16.2320,
            "target_lng": 80.5490
        }
    }

    def start_scenario(self, scenario_key: str, db: Session) -> Dict[str, Any]:
        """Initiates an autonomous digital twin scenario and generates the full agent decision loop."""
        scenario = self.SCENARIOS.get(scenario_key, self.SCENARIOS["ublock_fire"])
        now = datetime.now(timezone.utc)

        # Clear any prior blocked edges for a fresh simulation run
        from backend.services.road_network import road_network
        road_network.clear_blocked_edges()

        # 1. Create Incident
        inc_id = f"SIM-{now.strftime('%H%M%S')}-{scenario['incident_type'].upper()[:3]}"
        incident = IncidentDB(
            incident_id=inc_id,
            description=scenario["description"],
            incident_type=scenario["incident_type"],
            location=scenario["location"],
            severity="high",
            injured_count=scenario["injured_count"],
            status="awaiting_approval",
            current_step="Multi-agent emergency plan formulated. Awaiting commander authorization for public broadcast.",
            next_action="Commander must authorize deployment before units depart.",
            reported_by="AITAM Digital Twin Simulator",
            created_at=now,
            updated_at=now
        )
        db.add(incident)
        db.commit()
        db.refresh(incident)

        # 2. Log Supervisor Agent Trace
        event_engine.log_trace(
            incident_id=inc_id,
            agent_name="Supervisor Agent",
            action="evaluate_incident_intake",
            thought=f"Received emergency intake at {scenario['location']}. Initiating deterministic severity evaluation and spatial geocoding.",
            confidence=0.96,
            why=f"High priority report matching {scenario['incident_type']} keywords inside active response area."
        )

        # 3. Evaluate Severity with Deterministic Engine
        sev_res = severity_engine.evaluate(
            incident_type=scenario["incident_type"],
            description=scenario["description"],
            location=scenario["location"],
            injured_count=scenario["injured_count"],
            corroboration_count=2
        )
        incident.severity = sev_res.level
        incident.summary = sev_res.explanation
        db.commit()

        event_engine.log_trace(
            incident_id=inc_id,
            agent_name="Severity & Triage Engine",
            action="score_threat_level",
            thought=f"Calculated threat score: {sev_res.score}/100 ➔ Level: {sev_res.level.upper()}.",
            confidence=sev_res.confidence,
            why=sev_res.explanation
        )

        # 4. Agent Tool Invocations
        sec_team = campus_mcp_tools.find_nearest_security_team(scenario["target_lat"], scenario["target_lng"], db)
        event_engine.log_trace(
            incident_id=inc_id,
            agent_name="Security Agent",
            action="find_nearest_security_team",
            thought=f"Querying MCP resource layer for closest guard squad to {scenario['location']}.",
            tool_call={"tool": "find_nearest_security_team", "result": sec_team},
            confidence=0.94,
            why=f"{sec_team['name'] if sec_team else 'Security Alpha'} stationed within {sec_team['distance_meters'] if sec_team else 50}m of incident coordinates."
        )

        amb_team = campus_mcp_tools.find_nearest_ambulance(scenario["target_lat"], scenario["target_lng"], db)
        event_engine.log_trace(
            incident_id=inc_id,
            agent_name="Medical Agent",
            action="find_nearest_ambulance",
            thought=f"Assessing casualty risk and reserving nearest medical unit for triage.",
            tool_call={"tool": "find_nearest_ambulance", "result": amb_team},
            confidence=0.92,
            why=f"{amb_team['name'] if amb_team else 'Ambulance 1'} ready with 2-stretcher capacity at Health Centre."
        )

        route_info = campus_mcp_tools.calculate_emergency_route("AITAM Health Centre", scenario["location"])
        event_engine.log_trace(
            incident_id=inc_id,
            agent_name="Transport Agent",
            action="calculate_emergency_route",
            thought=f"Computing clear ingress corridor for dispatched emergency vehicles.",
            tool_call={"tool": "calculate_emergency_route", "result": route_info},
            confidence=0.95,
            why="Fastest unobstructed route via East Perimeter Road."
        )

        # 5. Formulate Response Plan
        plan = response_service.generate_plan(inc_id, db=db)

        return {
            "status": "scenario_initiated",
            "scenario": scenario_key,
            "incident_id": inc_id,
            "incident": incident,
            "plan_id": plan.plan_id,
            "severity_evaluation": sev_res,
            "decision_trace": event_engine.get_decision_trace(inc_id)
        }

    def inject_resource_failure(self, incident_id: str, failed_resource_id: str, db: Session) -> Dict[str, Any]:
        """
        Simulates an active resource breakdown (e.g. AMB-001 engine failure during transit).
        The Monitoring Agent detects the fault and triggers autonomous re-planning.
        """
        now = datetime.now(timezone.utc)

        # 1. Mark failed resource as unavailable
        failed_res = db.query(CampusResourceDB).filter(CampusResourceDB.resource_id == failed_resource_id).first()
        if failed_res:
            failed_res.availability_status = "busy"  # Out of commission
            failed_res.last_updated = now

        # 2. Log Monitoring Agent Failure Detection Trace
        event_engine.log_trace(
            incident_id=incident_id,
            agent_name="Monitoring Agent",
            action="detect_telemetry_anomaly",
            thought=f"⚠️ CRITICAL ALERT: Unit {failed_resource_id} ({failed_res.name if failed_res else 'Assigned Unit'}) reported telemetry timeout/mechanical breakdown.",
            confidence=0.99,
            why="Heartbeat failure detected from vehicle GPS transponder."
        )

        # 3. Autonomous Re-Planning Trigger
        incident = db.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
        if not incident:
            return {"status": "error", "message": "Incident not found"}

        # Search for alternate ambulance / security
        alternate_unit = db.query(CampusResourceDB).filter(
            CampusResourceDB.resource_type == (failed_res.resource_type if failed_res else "ambulance"),
            CampusResourceDB.resource_id != failed_resource_id,
            CampusResourceDB.availability_status == "available"
        ).first()

        alt_id = alternate_unit.resource_id if alternate_unit else "AMB-002"

        event_engine.log_trace(
            incident_id=incident_id,
            agent_name="Medical Agent (Autonomous Re-Planner)",
            action="replan_alternate_resource",
            thought=f"Re-evaluating response fleet: Selected alternate asset {alt_id} ({alternate_unit.name if alternate_unit else 'Ambulance 2'}).",
            tool_call={"substituted_unit": alt_id, "replaced_unit": failed_resource_id},
            confidence=0.94,
            why=f"Closest available operational {failed_res.resource_type if failed_res else 'unit'} in response pool."
        )

        # Update latest response plan
        plan = db.query(ResponsePlanDB).filter(ResponsePlanDB.incident_id == incident_id).order_by(ResponsePlanDB.created_at.desc()).first()
        if plan:
            try:
                allocated = json.loads(plan.allocated_resources) if isinstance(plan.allocated_resources, str) else list(plan.allocated_resources or [])
            except Exception:
                allocated = []
            allocated = [alt_id if r == failed_resource_id else r for r in allocated]
            if alt_id not in allocated:
                allocated.append(alt_id)
            plan.allocated_resources = json.dumps(allocated)
            plan.updated_at = now

        incident.current_step = f"Dynamic Re-Planning: {failed_resource_id} replaced with {alt_id}. Route re-routed."
        incident.updated_at = now
        db.commit()

        return {
            "status": "replan_success",
            "incident_id": incident_id,
            "failed_resource": failed_resource_id,
            "substitute_resource": alt_id,
            "new_plan": plan,
            "decision_trace": event_engine.get_decision_trace(incident_id)
        }


simulation_service = SimulationService()
