import json
import math
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.database.models import IncidentDB, ResponsePlanDB, CampusResourceDB
from backend.models.incident import IncidentStatus
from backend.models.dispatch import DispatchExecutionResult, BroadcastNotification, IncidentResolutionRequest
from backend.services.audit_service import audit_service
from backend.database.database import SessionLocal
from backend.config import settings
from backend.services.road_network import road_network
from backend.services.event_engine import event_engine


from backend.services.adapters.sms_adapter import sms_adapter
from backend.services.adapters.push_adapter import push_adapter
from backend.services.adapters.email_adapter import email_adapter
from backend.services.adapters.voice_adapter import voice_adapter
from backend.services.adapters.dispatch_adapter import dispatch_adapter
from backend.services.responder_directory import responder_directory


class DispatchService:
    """
    Step 7 Execution & Dispatch Service:
    - Executes approved action plans through real service adapters (SMS, Push, Email, Voice, CAD Dispatch).
    - Updates resource availability state in SQLite database.
    - Emits real-time WebSocket events for all provider operations.
    - Manages complete incident resolution and automatic resource pool release.
    """

    def execute_plan(self, plan_id: str, db: Session) -> DispatchExecutionResult:
        # 1. Fetch response plan
        plan = db.query(ResponsePlanDB).filter(ResponsePlanDB.plan_id == plan_id).first()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Response Plan '{plan_id}' not found."
            )

        # 2. Strict Safety Gate: High-impact actions require approval
        if plan.approval_status != "approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot execute unapproved response plan. Current status: '{plan.approval_status}'. Human approval is required."
            )

        incident = db.query(IncidentDB).filter(IncidentDB.incident_id == plan.incident_id).first()
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent incident '{plan.incident_id}' not found."
            )

        now = datetime.now(timezone.utc)
        allocated_ids: List[str] = json.loads(plan.allocated_resources) if isinstance(plan.allocated_resources, str) else plan.allocated_resources

        # 3. Dispatch Physical Campus Resources in SQLite
        dispatched_resources: List[str] = []
        if allocated_ids:
            for rid in allocated_ids:
                resource = db.query(CampusResourceDB).filter(CampusResourceDB.resource_id == rid).first()
                if resource:
                    resource.availability_status = "busy"
                    resource.last_updated = now
                    dispatched_resources.append(rid)

        # 4. Authorized Campus Dispatch Integration Request
        event_engine.publish_event(
            event_name="dispatch_requested",
            incident_id=incident.incident_id,
            payload={
                "event_name": "dispatch_requested",
                "plan_id": plan_id,
                "dispatched_resources": dispatched_resources,
                "location": incident.location
            }
        )
        dispatch_res = dispatch_adapter.dispatch_resources(incident.incident_id, plan_id, dispatched_resources, incident.location)
        event_engine.publish_event(
            event_name="dispatch_accepted" if dispatch_res.success else "dispatch_failed",
            incident_id=incident.incident_id,
            payload={
                "event_name": "dispatch_accepted" if dispatch_res.success else "dispatch_failed",
                "provider": dispatch_res.provider,
                "status": dispatch_res.status.value,
                "dispatch_id": dispatch_res.message_id or "N/A",
                "details": dispatch_res.details
            }
        )

        # 5. Multi-Channel External Operations via Adapters
        broadcasts: List[BroadcastNotification] = []

        # A. SMS is deliberately optional in the free real-operations demo.
        sms_body = f"CAMPUSFLOW ALERT: {incident.incident_type.upper()} reported near {incident.location}. Dispatched units: {', '.join(dispatched_resources) if dispatched_resources else 'Patrol'}. Keep routes clear."
        broadcasts.append(BroadcastNotification(
            channel="SMS (Optional)",
            recipient_group="Not configured for this demonstration",
            headline=f"ALERT: {incident.incident_type.upper()} at {incident.location}",
            message=sms_body,
            timestamp=now,
            status="OPTIONAL / NOT CONFIGURED"
        ))

        # B. Push Notification Dispatch
        push_tokens = [settings.TEST_DEVICE_TOKEN] if settings.TEST_DEVICE_TOKEN else []
        push_res = push_adapter.send_push(
            title=f"Emergency Alert: {incident.incident_type.upper()}",
            body=f"Active emergency near {incident.location}. Emergency units in transit.",
            target_tokens=push_tokens
        )
        broadcasts.append(BroadcastNotification(
            channel=f"Push ({push_res.provider})",
            recipient_group=f"Registered Mobile Devices ({push_res.recipient_count} devices)",
            headline=f"Active Safety Zone: {incident.location}",
            message=f"Please follow steward guidance. Active emergency response deployed.",
            timestamp=now,
            status=f"{push_res.status.value.upper()} - {push_res.message_id or push_res.error or 'N/A'}"
        ))

        # C. Email Dispatch
        email_recipients = [settings.TEST_EMAIL_ADDRESS] if settings.TEST_EMAIL_ADDRESS else []
        email_res = email_adapter.send_email(
            recipients=email_recipients,
            subject=f"[EMERGENCY ALERT] {incident.incident_type.upper()} at {incident.location}",
            body_text=f"CampusFlow Emergency Response System\nCampusFlow Incident ID: {incident.incident_id}\nIncident: {incident.incident_type}\nSeverity: {incident.severity}\nLocation: {incident.location}\nTimestamp: {now.isoformat()}\nRecommended response: Follow the approved response plan and campus commander directions.\nAssigned agents/responders: {', '.join(dispatched_resources) or 'Response team'}\nEvacuation instruction: Use the designated safe exit and keep emergency routes clear.\nSummary: {incident.summary}"
        )
        broadcasts.append(BroadcastNotification(
            channel=f"Email ({email_res.provider})",
            recipient_group=f"Campus Operations ({email_res.recipient_count} recipients)",
            headline=f"Incident Briefing - {incident.location}",
            message="Email adapter evaluated; no delivery is claimed unless the configured SMTP provider confirms it.",
            timestamp=now,
            status=f"{email_res.status.value.upper()} - {email_res.message_id or email_res.error or 'N/A'}"
        ))

        # D. AI Voice Audio Announcement
        voice_audio = voice_adapter.generate_voice_audio(
            f"Attention all personnel. An emergency involving {incident.incident_type} has been reported at {incident.location}. Please follow safety instructions."
        )
        broadcasts.append(BroadcastNotification(
            channel="AI Voice Announcement",
            recipient_group="Campus Broadcasters",
            headline="Voice Advisory Ready",
            message=f"Generated AI audio announcement: '{voice_audio.get('text')}'",
            timestamp=now,
            status=f"READY ({voice_audio.get('audio_id')})"
        ))

        # 6. Transition Incident status
        incident.status = "in_progress"
        incident.current_step = f"Emergency response initiated. Units dispatched: {', '.join(dispatched_resources) if dispatched_resources else 'Patrol'}. In-app demo alert active; optional provider channels evaluated truthfully."
        incident.next_action = "Response team en-route. Monitoring telemetry and route geometry."
        db.commit()

        event_engine.publish_event(
            event_name="dispatch_started",
            incident_id=incident.incident_id,
            payload={
                "event_name": "dispatch_started",
                "plan_id": plan_id,
                "description": f"Response in progress. {len(dispatched_resources)} campus resource(s) assigned.",
                "dispatched_resources": dispatched_resources,
                "status": incident.status,
            },
            db=db,
        )
        for resource_id in dispatched_resources:
            event_engine.publish_event(
                event_name="resource_dispatched",
                incident_id=incident.incident_id,
                payload={
                    "event_name": "resource_dispatched",
                    "resource_id": resource_id,
                    "description": f"Resource {resource_id} assigned to the emergency.",
                },
                db=db,
            )

        # Trigger background vehicle movement simulation
        if dispatched_resources:
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    loop.create_task(run_vehicle_simulation(incident.incident_id, plan.plan_id, dispatched_resources))
            except RuntimeError:
                pass


        # 6. Audit Logging
        audit_service.log(
            action_type="automation_execution",
            description=f"Response workflow initiated for plan {plan_id}. Dispatched {len(dispatched_resources)} unit(s). In-app demo alert displayed; optional provider results recorded.",
            incident_id=incident.incident_id,
            plan_id=plan_id,
            actor="System",
            details={
                "dispatched_resources": dispatched_resources,
                "broadcast_channels": [b.channel for b in broadcasts],
            },
            db=db
        )

        event_engine.publish_event(
            event_name="demo_push_available",
            incident_id=incident.incident_id,
            payload={
                "event_name": "demo_push_available",
                "description": "In-app DEMO PUSH notification is displayed. No mobile provider delivery claimed.",
                "channel": "DEMO PUSH — IN APP",
            },
            db=db,
        )

        return DispatchExecutionResult(
            plan_id=plan.plan_id,
            incident_id=incident.incident_id,
            execution_status="dispatched",
            dispatched_resources=dispatched_resources,
            broadcast_alerts=broadcasts,
            executed_at=now,
            execution_notes=f"Dispatched {len(dispatched_resources)} units for {incident.location}. In-app DEMO PUSH and browser voice are available; optional external channel results are explicitly reported."
        )

    def resolve_incident(
        self,
        incident_id: str,
        payload: IncidentResolutionRequest,
        db: Session
    ) -> IncidentDB:
        incident = db.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found."
            )

        now = datetime.now(timezone.utc)

        # 1. Find all plans for this incident and release allocated resources
        plans = db.query(ResponsePlanDB).filter(ResponsePlanDB.incident_id == incident_id).all()
        released_resources: List[str] = []

        for p in plans:
            allocated_ids: List[str] = json.loads(p.allocated_resources) if isinstance(p.allocated_resources, str) else p.allocated_resources
            for rid in allocated_ids:
                resource = db.query(CampusResourceDB).filter(CampusResourceDB.resource_id == rid).first()
                if resource and resource.availability_status == "busy":
                    resource.availability_status = "available"
                    resource.last_updated = now
                    released_resources.append(rid)

        # 2. Update Incident Status & Resolution Metadata
        incident.status = IncidentStatus.RESOLVED.value
        incident.resolved_at = now
        incident.resolution_note = payload.resolution_notes
        incident.current_step = f"Situation confirmed under control and resolved by {payload.resolved_by}."
        incident.next_action = "Incident resolved. Ready for administrative closure and archiving."
        incident.summary = f"{incident.summary or ''} [RESOLVED: {payload.resolution_notes}]".strip()
        incident.updated_at = now
        db.commit()
        db.refresh(incident)

        # 3. Audit Logging
        audit_service.log(
            action_type="incident_resolved",
            description=f"Incident '{incident_id}' marked RESOLVED by {payload.resolved_by}. Released {len(released_resources)} resource(s) back to available pool. Note: {payload.resolution_notes}",
            incident_id=incident.incident_id,
            actor=payload.resolved_by,
            details={
                "resolution_notes": payload.resolution_notes,
                "released_resources": released_resources,
                "resolved_at": now.isoformat()
            },
            db=db
        )

        event_engine.publish_event(
            event_name="incident_resolved",
            incident_id=incident.incident_id,
            payload={
                "event_name": "incident_resolved",
                "description": "Incident marked RESOLVED and allocated resources released.",
                "released_resources": released_resources,
                "status": incident.status,
            },
            db=db,
        )

        return incident


