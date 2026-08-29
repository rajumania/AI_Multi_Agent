from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.database.models import (
    CampusResourceDB,
    RegionDB,
    ZoneDB,
    CommunityDB,
    RouteDB,
)
import json
from backend.services.departments import department_for_resource_type, register_department
from backend.services.campus_locations import project_campus_coordinate
from backend.services.auth_service import hash_password
from backend.database.models import OrganizationDB, DepartmentDB


ORGANIZATION_CODE = "AITAM"
ORGANIZATION_NAME = "Aditya Institute of Technology and Management (AITAM)"

ORGANIZATION_DEPARTMENTS = [
    ("MEDICAL", "Medical & Health", "medical", "Clinical response, triage, first aid, and hospital coordination."),
    ("SEARCH_AND_RESCUE", "Search & Rescue", "search_and_rescue", "Rescue prioritization, extraction, and responder coordination."),
    ("FIRE", "Fire & Safety", "fire", "Fire suppression, hazmat safety, and fire-risk response."),
    ("SECURITY", "Security / Public Safety", "security", "Perimeter control, access safety, and public protection."),
    ("TRANSPORT", "Transport & Logistics", "transport", "Evacuation transport, vehicle dispatch, and route logistics."),
    ("COMMUNICATION", "Communications", "communication", "Approved public information and responder communications."),
    ("FACILITIES", "Infrastructure / Facilities", "infrastructure", "Utilities, infrastructure hazards, and route conditions."),
    ("SHELTER", "Shelter & Relief", "shelter", "Shelter capacity, relief supplies, and reception coordination."),
]


def seed_organization(db: Session) -> int:
    """Create/update the single AITAM organization and its eight departments."""
    organization = db.query(OrganizationDB).filter(OrganizationDB.code == ORGANIZATION_CODE).first()
    if organization is None:
        organization = OrganizationDB(code=ORGANIZATION_CODE, name=ORGANIZATION_NAME, status="active")
        db.add(organization)
        db.flush()
    elif organization.name != ORGANIZATION_NAME:
        organization.name = ORGANIZATION_NAME
    for existing_department in db.query(DepartmentDB).all():
        register_department(existing_department.code, existing_department.name)
    for code, name, department_type, description in ORGANIZATION_DEPARTMENTS:
        department = db.query(DepartmentDB).filter(DepartmentDB.code == code).first()
        if department is None:
            db.add(DepartmentDB(
                organization_id=organization.id, code=code, name=name,
                department_type=department_type, description=description, status="active",
            ))
        else:
            department.organization_id = organization.id
            department.name = name
            department.department_type = department_type
            department.description = description
        register_department(code, name)
    db.commit()
    return len(ORGANIZATION_DEPARTMENTS)

