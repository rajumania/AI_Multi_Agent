import math
from typing import Dict, List, Tuple, Set, Optional, Any
from backend.config import settings
from backend.services.campus_locations import CAMPUS_NODE_COORDINATES, nearest_campus_node, project_campus_coordinate
from backend.services.routing_providers import OSRMProvider, RouteProviderUnavailable


# Backwards-compatible export used by the existing graph and tests.  The
# coordinate source is centralized in campus_locations.py.
NODES = dict(CAMPUS_NODE_COORDINATES)

# Curved street path geometry (lists of waypoints) for each bidirectional road segment
ROAD_GEOMETRIES = {
    ("gate", "depot_junc"): [(16.2320, 80.5490), (16.2317, 80.5492), (16.2315, 80.5495)],
    ("depot_junc", "depot"): [(16.2315, 80.5495), (16.2310, 80.5495)],
    ("depot_junc", "health_junc"): [(16.2315, 80.5495), (16.2320, 80.5498), (16.2325, 80.5500), (16.2330, 80.5502)],
    ("health_junc", "health_centre"): [(16.2330, 80.5502), (16.2332, 80.5502)],
    ("health_junc", "library"): [(16.2330, 80.5502), (16.2333, 80.5505), (16.2335, 80.5508)],
    ("library", "admin_roundabout"): [(16.2335, 80.5508), (16.2334, 80.5510), (16.2332, 80.5511)],
    ("admin_roundabout", "a_block"): [(16.2332, 80.5511), (16.2330, 80.5510)],
    
    # North Route (To Convocation/U-Block/Pharmacy/H-Block/Sports)
    ("admin_roundabout", "u_block_junc"): [(16.2332, 80.5511), (16.2335, 80.5514), (16.2338, 80.5518)],
    ("u_block_junc", "u_block"): [(16.2338, 80.5518), (16.2340, 80.5520)],
    ("u_block_junc", "convocation_junc"): [(16.2338, 80.5518), (16.2342, 80.5517), (16.2346, 80.5517)],
    ("convocation_junc", "convocation"): [(16.2346, 80.5517), (16.2350, 80.5518)],
    ("u_block_junc", "pharmacy_junc"): [(16.2338, 80.5518), (16.2341, 80.5524), (16.2345, 80.5528)],
    ("pharmacy_junc", "pharmacy"): [(16.2345, 80.5528), (16.2348, 80.5530)],
    
    # West loop connections
    ("health_junc", "sac"): [(16.2330, 80.5502), (16.2335, 80.5501), (16.2338, 80.5500)],
    ("sac", "sports_junc"): [(16.2338, 80.5500), (16.2342, 80.5498), (16.2345, 80.5496)],
    ("sports_junc", "sports"): [(16.2345, 80.5496), (16.2350, 80.5495), (16.2355, 80.5495)],
    
    ("sports_junc", "h_block_junc"): [(16.2345, 80.5496), (16.2343, 80.5501), (16.2342, 80.5506)],
    ("h_block_junc", "h_block"): [(16.2342, 80.5506), (16.2345, 80.5505)],
    ("h_block_junc", "convocation_junc"): [(16.2342, 80.5506), (16.2344, 80.5512), (16.2346, 80.5517)],

    # South-East Route (To Hostels & V-Block)
    ("admin_roundabout", "hostel_junc"): [(16.2332, 80.5511), (16.2325, 80.5518), (16.2318, 80.5530)],
    ("hostel_junc", "hostels"): [(16.2318, 80.5530), (16.2315, 80.5535)],
    ("admin_roundabout", "v_block_junc"): [(16.2332, 80.5511), (16.2330, 80.5517), (16.2328, 80.5523)],
    ("v_block_junc", "v_block"): [(16.2328, 80.5523), (16.2325, 80.5525)],
    ("v_block_junc", "hostel_junc"): [(16.2328, 80.5523), (16.2324, 80.5526), (16.2318, 80.5530)],
}

# Preserve the hand-authored graph shape while relocating its old campus
# fixture offsets to the verified AITAM Tekkali anchor.
ROAD_GEOMETRIES = {
    edge: [project_campus_coordinate(*point) for point in points]
    for edge, points in ROAD_GEOMETRIES.items()
}

