from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from backend.services.road_network import road_network

router = APIRouter(prefix="/api/v1/routes", tags=["Road Routing"])

@router.get("/calculate")
def calculate_route(origin: str, destination: str):
    """Calculates road-based routing between two campus locations."""
    origin_node = road_network.map_location_to_node(origin)
    dest_node = road_network.map_location_to_node(destination)

    path, distance = road_network.get_shortest_path(origin_node, dest_node)
    if not path:
        raise HTTPException(status_code=400, detail=f"No route found between '{origin}' and '{destination}'")

    coords = road_network.get_path_coordinates(path)
    # Estimate travel time assuming 10 m/s (36 km/h) average speed on campus
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
        "eta_minutes": round(eta_seconds / 60.0, 1)
    }