MOCK_RESOURCES = [
    {
        "resource_id": "AMB-001",
        "name": "AITAM Response Ambulance 1 (Primary - Health Centre)",
        "resource_type": "ambulance",
        "location": "AITAM Health & Medical Centre",
        "latitude": 16.2332,
        "longitude": 80.5502,
        "availability_status": "available",
        "capacity": 2,
        "quantity": 1,
        "contact": "Ext 401 / 0863-2344700 / Radio MED-1",
    },
    {
        "resource_id": "AMB-002",
        "name": "AITAM Response Ambulance 2 (Residential Zone)",
        "resource_type": "ambulance",
        "location": "Mahalakshmi & Vasishta Hostels Post",
        "latitude": 16.2315,
        "longitude": 80.5535,
        "availability_status": "available",
        "capacity": 2,
        "quantity": 1,
        "contact": "Ext 402 / Radio MED-2",
    },
    {
        "resource_id": "SEC-001",
        "name": "AITAM Public Safety Alpha - Main Response Gate",
        "resource_type": "security",
        "location": "AITAM Main Entrance Gate",
        "latitude": 16.2320,
        "longitude": 80.5490,
        "availability_status": "available",
        "capacity": 4,
        "quantity": 1,
        "contact": "Ext 101 / Radio SEC-ALPHA",
    },
    {
        "resource_id": "SEC-002",
        "name": "AITAM Public Safety Bravo - Academic Quad (U-Block & H-Block)",
        "resource_type": "security",
        "location": "U-Block & H-Block Station",
        "latitude": 16.2340,
        "longitude": 80.5520,
        "availability_status": "available",
        "capacity": 4,
        "quantity": 1,
        "contact": "Ext 102 / Radio SEC-BRAVO",
    },
    {
        "resource_id": "SEC-003",
        "name": "AITAM Public Safety Patrol - Residential Perimeter",
        "resource_type": "security",
        "location": "South Residential & Sports Perimeter",
        "latitude": 16.2310,
        "longitude": 80.5540,
        "availability_status": "busy",
        "capacity": 3,
        "quantity": 1,
        "contact": "Ext 103 / Radio SEC-PATROL",
    },
    {
        "resource_id": "MED-001",
        "name": "First Aid Rapid Response Unit 1 - SAC & Food Court",
        "resource_type": "first_aid",
        "location": "Community Activity Center (SAC)",
        "latitude": 16.2338,
        "longitude": 80.5500,
        "availability_status": "available",
        "capacity": 10,
        "quantity": 1,
        "contact": "Ext 301 / Radio FA-1",
    },
    {
        "resource_id": "MED-002",
        "name": "First Aid Rapid Response Unit 2 - Sports Arena",
        "resource_type": "first_aid",
        "location": "Sports Complex & Athletic Ground",
        "latitude": 16.2355,
        "longitude": 80.5495,
        "availability_status": "available",
        "capacity": 8,
        "quantity": 1,
        "contact": "Ext 302 / Radio FA-2",
    },
    {
        "resource_id": "SHELTER-001",
        "name": "AITAM Convocation Hall Emergency Shelter",
        "resource_type": "shelter",
        "location": "NTR Convocation Hall & Auditorium",
        "latitude": 16.2350,
        "longitude": 80.5518,
        "availability_status": "available",
        "capacity": 1200,
        "quantity": 1,
        "contact": "Ext 501 / Facilities Desk",
    },
    {
        "resource_id": "SHELTER-002",
        "name": "AITAM Indoor Stadium Emergency Shelter",
        "resource_type": "shelter",
        "location": "Sports Complex Indoor Stadium",
        "latitude": 16.2355,
        "longitude": 80.5495,
        "availability_status": "available",
        "capacity": 900,
        "quantity": 1,
        "contact": "Ext 502 / Physical Education Office",
    },
    {
        "resource_id": "VEH-001",
        "name": "AITAM Rapid Evacuation Van 1",
        "resource_type": "vehicle",
        "location": "A-Block Administrative Parking",
        "latitude": 16.2330,
        "longitude": 80.5510,
        "availability_status": "available",
        "capacity": 14,
        "quantity": 1,
        "contact": "Ext 601 / Transport Dispatch",
    },
    {
        "resource_id": "VEH-002",
        "name": "AITAM Evacuation Bus Fleet 1",
        "resource_type": "vehicle",
        "location": "Central Transport Hub & Bus Depot",
        "latitude": 16.2310,
        "longitude": 80.5495,
        "availability_status": "available",
        "capacity": 55,
        "quantity": 1,
        "contact": "Ext 602 / Transport Officer",
    },
    {
        "resource_id": "FAC-001",
        "name": "AITAM Facilities & Power Hazard Crew",
        "resource_type": "facility",
        "location": "V-Block Mechanical Workshops & Electrical Hub",
        "latitude": 16.2325,
        "longitude": 80.5525,
        "availability_status": "available",
        "capacity": 6,
        "quantity": 1,
        "contact": "Ext 701 / Maintenance Desk",
    },
    {
        "resource_id": "FIRE-001",
        "name": "AITAM Rapid Fire Safety & Extinguisher Squad",
        "resource_type": "fire_response",
        "location": "A-Block Central Safety Hub",
        "latitude": 16.2330,
        "longitude": 80.5510,
        "availability_status": "available",
        "capacity": 4,
        "quantity": 1,
        "contact": "Ext 911 / 0863-2344700 / Fire Safety Post",
    },
]


def seed_resources(db: Session) -> int:
    """Idempotently adds the original resources without replacing user data."""
    for item in MOCK_RESOURCES:
        existing = db.query(CampusResourceDB).filter(CampusResourceDB.resource_id == item["resource_id"]).first()
        if existing:
            existing.latitude, existing.longitude = project_campus_coordinate(existing.latitude, existing.longitude)
            mapped = department_for_resource_type(existing.resource_type)
            if mapped and existing.resource_type in {"rescue_team", "shelter"} and existing.department in {"SECURITY", "FACILITIES"}:
                existing.department = mapped
            continue
        resource = CampusResourceDB(
            resource_id=item["resource_id"],
            name=item["name"],
            resource_type=item["resource_type"],
            location=item["location"],
            latitude=project_campus_coordinate(item.get("latitude"), item.get("longitude"))[0],
            longitude=project_campus_coordinate(item.get("latitude"), item.get("longitude"))[1],
            availability_status=item.get("availability_status", "available"),
            capacity=item.get("capacity"),
            quantity=item.get("quantity", 1),
            contact=item.get("contact"),
            department=department_for_resource_type(item["resource_type"]),
            last_updated=datetime.now(timezone.utc),
        )
        db.add(resource)
    db.commit()
    return db.query(CampusResourceDB).count()


