from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.database.database import get_db
from backend.database.models import CampusResourceDB
from backend.api.deps import get_current_principal
from backend.models.resources import CampusResourceRead, ResourceType, AvailabilityStatus
from backend.mcp.tools.facilities import find_nearby_resources

router = APIRouter(prefix="/api/v1/resources", tags=["Campus Resources"])


@router.get("", response_model=List[CampusResourceRead])
def list_resources(
    resource_type: Optional[ResourceType] = Query(None, alias="type"),
    availability: Optional[AvailabilityStatus] = Query(None, alias="status"),
    include_demo: bool = Query(False, description="Include explicitly labelled demonstration resources."),
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
):
    """
    Retrieve campus emergency resources from SQLite database.
    """
    query = db.query(CampusResourceDB)
    # The generic campus inventory remains scoped to real campus assets. The
    # disaster map has its own consolidated view and intentionally includes
    # labelled Nepal demo assets; callers can opt into those here explicitly.
    if not include_demo:
        query = query.filter(CampusResourceDB.is_demo == 0)
    if resource_type:
        query = query.filter(CampusResourceDB.resource_type == resource_type.value)
    if availability:
        query = query.filter(CampusResourceDB.availability_status == availability.value)
    if principal is not None and principal.is_department:
        query = query.filter(CampusResourceDB.department == principal.department)
    elif principal is not None and principal.is_user:
        return []
    
    return query.all()


@router.get("/search/available", response_model=List[CampusResourceRead])
def search_available_resources(
    resource_type: Optional[str] = Query(None, alias="type"),
    location: Optional[str] = Query(None, alias="location"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    principal=Depends(get_current_principal),
):
    """
    MCP-backed location-aware search for available campus resources.
    """
    if principal.is_user:
        return []
    results = find_nearby_resources(
        resource_type=resource_type,
        location=location,
        availability="available",
        limit=limit
    )
    if principal.is_department:
        results = [item for item in results if item.get("department") == principal.department]
    return results


@router.get("/{resource_id}", response_model=CampusResourceRead)
def get_resource_by_id(resource_id: str, db: Session = Depends(get_db), principal=Depends(get_current_principal)):
    """
    Retrieve details of a single campus resource.
    """
    resource = db.query(CampusResourceDB).filter(CampusResourceDB.resource_id == resource_id).first()
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resource '{resource_id}' not found."
        )
    if principal is not None and principal.is_department and resource.department != principal.department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Resource '{resource_id}' not found.")
    if principal is not None and principal.is_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Resource '{resource_id}' not found.")
    return resource
