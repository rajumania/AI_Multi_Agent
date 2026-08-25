from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.database.models import CampusResourceDB
from backend.services.departments import department_for_resource_type
from backend.services.auth_service import hash_password

MOCK_RESOURCES = [
    {
        "resource_id": "AMB-001",
        "name": "Vignan Campus Ambulance 1 (Primary - Health Centre)",
        "resource_type": "ambulance",
        "location": "Campus Health & Medical Centre",
        "latitude": 16.2332,
        "longitude": 80.5502,
        "availability_status": "available",
        "capacity": 2,
        "quantity": 1,
        "contact": "Ext 401 / 0863-2344700 / Radio MED-1",
    },
    {
        "resource_id": "AMB-002",
        "name": "Vignan Campus Ambulance 2 (Hostel Zone)",
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
        "name": "Vignan Security Alpha - Main Vadlamudi Gate",
        "resource_type": "security",
        "location": "Main Vadlamudi Entrance Gate",
        "latitude": 16.2320,
        "longitude": 80.5490,
        "availability_status": "available",
        "capacity": 4,
        "quantity": 1,
        "contact": "Ext 101 / Radio SEC-ALPHA",
    },
    {
        "resource_id": "SEC-002",
        "name": "Vignan Security Bravo - Academic Quad (U-Block & H-Block)",
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
        "name": "Vignan Security Patrol - Hostels & Perimeter",
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
        "location": "Student Activity Center (SAC)",
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
        "name": "NTR Vignan Vihar / Convocation Hall Shelter",
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
        "name": "Vignan Indoor Stadium Emergency Shelter",
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
        "name": "Vignan Rapid Evacuation Van 1",
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
        "name": "Vignan University Evacuation Bus Fleet 1",
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
        "name": "Vignan Facilities & Power Hazard Crew",
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
        "name": "Vignan Rapid Fire Safety & Extinguisher Squad",
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
            department=department_for_resource_type(item["resource_type"]),
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


def seed_users(db: Session):
    """Seeds the default admin, six department staff accounts, and a demo user.

    All inserts are idempotent (checked by username/email) so this is safe to
    run on every startup and never disturbs accounts a user has already created.
    """
    from backend.database.models import UserDB, DepartmentUserDB

    # 1) Legacy privileged command-center account (Main Admin / operator).
    existing = db.query(UserDB).filter(UserDB.username == "admin").first()
    if not existing:
        db.add(UserDB(
            username="admin",
            hashed_password=hash_password("password123"),
            role="operator",
            full_name="Campus Safety Director",
            status="active",
        ))
        db.commit()

    # 2) One staff login per department (email + password + department).
    for email, full_name, department in DEPARTMENT_ACCOUNTS:
        if not db.query(DepartmentUserDB).filter(DepartmentUserDB.email == email).first():
            db.add(DepartmentUserDB(
                email=email,
                hashed_password=hash_password("password123"),
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
    ("security@vignan.ac.in", "Security Control Room", "SECURITY"),
    ("medical@vignan.ac.in", "Campus Health Centre", "MEDICAL"),
    ("transport@vignan.ac.in", "Transport Control", "TRANSPORT"),
    ("communication@vignan.ac.in", "Communications Desk", "COMMUNICATION"),
    ("fire@vignan.ac.in", "Fire & Safety Post", "FIRE"),
    ("facilities@vignan.ac.in", "Facilities Control", "FACILITIES"),
]

# Demo citizen: (email, phone, full_name)
DEMO_USER = ("student@vignan.ac.in", "9000000000", "Demo Student")