# Clearly labelled development data. These records are not government or live
# emergency data and are only used to exercise the Phase 1 domain contracts.
DEMO_REGIONS = [
    {"id": "DEMO-REGION-01", "name": "Demo Coastal Region", "risk_status": "demo", "population": 42000, "latitude": 16.2334, "longitude": 80.5513},
    {"id": "DEMO-NEPAL-MOUNTAIN", "name": "Nepal Mountain Region (DEMO)", "risk_status": "demo", "population": 2200, "latitude": 28.2100, "longitude": 84.0200},
]
DEMO_ZONES = [
    {"id": "DEMO-ZONE-A", "region_id": "DEMO-REGION-01", "name": "Zone A (DEMO)", "risk_status": "demo", "population": 12400, "latitude": 16.2334, "longitude": 80.5513, "elevation_m": 3.0, "slope_deg": 1.5, "vulnerability_score": 78.0, "historical_disaster_frequency": 4.0, "river_proximity_km": 0.8, "drainage_vulnerability": 82.0, "hazard_classification": "flood_prone", "coastal_vulnerability": 55.0},
    {"id": "DEMO-ZONE-B", "region_id": "DEMO-REGION-01", "name": "Zone B (DEMO)", "risk_status": "demo", "population": 9800, "latitude": 16.2380, "longitude": 80.5580, "elevation_m": 12.0, "slope_deg": 3.0, "vulnerability_score": 35.0, "historical_disaster_frequency": 1.0, "river_proximity_km": 4.0, "drainage_vulnerability": 35.0, "hazard_classification": "general", "coastal_vulnerability": 25.0},
    {"id": "DEMO-N14", "region_id": "DEMO-NEPAL-MOUNTAIN", "name": "N-14 (DEMO/SIMULATION)", "risk_status": "demo", "population": 2200, "latitude": 28.2100, "longitude": 84.0200, "elevation_m": 3400.0, "slope_deg": 78.0, "vulnerability_score": 88.0, "historical_disaster_frequency": 4.5, "river_proximity_km": 0.5, "drainage_vulnerability": 70.0, "hazard_classification": "mountain_landslide", "coastal_vulnerability": 0.0},
]
DEMO_COMMUNITIES = [
    {"id": "DEMO-COMMUNITY-01", "zone_id": "DEMO-ZONE-A", "name": "Demo Riverside Community", "population": 5600, "latitude": 16.2320, "longitude": 80.5540},
]
DEMO_DOMAIN_RESOURCES = [
    {"resource_id": "DEMO-SHELTER-01", "name": "Demo Community Shelter A", "resource_type": "shelter", "location": "Zone A Demo Relief Hub", "latitude": 16.2338, "longitude": 80.5500, "availability_status": "available", "capacity": 500, "contact": "DEMO ONLY / Relief Desk", "department": "SHELTER"},
    {"resource_id": "DEMO-HOSPITAL-01", "name": "Demo District Hospital", "resource_type": "hospital", "location": "Demo Medical Corridor", "latitude": 16.2290, "longitude": 80.5570, "availability_status": "available", "capacity": 120, "emergency_beds": 40, "contact": "DEMO ONLY / Medical Desk", "department": "MEDICAL"},
    {"resource_id": "DEMO-RESCUE-01", "name": "Rescue Team 01 (DEMO)", "resource_type": "rescue_team", "location": "Zone A Demo Response Base", "latitude": 16.2345, "longitude": 80.5525, "availability_status": "available", "capacity": 8, "contact": "DEMO ONLY / Rescue Control", "department": "SEARCH_AND_RESCUE"},
    {"resource_id": "DEMO-FIRE-01", "name": "Demo Fire & Emergency Service", "resource_type": "fire_service", "location": "Demo Regional Response Base", "latitude": 16.2360, "longitude": 80.5485, "availability_status": "available", "capacity": 6, "contact": "DEMO ONLY / Fire Control", "department": "FIRE"},
    {"resource_id": "DEMO-BOAT-01", "name": "Demo Flood Rescue Boat", "resource_type": "boat", "location": "Demo Flood Equipment Depot", "latitude": 16.2305, "longitude": 80.5535, "availability_status": "available", "capacity": 10, "contact": "DEMO ONLY / Water Rescue", "department": "TRANSPORT"},
    {"resource_id": "DEMO-WATER-01", "name": "Demo Drinking Water Stock", "resource_type": "water", "location": "Zone A Demo Relief Hub", "latitude": 16.2338, "longitude": 80.5500, "availability_status": "available", "quantity": 1000, "contact": "DEMO ONLY / Relief Logistics", "department": "FACILITIES"},
    {"resource_id": "DEMO-KIT-01", "name": "Demo Emergency Kit Cache", "resource_type": "emergency_kit", "location": "Zone B Demo Relief Hub", "latitude": 16.2380, "longitude": 80.5580, "availability_status": "available", "quantity": 100, "contact": "DEMO ONLY / Relief Logistics", "department": "FACILITIES"},
    {"resource_id": "DEMO-N14-RESCUE-01", "name": "Rescue Team N-14 (DEMO)", "resource_type": "rescue_team", "location": "Nepal Mountain N-14 Response Base", "latitude": 28.2080, "longitude": 84.0150, "availability_status": "available", "capacity": 8, "quantity": 1, "contact": "DEMO ONLY / Mountain Rescue Control", "department": "SEARCH_AND_RESCUE"},
    {"resource_id": "DEMO-N14-SHELTER-01", "name": "N-14 Mountain Relief Shelter (DEMO)", "resource_type": "shelter", "location": "Nepal Mountain N-14 Safe Area", "latitude": 28.2160, "longitude": 84.0280, "availability_status": "available", "capacity": 500, "quantity": 1, "contact": "DEMO ONLY / Shelter Desk", "department": "SHELTER"},
    {"resource_id": "DEMO-N14-HOSPITAL-01", "name": "N-14 District Emergency Hospital (DEMO)", "resource_type": "hospital", "location": "Nepal Mountain N-14 Medical Post", "latitude": 28.2000, "longitude": 84.0300, "availability_status": "available", "capacity": 60, "emergency_beds": 12, "quantity": 1, "contact": "DEMO ONLY / Medical Desk", "department": "MEDICAL"},
    {"resource_id": "DEMO-N14-VEHICLE-01", "name": "Mountain Rescue Vehicle N-14 (DEMO)", "resource_type": "vehicle", "location": "Nepal Mountain N-14 Response Base", "latitude": 28.2080, "longitude": 84.0150, "availability_status": "available", "capacity": 6, "quantity": 1, "contact": "DEMO ONLY / Transport Control", "department": "TRANSPORT"},
]