class RoadNetwork:
    def __init__(self):
        # Build adjacency list
        self.graph: Dict[str, Dict[str, float]] = {node: {} for node in NODES}
        self.blocked_edges: Set[Tuple[str, str]] = set()

        for (u, v), coords in ROAD_GEOMETRIES.items():
            # Calculate distance using coordinates
            dist = 0.0
            for i in range(len(coords) - 1):
                lat1, lng1 = coords[i]
                lat2, lng2 = coords[i+1]
                dist += math.hypot(lat2 - lat1, lng2 - lng1)
            
            # Distance in meters (approx)
            meters = dist * 111000
            
            self.graph[u][v] = meters
            self.graph[v][u] = meters

    def block_edge(self, u: str, v: str):
        """Blocks a road segment (bidirectional)."""
        self.blocked_edges.add((u, v))
        self.blocked_edges.add((v, u))

    def unblock_edge(self, u: str, v: str):
        """Unblocks a road segment (bidirectional)."""
        self.blocked_edges.discard((u, v))
        self.blocked_edges.discard((v, u))

    def clear_blocked_edges(self):
        """Clears all road blockages."""
        self.blocked_edges.clear()

    def get_shortest_path(self, start: str, end: str) -> Tuple[Optional[List[str]], float]:
        """Calculates shortest path using Dijkstra, avoiding blocked edges."""
        if start not in NODES or end not in NODES:
            return None, float("inf")

        distances = {node: float("inf") for node in NODES}
        distances[start] = 0.0
        previous = {node: None for node in NODES}
        nodes_to_visit = set(NODES.keys())

        while nodes_to_visit:
            current = min(nodes_to_visit, key=lambda n: distances[n])
            if distances[current] == float("inf"):
                break

            if current == end:
                break

            nodes_to_visit.remove(current)

            for neighbor, weight in self.graph[current].items():
                # Skip if edge is blocked
                if (current, neighbor) in self.blocked_edges:
                    continue

                alternative_route = distances[current] + weight
                if alternative_route < distances[neighbor]:
                    distances[neighbor] = alternative_route
                    previous[neighbor] = current

        path = []
        curr = end
        while previous[curr] is not None:
            path.append(curr)
            curr = previous[curr]
        if path:
            path.append(start)
            path.reverse()
            return path, distances[end]
        
        # If start == end
        if start == end:
            return [start], 0.0

        return None, float("inf")

    def get_path_coordinates(self, path: List[str]) -> List[Tuple[float, float]]:
        """Maps a node-based path to a sequence of GPS coordinates following road curves."""
        if not path:
            return []

        coords = []
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            geom = ROAD_GEOMETRIES.get((u, v))
            if geom:
                # Add all except last to avoid duplication
                coords.extend(geom[:-1])
            else:
                geom_rev = ROAD_GEOMETRIES.get((v, u))
                if geom_rev:
                    coords.extend(list(reversed(geom_rev))[:-1])
                else:
                    # Straight line fallback if no geom is defined (should not happen)
                    coords.append(NODES[u])
        coords.append(NODES[path[-1]])
        return coords

    def map_location_to_node(self, location_name: str) -> str:
        """Helper to map natural language building names to graph nodes."""
        loc = location_name.lower()
        canonical = loc.strip().replace("-", "_").replace(" ", "_")
        if canonical in NODES:
            return canonical
        if "u-block" in loc or "cse" in loc or "computing" in loc or "it block" in loc:
            return "u-block"
        if "a-block" in loc or "admin" in loc or "registrar" in loc:
            return "a-block"
        if "h-block" in loc or "biotech" in loc or "science" in loc or "chem" in loc:
            return "h-block"
        if "v-block" in loc or "mech" in loc or "workshop" in loc or "civil" in loc:
            return "v-block"
        if "library" in loc or "ntr" in loc:
            return "library"
        if "auditorium" in loc or "convocation" in loc or "oat" in loc:
            return "convocation"
        if "sports" in loc or "stadium" in loc or "arena" in loc or "ground" in loc:
            return "sports"
        if "sac" in loc or "cafeteria" in loc or "canteen" in loc or "food court" in loc:
            return "sac"
        if "hostel" in loc or "mahalakshmi" in loc or "vasishta" in loc or "valmiki" in loc:
            return "hostels"
        if "gate" in loc or "entrance" in loc:
            return "gate"
        if "medical" in loc or "health" in loc or "first aid" in loc:
            return "health_centre"
        if "pharmacy" in loc or "bio-nest" in loc:
            return "pharmacy"
        if "transport" in loc or "bus" in loc or "parking" in loc or "depot" in loc:
            return "depot"
        return "admin_roundabout"

    def interpolate_path(self, coords: List[Tuple[float, float]], step_meters: float = 8.0) -> List[Tuple[float, float]]:
        """Interpolates coordinates for smoother animated vehicle step progression."""
        if not coords:
            return []

        interpolated = [coords[0]]
        step_deg = step_meters / 111000.0  # Approx meters to deg

        for i in range(len(coords) - 1):
            lat1, lng1 = coords[i]
            lat2, lng2 = coords[i+1]
            
            d_lat = lat2 - lat1
            d_lng = lng2 - lng1
            segment_len = math.hypot(d_lat, d_lng)
            
            if segment_len == 0:
                continue

            num_steps = int(segment_len / step_deg)
            for s in range(1, num_steps):
                ratio = s / num_steps
                interpolated.append((lat1 + d_lat * ratio, lng1 + d_lng * ratio))
    def fetch_osrm_route(self, origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> Optional[Dict[str, Any]]:
        """
        Queries real OpenStreetMap OSRM driving route API.
        Returns coordinates [lat, lng], distance (meters), duration (seconds), and steps.
        """
        try:
            if settings.ROUTING_PROVIDER.strip().lower() not in {"osrm", "openstreetmap", "open_street_map"}:
                return None
            return OSRMProvider().route(origin_lat, origin_lng, dest_lat, dest_lng)
        except RouteProviderUnavailable:
            # Clean fallback to the verified local road graph if OSRM is
            # unreachable/offline. The returned route is marked FALLBACK.
            return None
        return None

    def get_route_details(self, origin_node: str, dest_node: str) -> Dict[str, Any]:
        """
        Returns real road route details between origin and destination.
        Tries OSRM first, falling back to local road graph geometry.
        """
        from backend.config import settings
        
        orig_coords = NODES.get(origin_node, (18.56517, 84.19587))
        dest_coords = NODES.get(dest_node, (18.56517, 84.19587))
        
        osrm_res = self.fetch_osrm_route(orig_coords[0], orig_coords[1], dest_coords[0], dest_coords[1])
        if osrm_res and len(osrm_res.get("coordinates", [])) > 1:
            osrm_res["source"] = origin_node
            osrm_res["destination"] = dest_node
            osrm_res["route"] = [origin_node, dest_node]
            return osrm_res

        # Local Campus Dijkstra Graph Fallback
        path, distance = self.get_shortest_path(origin_node, dest_node)
        if not path:
            path = [origin_node, dest_node]
            distance = 300.0
            
        coords = self.get_path_coordinates(path)
        eta_sec = int(distance / 10.0) if distance > 0 else 0
        return {
            "coordinates": coords,
            "distance_meters": int(distance),
            "eta_seconds": eta_sec,
            "routing_engine": "Campus Graph Engine",
            "source": origin_node,
            "data_status": "FALLBACK",
            "destination": dest_node,
            "route": path,
            "steps": [
                {"instruction": f"Head from {origin_node.replace('_', ' ').title()} towards {dest_node.replace('_', ' ').title()}", "distance_meters": int(distance), "duration_seconds": eta_sec}
            ]
        }

    def get_route_between_coordinates(
        self,
        origin_lat: float,
        origin_lng: float,
        destination_lat: float,
        destination_lng: float,
    ) -> Optional[Dict[str, Any]]:
        """Route exact coordinates only when a reliable geometry source exists.

        OSRM is attempted first.  If it is unavailable, the verified-in-project
        campus graph is used only when both endpoints are close to known graph
        nodes.  Arbitrary points are not silently connected with guessed roads.
        """
        origin_node = nearest_campus_node(origin_lat, origin_lng)
        destination_node = nearest_campus_node(destination_lat, destination_lng)
        if origin_node and destination_node:
            path, distance = self.get_shortest_path(origin_node, destination_node)
            if path:
                graph_coordinates = self.get_path_coordinates(path)
                coordinates: List[Tuple[float, float]] = [(origin_lat, origin_lng)]
                if graph_coordinates:
                    if graph_coordinates[0] != coordinates[0]:
                        coordinates.extend(graph_coordinates)
                    else:
                        coordinates = graph_coordinates[:]
                if coordinates[-1] != (destination_lat, destination_lng):
                    coordinates.append((destination_lat, destination_lng))

                # Include endpoint access distances while retaining the graph's
                # road geometry. The access segments are explicitly labelled.
                access_distance = (
                    math.hypot(origin_lat - NODES[origin_node][0], origin_lng - NODES[origin_node][1])
                    + math.hypot(destination_lat - NODES[destination_node][0], destination_lng - NODES[destination_node][1])
                ) * 111000.0
                total_distance = distance + access_distance
                eta_seconds = int(total_distance / 10.0) if total_distance > 0 else 0
                return {
                    "coordinates": coordinates,
                    "distance_meters": int(total_distance),
                    "eta_seconds": eta_seconds,
                    "routing_engine": "Campus Graph Engine",
                    "source": "CAMPUS_GRAPH",
                    "data_status": "FALLBACK",
                    "origin_node": origin_node,
                    "destination_node": destination_node,
                    "route": path,
                    "steps": [{
                        "instruction": f"Follow the existing campus road graph from {origin_node} to {destination_node}",
                        "distance_meters": int(total_distance),
                        "duration_seconds": eta_seconds,
                    }],
                }

        # Outside the known campus graph, use OSRM only when it can provide
        # actual geometry. Never use it to replace known private-campus roads.
        osrm_result = self.fetch_osrm_route(origin_lat, origin_lng, destination_lat, destination_lng)
        if osrm_result and len(osrm_result.get("coordinates", [])) > 1:
            osrm_result["source"] = "OSRM"
            return osrm_result
        return None


road_network = RoadNetwork()
