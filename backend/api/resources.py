from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.database.models import CampusResourceDB
from backend.models.resources import CampusResourceRead, ResourceType, AvailabilityStatus
from backend.mcp.tools.facilities import find_nearby_resources

router = APIRouter(prefix="/api/v1/resources", tags=["Campus Resources"])


@router.get("", response_model=List[CampusResourceRead])
def list_resources(
    resource_type: Optional[ResourceType] = Query(None, alias="type"),
    availability: Optional[AvailabilityStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db)
):
    """
    Retrieve campus emergency resources from SQLite database.
    """
    query = db.query(CampusResourceDB)
    if resource_type:
        query = query.filter(CampusResourceDB.resource_type == resource_type.value)
    if availability:
        query = query.filter(CampusResourceDB.availability_status == availability.value)
    
    return query.all()


@router.get("/search/available", response_model=List[CampusResourceRead])
def search_available_resources(
    resource_type: Optional[str] = Query(None, alias="type"),
    location: Optional[str] = Query(None, alias="location"),
    limit: int = Query(10, ge=1, le=50)
):
    """
    MCP-backed location-aware search for available campus resources.
    """
    results = find_nearby_resources(
        resource_type=resource_type,
        location=location,
        availability="available",
        limit=limit
    )
    return results


@router.get("/{resource_id}", response_model=CampusResourceRead)
def get_resource_by_id(resource_id: str, db: Session = Depends(get_db)):
    """
    Retrieve details of a single campus resource.
    """
    resource = db.query(CampusResourceDB).filter(CampusResourceDB.resource_id == resource_id).first()
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resource '{resource_id}' not found."
        )
    return resource