DEMO_MAP_ROUTES = [
    {"incident_id": "DEMO-N14-MAP", "resource_id": "DEMO-N14-RESCUE-01", "origin": "N-14 Response Base", "destination": "N-14 affected slope", "status": "active", "path": [[28.2080, 84.0150], [28.2100, 84.0200], [28.2120, 84.0230]], "distance_m": 1250, "eta_seconds": 480, "geometry_source": "DEMO/SIMULATION"},
    {"incident_id": "DEMO-N14-MAP", "resource_id": "DEMO-N14-RESCUE-01", "origin": "N-14 Response Base", "destination": "River access road", "status": "blocked", "path": [[28.2080, 84.0150], [28.2050, 84.0220], [28.2010, 84.0300]], "distance_m": 1800, "eta_seconds": 900, "geometry_source": "DEMO/SIMULATION"},
]


def seed_disaster_domain(db: Session) -> int:
    """Seed clearly labelled Phase 1 demo geography and response assets."""
    for item in DEMO_REGIONS:
        if not db.query(RegionDB).filter(RegionDB.id == item["id"]).first():
            db.add(RegionDB(**item, is_demo=1))
    for item in DEMO_ZONES:
        existing = db.query(ZoneDB).filter(ZoneDB.id == item["id"]).first()
        if not existing:
            db.add(ZoneDB(**item, is_demo=1))
        else:
            # Backfill only missing demo metadata; preserve operator edits.
            for key, value in item.items():
                if key != "id" and getattr(existing, key, None) is None:
                    setattr(existing, key, value)
    for item in DEMO_COMMUNITIES:
        if not db.query(CommunityDB).filter(CommunityDB.id == item["id"]).first():
            db.add(CommunityDB(**item, is_demo=1))
    for item in DEMO_DOMAIN_RESOURCES:
        existing = db.query(CampusResourceDB).filter(CampusResourceDB.resource_id == item["resource_id"]).first()
        if existing:
            # Complete only missing demo metadata; preserve live status and
            # operator assignments on records that already exist.
            if existing.latitude is None:
                existing.latitude = item.get("latitude")
            if existing.longitude is None:
                existing.longitude = item.get("longitude")
            mapped = department_for_resource_type(existing.resource_type)
            if mapped and existing.resource_type in {"rescue_team", "shelter"} and existing.department in {"SECURITY", "FACILITIES"}:
                existing.department = mapped
            continue
        if not existing:
            resource_data = {**item, "quantity": item.get("quantity", 1), "is_demo": 1, "last_updated": datetime.now(timezone.utc)}
            db.add(CampusResourceDB(**resource_data))
    for item in DEMO_MAP_ROUTES:
        if not db.query(RouteDB).filter(RouteDB.incident_id == item["incident_id"], RouteDB.resource_id == item["resource_id"], RouteDB.status == item["status"]).first():
            db.add(RouteDB(**{**item, "path": json.dumps(item["path"]), "route_version": 1, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}))
    db.commit()
    return len(DEMO_REGIONS) + len(DEMO_ZONES) + len(DEMO_COMMUNITIES) + len(DEMO_DOMAIN_RESOURCES)


