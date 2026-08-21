import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.database.models import IncidentDB, ResponsePlanDB, CampusResourceDB
from backend.models.incident import IncidentStatus
from backend.models.dispatch import DispatchExecutionResult, BroadcastNotification, IncidentResolutionRequest
from backend.services.audit_service import audit_service


class DispatchService:
    """
    Step 7 Execution & Dispatch Service:
    - Executes approved action plans by dispatching physical units (updating SQLite availability to 'busy').
    - Disseminates multi-channel simulated broadcasts (SMS, App Push, Digital Signage, PA).
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

        # 4. Generate Multi-Channel Emergency Broadcast Notifications
        broadcasts: List[BroadcastNotification] = [
            BroadcastNotification(
                channel="Campus Emergency SMS",
                recipient_group="Campus Community & First Responders",
                headline=f"ALERT: {incident.incident_type.upper()} at {incident.location}",
                message=f"CampusFlow Advisory: Response underway for {incident.incident_type} near {incident.location}. Stay clear of emergency access routes.",
                timestamp=now,
                status="sent"
            ),
            BroadcastNotification(
                channel="Mobile Safety App Push",
                recipient_group="Students & Faculty within 500m",
                headline=f"Active Safety Zone: {incident.location}",
                message=f"Please follow steward guidance. Emergency response units ({', '.join(dispatched_resources) if dispatched_resources else 'On-duty Patrol'}) deployed.",
                timestamp=now,
                status="delivered"
            ),
            BroadcastNotification(
                channel="Campus PA Audio & Digital Signage",
                recipient_group="Zone Occupants",
                headline=f"Emergency Advisory - {incident.location}",
                message="Attention all personnel: Proceed in orderly fashion to the designated muster point.",
                timestamp=now,
                status="broadcasted"
            ),
        ]

        # 5. Transition Incident status
        incident.status = "in_progress"
        incident.updated_at = now
        db.commit()

        # 6. Audit Logging
        audit_service.log(
            action_type="automation_execution",
            description=f"Automated dispatch executed for plan {plan_id}. Dispatched {len(dispatched_resources)} unit(s) ({', '.join(dispatched_resources)}). Broadcasted 3 multi-channel alert stream(s).",
            incident_id=incident.incident_id,
            plan_id=plan_id,
            actor="dispatch_engine",
            details={
                "dispatched_resources": dispatched_resources,
                "broadcast_channels": [b.channel for b in broadcasts],
            },
            db=db
        )

        return DispatchExecutionResult(
            plan_id=plan.plan_id,
            incident_id=incident.incident_id,
            execution_status="dispatched",
            dispatched_resources=dispatched_resources,
            broadcast_alerts=broadcasts,
            executed_at=now,
            execution_notes=f"Dispatched {len(dispatched_resources)} units and broadcasted multi-channel alerts for {incident.location}."
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

        # 2. Update Incident Status
        incident.status = IncidentStatus.RESOLVED.value
        incident.summary = f"{incident.summary or ''} [RESOLVED: {payload.resolution_notes}]".strip()
        incident.updated_at = now
        db.commit()
        db.refresh(incident)

        # 3. Audit Logging
        audit_service.log(
            action_type="incident_resolved",
            description=f"Incident '{incident_id}' marked RESOLVED by {payload.resolved_by}. Released {len(released_resources)} resource(s) ({', '.join(released_resources) if released_resources else 'None'}) back to available pool. Resolution Notes: {payload.resolution_notes}",
            incident_id=incident.incident_id,
            actor=payload.resolved_by,
            details={
                "resolution_notes": payload.resolution_notes,
                "released_resources": released_resources,
                "resolved_at": now.isoformat()
            },
            db=db
        )

        return incident


dispatch_service = DispatchService()
