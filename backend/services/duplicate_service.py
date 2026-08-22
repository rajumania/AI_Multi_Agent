import difflib
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from backend.database.models import IncidentDB


class DuplicateService:
    """
    Automatic Duplicate Detection & Corroboration Clustering Service.
    Clusters incoming emergency reports into primary incidents if they refer to the
    same campus block, incident type, and within a recent time window (e.g. 60 mins).
    """

    def find_matching_incident(
        self,
        description: str,
        location: str,
        incident_type: str,
        db: Session,
        window_minutes: int = 60
    ) -> Optional[IncidentDB]:
        now = datetime.now(timezone.utc)
        time_cutoff = now - timedelta(minutes=window_minutes)

        # Look for open incidents (not resolved or closed) within the time window
        candidates = db.query(IncidentDB).filter(
            IncidentDB.status.notin_(["resolved", "closed", "rejected", "cancelled"]),
            IncidentDB.created_at >= time_cutoff
        ).all()

        loc_clean = location.lower().strip()
        type_clean = incident_type.lower().strip()

        for cand in candidates:
            cand_loc = cand.location.lower().strip()
            cand_type = cand.incident_type.lower().strip()

            # Check location match or substring match
            loc_match = (
                loc_clean in cand_loc or
                cand_loc in loc_clean or
                difflib.SequenceMatcher(None, loc_clean, cand_loc).ratio() > 0.7
            )

            # Check type match or general emergency alignment
            type_match = (
                type_clean == cand_type or
                type_clean == "unknown" or
                cand_type == "unknown" or
                (type_clean in ["fire", "explosion"] and cand_type in ["fire", "explosion"])
            )

            if loc_match and type_match:
                return cand

        return None

    def corroborate(
        self,
        primary_incident: IncidentDB,
        new_description: str,
        new_reporter: str,
        new_injured_count: Optional[int],
        db: Session
    ) -> IncidentDB:
        """Adds a corroborating report to an existing active incident."""
        now = datetime.now(timezone.utc)

        # Update summary / description with appended witness report
        witness_tag = f"\n[Corroboration #{len(primary_incident.description.splitlines()) + 1} by {new_reporter} at {now.strftime('%H:%M:%S')}]: \"{new_description}\""
        primary_incident.description = f"{primary_incident.description} {witness_tag}".strip()

        # Update casualties if more definitive information is reported
        if new_injured_count is not None:
            if primary_incident.injured_count is None:
                primary_incident.injured_count = new_injured_count
            else:
                primary_incident.injured_count = max(primary_incident.injured_count, new_injured_count)

        primary_incident.updated_at = now
        db.commit()
        db.refresh(primary_incident)
        return primary_incident


duplicate_service = DuplicateService()