def reset_seed_resources(db: Session):
    """Resets all resources to their original initial availability status."""
    for item in MOCK_RESOURCES:
        r = db.query(CampusResourceDB).filter(CampusResourceDB.resource_id == item["resource_id"]).first()
        if r:
            r.availability_status = item.get("availability_status", "available")
            r.last_updated = datetime.now(timezone.utc)
    db.commit()


def seed_users(db: Session):
    """Seeds the default admin, department staff accounts, and a demo user.

    All inserts are idempotent (checked by username/email) so this is safe to
    run on every startup and never disturbs accounts a user has already created.
    """
    from backend.database.models import UserDB, DepartmentUserDB

    # 1) Privileged command-center account for the local response demo.
    existing = db.query(UserDB).filter(UserDB.username == "admin").first()
    if not existing:
        db.add(UserDB(
            username="admin",
            hashed_password=hash_password("password123"),
            role="operator",
            full_name="AITAM Response Commander",
            status="active",
        ))
        db.commit()

    # 2) One staff login per department (email + password + department).
    for email, full_name, department in DEPARTMENT_ACCOUNTS:
        existing_staff = db.query(DepartmentUserDB).filter(DepartmentUserDB.email == email).first()
        if existing_staff:
            if email == "rescue@aitam.local" and existing_staff.department == "SECURITY":
                existing_staff.department = "SEARCH_AND_RESCUE"
            continue
        password = "AITAM@Shelter123" if email == "shelter@aitam.local" else "password123"
        if not existing_staff:
            db.add(DepartmentUserDB(
                email=email,
                hashed_password=hash_password(password),
                full_name=full_name,
                department=department,
                role="department_head",
                status="active",
            ))
    db.commit()

    # 3) Demo citizen account for the user portal (login = email + phone).
    demo_email, demo_phone, demo_name = DEMO_USER
    if not db.query(UserDB).filter(UserDB.email == demo_email).first() \
            and not db.query(UserDB).filter(UserDB.username == demo_email).first():
        db.add(UserDB(
            username=demo_email,
            email=demo_email,
            phone=demo_phone,
            hashed_password=hash_password(f"phone:{demo_phone}"),
            role="user",
            full_name=demo_name,
            status="active",
        ))
        db.commit()


# Department staff accounts: (email, full_name, DEPARTMENT_CODE). Password is
# "password123" for all demo accounts.
DEPARTMENT_ACCOUNTS = [
    ("security@aitam.local", "Public Safety Control Room", "SECURITY"),
    ("medical@aitam.local", "Medical Response Centre", "MEDICAL"),
    ("rescue@aitam.local", "Search & Rescue Control Room", "SEARCH_AND_RESCUE"),
    ("transport@aitam.local", "Transport Control", "TRANSPORT"),
    ("communication@aitam.local", "Communications Desk", "COMMUNICATION"),
    ("fire@aitam.local", "Fire & Safety Post", "FIRE"),
    ("facilities@aitam.local", "Facilities Control", "FACILITIES"),
    ("shelter@aitam.local", "Shelter & Relief Desk", "SHELTER"),
]

# Demo citizen: (email, phone, full_name)
DEMO_USER = ("community@aitam.local", "9000000000", "Demo Community Member")


