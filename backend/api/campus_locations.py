from fastapi import APIRouter

from backend.services.campus_locations import campus_location_catalog


router = APIRouter(prefix="/api/v1/campus-locations", tags=["Campus Locations"])


@router.get("")
def list_campus_locations():
    """Return the existing project campus catalog for map labels/pickers."""
    return campus_location_catalog()
