"""Central campus location catalog built from the project's existing coordinates.

The values in this catalog are the coordinates already used by CampusFlow's
resource seed and campus routing graph.  They are intentionally marked as
requiring external verification before production dispatch decisions rely on
them; this module does not invent new coordinates.
"""

from __future__ import annotations

from math import hypot
from typing import Any, Dict, Iterable, Optional


CAMPUS_NODE_COORDINATES: Dict[str, tuple[float, float]] = {
    "gate": (16.2320, 80.5490),
    "depot": (16.2310, 80.5495),
    "health_centre": (16.2332, 80.5502),
    "sac": (16.2338, 80.5500),
    "library": (16.2335, 80.5508),
    "admin_roundabout": (16.2332, 80.5511),
    "a_block": (16.2330, 80.5510),
    "v_block": (16.2325, 80.5525),
    "u_block": (16.2340, 80.5520),
    "h_block": (16.2345, 80.5505),
    "convocation": (16.2350, 80.5518),
    "sports": (16.2355, 80.5495),
    "hostels": (16.2315, 80.5535),
    "pharmacy": (16.2348, 80.5530),
    "depot_junc": (16.2315, 80.5495),
    "health_junc": (16.2330, 80.5502),
    "sports_junc": (16.2345, 80.5496),
    "h_block_junc": (16.2342, 80.5506),
    "convocation_junc": (16.2346, 80.5517),
    "u_block_junc": (16.2338, 80.5518),
    "hostel_junc": (16.2318, 80.5530),
    "v_block_junc": (16.2328, 80.5523),
    "pharmacy_junc": (16.2345, 80.5528),
}


_LOCATION_DEFINITIONS = (
    ("u_block", "U-Block (CSE & IT)", "building", ("u-block", "cse", "computing", "it block")),
    ("a_block", "A-Block (Admin & Central Office)", "building", ("a-block", "admin", "registrar", "vc office")),
    ("h_block", "H-Block (Biotechnology & Sciences)", "building", ("h-block", "biotech", "science", "chem")),
    ("v_block", "V-Block (Mechanical & Workshops)", "building", ("v-block", "mech", "workshop", "civil")),
    ("library", "NTR Central Library", "facility", ("library", "ntr")),
    ("convocation", "NTR Convocation Hall & Auditorium", "facility", ("auditorium", "convocation", "vignan vihar", "oat")),
    ("sports", "Sports Complex & Indoor Stadium", "facility", ("sports", "stadium", "arena", "ground")),
    ("sac", "Student Activity Center (SAC) & Cafeteria", "facility", ("sac", "cafeteria", "canteen", "food court")),
    ("hostels", "Mahalakshmi & Vasishta Hostels", "hostel", ("hostel", "mahalakshmi", "vasishta", "valmiki", "dorm")),
    ("gate", "Main Vadlamudi Entrance Gate", "gate", ("gate", "entrance", "vadlamudi")),
    ("health_centre", "Campus Health & Medical Centre", "medical", ("medical", "health", "first aid")),
    ("pharmacy", "Pharmacy Block & Bio-Nest Hub", "facility", ("pharmacy", "bio-nest")),
    ("depot", "Central Transport Hub & Bus Depot", "transport", ("transport", "bus", "parking", "depot")),
)


def campus_location_catalog() -> list[Dict[str, Any]]:
    """Return serializable building/facility/access-point metadata."""
    rows: list[Dict[str, Any]] = []
    for location_id, name, kind, aliases in _LOCATION_DEFINITIONS:
        latitude, longitude = CAMPUS_NODE_COORDINATES[location_id]
        rows.append({
            "location_id": location_id,
            "name": name,
            "kind": kind,
            "latitude": latitude,
            "longitude": longitude,
            "aliases": list(aliases),
            "coordinate_source": "existing_project_coordinate",
            "verification_status": "requires_external_verification",
        })
    return rows


def match_campus_location(location: Optional[str]) -> Optional[Dict[str, Any]]:
    """Match text to a catalog item without inventing a coordinate."""
    text = (location or "").strip().lower()
    if not text:
        return None
    for row in campus_location_catalog():
        if any(alias in text for alias in row["aliases"]):
            return row
    return None


def nearest_campus_node(latitude: float, longitude: float, max_distance_m: float = 180.0) -> Optional[str]:
    """Return a graph node only when the point is close to known graph data."""
    best_node: Optional[str] = None
    best_distance = float("inf")
    for node, (node_lat, node_lng) in CAMPUS_NODE_COORDINATES.items():
        distance = hypot(node_lat - latitude, node_lng - longitude) * 111_000.0
        if distance < best_distance:
            best_distance = distance
            best_node = node
    return best_node if best_distance <= max_distance_m else None