async def run_vehicle_simulation(incident_id: str, plan_id: str, resource_ids: List[str]):
    # Allow DB session creation
    db = SessionLocal()
    try:
        incident = db.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
        if not incident:
            return
        
        destination_location = incident.location
        dest_node = road_network.map_location_to_node(destination_location)
        
        tasks = []
        for rid in resource_ids:
            tasks.append(simulate_single_resource(incident_id, plan_id, rid, dest_node))
            
        await asyncio.gather(*tasks)
        
    except Exception as e:
        print(f"[run_vehicle_simulation] Error: {e}")
    finally:
        db.close()


async def simulate_single_resource(incident_id: str, plan_id: str, resource_id: str, dest_node: str):
    db = SessionLocal()
    try:
        resource = db.query(CampusResourceDB).filter(CampusResourceDB.resource_id == resource_id).first()
        if not resource:
            return
            
        # Non-movable resource logic
        if resource.resource_type not in ["ambulance", "security", "vehicle", "fire_response"]:
            resource.availability_status = "busy"
            db.commit()
            return
            
        origin_node = road_network.map_location_to_node(resource.location)
        
        path, distance = road_network.get_shortest_path(origin_node, dest_node)
        if not path:
            path = [origin_node, dest_node]
            distance = 300.0
            
        coords = road_network.get_path_coordinates(path)
        event_engine.publish_event(
            event_name="route_selected",
            incident_id=incident_id,
            payload={
                "event_name": "route_selected",
                "resource_id": resource_id,
                "origin": origin_node,
                "destination": dest_node,
                "route": path,
                "coordinates": coords,
                "distance_meters": int(distance),
                "eta_seconds": int(distance / 10.0) if distance > 0 else 0
            }
        )
        
        resource.availability_status = "dispatched"
        db.commit()
        
        event_engine.publish_event(
            event_name="response_status_changed",
            incident_id=incident_id,
            payload={
                "event_name": "response_status_changed",
                "resource_id": resource_id,
                "status": "dispatched"
            }
        )
        
        await asyncio.sleep(1.0)
        
        resource.availability_status = "en_route"
        db.commit()
        event_engine.publish_event(
            event_name="response_status_changed",
            incident_id=incident_id,
            payload={
                "event_name": "response_status_changed",
                "resource_id": resource_id,
                "status": "en_route"
            }
        )
        
        interpolated = road_network.interpolate_path(coords, step_meters=6.0)
        
        idx = 0
        while idx < len(interpolated):
            current_lat, current_lng = interpolated[idx]
            
            # Find closest node in path to current position to check for roadblocks
            closest_node_idx = 0
            min_dist = float("inf")
            for i, node_name in enumerate(path):
                n_lat, n_lng = road_network.NODES[node_name]
                dist = math.hypot(n_lat - current_lat, n_lng - current_lng)
                if dist < min_dist:
                    min_dist = dist
                    closest_node_idx = i
            
            blocked_detected = False
            for i in range(closest_node_idx, len(path) - 1):
                u, v = path[i], path[i+1]
                if (u, v) in road_network.blocked_edges or (v, u) in road_network.blocked_edges:
                    blocked_detected = True
                    break
                    
            if blocked_detected:
                current_node = path[closest_node_idx]
                new_path, new_distance = road_network.get_shortest_path(current_node, dest_node)
                if new_path and new_path != path[closest_node_idx:]:
                    path = path[:closest_node_idx] + new_path
                    new_coords = road_network.get_path_coordinates(path)
                    remaining_coords = [interpolated[idx]] + new_coords[1:]
                    interpolated = road_network.interpolate_path(remaining_coords, step_meters=6.0)
                    idx = 0
                    coords = new_coords
                    distance = new_distance
                    
                    event_engine.publish_event(
                        event_name="route_blocked",
                        incident_id=incident_id,
                        payload={
                            "event_name": "route_blocked",
                            "resource_id": resource_id,
                            "description": f"En-route segment blocked! Rerouting {resource_id}."
                        }
                    )
                    
                    event_engine.publish_event(
                        event_name="route_recalculated",
                        incident_id=incident_id,
                        payload={
                            "event_name": "route_recalculated",
                            "resource_id": resource_id,
                            "route": path,
                            "coordinates": coords,
                            "distance_meters": int(distance),
                            "eta_seconds": int(distance / 10.0) if distance > 0 else 0
                        }
                    )
            
            lat, lng = interpolated[idx]
            resource = db.query(CampusResourceDB).filter(CampusResourceDB.resource_id == resource_id).first()
            if resource:
                if resource.availability_status not in ["busy", "dispatched", "en_route"]:
                    break
                resource.latitude = lat
                resource.longitude = lng
                db.commit()
                
            rem_distance = 0.0
            if idx < len(interpolated) - 1:
                for k in range(idx, len(interpolated) - 1):
                    y1, x1 = interpolated[k]
                    y2, x2 = interpolated[k+1]
                    rem_distance += math.hypot(y2 - y1, x2 - x1) * 111000.0
                    
            eta_sec = int(rem_distance / 10.0) if rem_distance > 0 else 0
            
            event_engine.publish_event(
                event_name="vehicle_location_updated",
                incident_id=incident_id,
                payload={
                    "event_name": "vehicle_location_updated",
                    "resource_id": resource_id,
                    "latitude": lat,
                    "longitude": lng,
                    "status": "en_route",
                    "distance_remaining": round(rem_distance / 1000.0, 2),
                    "eta_seconds": eta_sec,
                    "route_coordinates": interpolated[idx:]
                }
            )
            
            idx += 1
            await asyncio.sleep(0.4)
            
        # Arrived at destination
        resource = db.query(CampusResourceDB).filter(CampusResourceDB.resource_id == resource_id).first()
        if resource and resource.availability_status in ["busy", "dispatched", "en_route"]:
            resource.availability_status = "busy"
            resource.latitude, resource.longitude = road_network.NODES[dest_node]
            db.commit()
            
            incident_db = db.query(IncidentDB).filter(IncidentDB.incident_id == incident_id).first()
            if incident_db:
                incident_db.current_step = f"Response team ({resource_id}) arrived on-scene at {incident_db.location}."
                incident_db.status = "monitoring"
                db.commit()
                
            event_engine.publish_event(
                event_name="vehicle_arrived",
                incident_id=incident_id,
                payload={
                    "event_name": "vehicle_arrived",
                    "resource_id": resource_id,
                    "status": "arrived",
                    "latitude": road_network.NODES[dest_node][0],
                    "longitude": road_network.NODES[dest_node][1]
                }
            )
            event_engine.publish_event(
                event_name="response_status_changed",
                incident_id=incident_id,
                payload={
                    "event_name": "response_status_changed",
                    "resource_id": resource_id,
                    "status": "arrived"
                }
            )
            
    except Exception as e:
        print(f"[simulate_single_resource] Error in {resource_id}: {e}")
    finally:
        db.close()


dispatch_service = DispatchService()

