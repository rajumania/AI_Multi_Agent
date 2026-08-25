from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from backend.services.road_network import road_network
from backend.api.deps import get_current_principal

router = APIRouter(prefix="/api/v1/routes", tags=["Road Routing"])

@router.get("/calculate")
def calculate_route(
    origin: str,
    destination: str,
    origin_lat: Optional[float] = None,
    origin_lng: Optional[float] = None,
    destination_lat: Optional[float] = None,
    destination_lng: Optional[float] = None,
    principal=Depends(get_current_principal),
):
    """Calculate a route from exact coordinates or known campus locations."""
    if any(value is not None for value in (origin_lat, origin_lng, destination_lat, destination_lng)):
        if None in (origin_lat, origin_lng, destination_lat, destination_lng):
            raise HTTPException(status_code=422, detail="All route coordinates must be supplied together.")
        route = road_network.get_route_between_coordinates(origin_lat, origin_lng, destination_lat, destination_lng)
        if route is None:
            raise HTTPException(status_code=422, detail="Reliable road geometry is unavailable for these coordinates.")
        return {
            **route,
            "origin": origin,
            "destination": destination,
            "eta_minutes": round(route["eta_seconds"] / 60.0, 1),
        }

    origin_node = road_network.map_location_to_node(origin)
    dest_node = road_network.map_location_to_node(destination)
    path, distance = road_network.get_shortest_path(origin_node, dest_node)
    if not path:
        raise HTTPException(status_code=400, detail=f"No route found between '{origin}' and '{destination}'")

    coords = road_network.get_path_coordinates(path)
    eta_seconds = int(distance / 10.0) if distance > 0 else 0
    return {
        "origin": origin,
        "origin_node": origin_node,
        "destination": destination,
        "destination_node": dest_node,
        "path": path,
        "coordinates": coords,
        "distance_meters": int(distance),
        "eta_seconds": eta_seconds,
        "eta_minutes": round(eta_seconds / 60.0, 1),
        "source": "CAMPUS_GRAPH",
    }
