from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.database.models import CampusResourceDB

MOCK_RESOURCES = [
    {
        "resource_id": "AMB-001",
        "name": "Campus Ambulance 1 (Primary)",
        "resource_type": "ambulance",
        "location": "Central Medical Center",
        "latitude": 17.5448,
        "longitude": 78.5718,
        "availability_status": "available",
        "capacity": 2,
        "quantity": 1,
        "contact": "Ext 401 / Radio MED-1",
    },
    {
        "resource_id": "AMB-002",
        "name": "Campus Ambulance 2 (North Post)",
        "resource_type": "ambulance",
        "location": "North Campus Health Post",
        "latitude": 17.5480,
        "longitude": 78.5740,
        "availability_status": "available",
        "capacity": 2,
        "quantity": 1,
        "contact": "Ext 402 / Radio MED-2",
    },
    {
        "resource_id": "SEC-001",
        "name": "Campus Security Unit 1 - Alpha",
        "resource_type": "security",
        "location": "Main Entrance Security Post",
        "latitude": 17.5420,
        "longitude": 78.5700,
        "availability_status": "available",
        "capacity": 4,
        "quantity": 1,
        "contact": "Ext 101 / Radio SEC-ALPHA",
    },
    {
        "resource_id": "SEC-002",
        "name": "Campus Security Unit 2 - Bravo",
        "resource_type": "security",
        "location": "Science & CSE Block Station",
        "latitude": 17.5460,
        "longitude": 78.5725,
        "availability_status": "available",
        "capacity": 4,
        "quantity": 1,
        "contact": "Ext 102 / Radio SEC-BRAVO",
    },
    {
        "resource_id": "SEC-003",
        "name": "Campus Security Unit 3 - Patrol",
        "resource_type": "security",
        "location": "South Residential Perimeter",
        "latitude": 17.5410,
        "longitude": 78.5735,
        "availability_status": "busy",
        "capacity": 3,
        "quantity": 1,
        "contact": "Ext 103 / Radio SEC-PATROL",
    },
    {
        "resource_id": "MED-001",
        "name": "First Aid Rapid Response Unit 1",
        "resource_type": "first_aid",
        "location": "Student Activity Center",
        "latitude": 17.5450,
        "longitude": 78.5710,
        "availability_status": "available",
        "capacity": 10,
        "quantity": 1,
        "contact": "Ext 301 / Radio FA-1",
    },
    {
        "resource_id": "MED-002",
        "name": "First Aid Rapid Response Unit 2",
        "resource_type": "first_aid",
        "location": "Sports & Recreation Complex",
        "latitude": 17.5475,
        "longitude": 78.5695,
        "availability_status": "available",
        "capacity": 8,
        "quantity": 1,
        "contact": "Ext 302 / Radio FA-2",
    },
    {
        "resource_id": "SHELTER-001",
        "name": "North Campus Main Auditorium Shelter",
        "resource_type": "shelter",
        "location": "Auditorium Complex",
        "latitude": 17.5485,
        "longitude": 78.5730,
        "availability_status": "available",
        "capacity": 600,
        "quantity": 1,
        "contact": "Ext 501 / Facilities Desk",
    },
    {
        "resource_id": "SHELTER-002",
        "name": "Indoor Stadium Emergency Shelter",
        "resource_type": "shelter",
        "location": "Sports Complex Arena",
        "latitude": 17.5470,
        "longitude": 78.5690,
        "availability_status": "available",
        "capacity": 900,
        "quantity": 1,
        "contact": "Ext 502 / Sports Office",
    },
    {
        "resource_id": "VEH-001",
        "name": "Campus Rapid Evacuation Van 1",
        "resource_type": "vehicle",
        "location": "Central Parking Depot",
        "latitude": 17.5435,
        "longitude": 78.5715,
        "availability_status": "available",
        "capacity": 14,
        "quantity": 1,
        "contact": "Ext 601 / Dispatch",
    },
    {
        "resource_id": "VEH-002",
        "name": "Campus Evacuation Bus 1",
        "resource_type": "vehicle",
        "location": "South Transport Hub",
        "latitude": 17.5415,
        "longitude": 78.5680,
        "availability_status": "available",
        "capacity": 50,
        "quantity": 1,
        "contact": "Ext 602 / Dispatch",
    },
    {
        "resource_id": "FAC-001",
        "name": "Facilities & Power Hazard Crew 1",
        "resource_type": "facility",
        "location": "Engineering Workshops Hub",
        "latitude": 17.5465,
        "longitude": 78.5750,
        "availability_status": "available",
        "capacity": 5,
        "quantity": 1,
        "contact": "Ext 701 / Hazmat Desk",
    },
    {
        "resource_id": "FIRE-001",
        "name": "Campus Fire Safety Rapid Equipment Team",
        "resource_type": "fire_response",
        "location": "Safety Operations Hub",
        "latitude": 17.5440,
        "longitude": 78.5705,
        "availability_status": "available",
        "capacity": 4,
        "quantity": 1,
        "contact": "Ext 911 / Fire Post",
    },
]


def seed_resources(db: Session) -> int:
    """Populates initial mock campus resources if table is empty."""
    existing_count = db.query(CampusResourceDB).count()
    if existing_count > 0:
        return existing_count

    for item in MOCK_RESOURCES:
        resource = CampusResourceDB(
            resource_id=item["resource_id"],
            name=item["name"],
            resource_type=item["resource_type"],
            location=item["location"],
            latitude=item.get("latitude"),
            longitude=item.get("longitude"),
            availability_status=item.get("availability_status", "available"),
            capacity=item.get("capacity"),
            quantity=item.get("quantity", 1),
            contact=item.get("contact"),
            last_updated=datetime.now(timezone.utc),
        )
        db.add(resource)
    db.commit()
    return len(MOCK_RESOURCES)


def reset_seed_resources(db: Session):
    """Resets all resources to their original initial availability status."""
    for item in MOCK_RESOURCES:
        r = db.query(CampusResourceDB).filter(CampusResourceDB.resource_id == item["resource_id"]).first()
        if r:
            r.availability_status = item.get("availability_status", "available")
            r.last_updated = datetime.now(timezone.utc)
    db.commit()

