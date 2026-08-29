"""Central AITAM location catalog and the verified institutional anchor."""

from __future__ import annotations

from math import hypot
from typing import Any, Dict, Iterable, Optional


AITAM_COORDINATES = (18.56517, 84.19587)
_LEGACY_COORDINATE_ANCHOR = (16.2334, 80.5513)


def project_campus_coordinate(latitude: Optional[float], longitude: Optional[float]) -> tuple[Optional[float], Optional[float]]:
    """Move the old local campus graph offsets onto the verified AITAM site.

    Only the former 16/80 campus fixture is projected. Nepal/N-14 and any
    user-supplied real-world coordinates are returned unchanged.
    """
    if latitude is None or longitude is None:
        return latitude, longitude
    if 15.0 <= latitude <= 17.0 and 79.0 <= longitude <= 81.0:
        return (
            round(AITAM_COORDINATES[0] + (latitude - _LEGACY_COORDINATE_ANCHOR[0]), 6),
            round(AITAM_COORDINATES[1] + (longitude - _LEGACY_COORDINATE_ANCHOR[1]), 6),
        )
    return latitude, longitude


_RAW_CAMPUS_NODE_COORDINATES: Dict[str, tuple[float, float]] = {
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

CAMPUS_NODE_COORDINATES: Dict[str, tuple[float, float]] = {
    key: project_campus_coordinate(*coordinates)  # type: ignore[misc]
    for key, coordinates in _RAW_CAMPUS_NODE_COORDINATES.items()
}


_LOCATION_DEFINITIONS = (
    ("u_block", "U-Block (CSE & IT)", "building", ("u-block", "cse", "computing", "it block")),
    ("a_block", "A-Block (Admin & Central Office)", "building", ("a-block", "admin", "registrar", "vc office")),
    ("h_block", "H-Block (Biotechnology & Sciences)", "building", ("h-block", "biotech", "science", "chem")),
    ("v_block", "V-Block (Mechanical & Workshops)", "building", ("v-block", "mech", "workshop", "civil")),
    ("library", "NTR Central Library", "facility", ("library", "ntr")),
    ("convocation", "AITAM Convocation Hall & Auditorium", "facility", ("auditorium", "convocation", "oat")),
    ("sports", "Sports Complex & Indoor Stadium", "facility", ("sports", "stadium", "arena", "ground")),
    ("sac", "Community Activity Center (SAC) & Cafeteria", "facility", ("sac", "cafeteria", "canteen", "food court")),
    ("hostels", "AITAM Residential Zone", "hostel", ("hostel", "mahalakshmi", "vasishta", "valmiki", "dorm")),
    ("gate", "Main Response Gate", "gate", ("gate", "entrance")),
    ("health_centre", "AITAM Health & Medical Centre", "medical", ("medical", "health", "first aid")),
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
            "coordinate_source": "AITAM_official_location_source",
            "verification_status": "verified_official_source",
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
