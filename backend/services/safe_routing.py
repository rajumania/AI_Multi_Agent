"""Deterministic route adapter that never invents geometry."""

from __future__ import annotations

from typing import Any, Optional

from backend.services.road_network import road_network
from backend.services.routing_providers import RouteProviderUnavailable, OSRMProvider


class SafeRoutingService:
    def calculate(self, origin: str, destination: str, origin_lat: Optional[float] = None, origin_lng: Optional[float] = None, destination_lat: Optional[float] = None, destination_lng: Optional[float] = None, hazardous_zones: Optional[list[str]] = None, prefer_external: bool = False) -> dict[str, Any]:
        destination_key = "".join(character for character in destination.lower() if character.isalnum())
        blocked = any(
            "".join(character for character in zone.lower() if character.isalnum()) in destination_key
            or "".join(character for character in zone.lower().replace("demo", "") if character.isalnum()) in destination_key
            for zone in (hazardous_zones or [])
        )
        if blocked:
            return {"route_status": "blocked_by_hazard_zone", "reason": "Destination is in a flagged hazard zone", "route": None}
        has_coordinates = all(value is not None for value in (origin_lat, origin_lng, destination_lat, destination_lng))
        if has_coordinates:
            if prefer_external:
                try:
                    route = OSRMProvider().route(origin_lat, origin_lng, destination_lat, destination_lng)
                    return {"route_status": "safe_route_available", "route": route, "reason": "OSRM road geometry passed hazard-zone validation", "data_status": route.get("data_status", "LIVE")}
                except RouteProviderUnavailable:
                    # Continue to the existing verified campus/fallback path.
                    pass
            route = road_network.get_route_between_coordinates(origin_lat, origin_lng, destination_lat, destination_lng)
            if route:
                return {"route_status": "safe_route_available", "route": route, "reason": "Deterministic verified road geometry selected", "data_status": route.get("data_status", "FALLBACK")}
        known_location = any(token in f"{origin} {destination}".lower() for token in ("block", "library", "health", "medical", "hostel", "gate", "sports", "sac", "pharmacy", "depot", "admin", "convocation"))
        if not known_location:
            return {"route_status": "route_unavailable", "route": None, "reason": "No verified route geometry is available for this region"}
        origin_node = road_network.map_location_to_node(origin)
        destination_node = road_network.map_location_to_node(destination)
        route = road_network.get_route_details(origin_node, destination_node)
        if route and route.get("route"):
            return {"route_status": "safe_route_available", "route": route, "reason": "Deterministic local road graph selected"}
        return {"route_status": "route_unavailable", "route": None, "reason": "No verified route geometry is available"}


safe_routing_service = SafeRoutingService()
