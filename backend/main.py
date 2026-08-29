from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.config import settings
from backend.database.database import engine, Base, get_db, SessionLocal
from backend.database.migrate import ensure_schema
from backend.database.seed import seed_resources, seed_users, seed_disaster_domain, seed_organization
from backend.database.models import CampusResourceDB
from backend.api.incidents import router as incidents_router
from backend.api.resources import router as resources_router
from backend.api.responses import router as responses_router
from backend.api.approvals import router as approvals_router
from backend.api.audit import router as audit_router
from backend.api.dispatch import router as dispatch_router
from backend.api.simulation import router as simulation_router
from backend.api.events import router as events_router
from backend.api.routes import router as routes_router
from backend.api.auth import router as auth_router
from backend.api.telemetry import router as telemetry_router
from backend.api.voice import router as voice_router
from backend.api.system import router as system_router
from backend.api.assignments import router as assignments_router
from backend.api.notifications import router as notifications_router, alerts_router
from backend.api.disaster_domain import router as disaster_domain_router
from backend.api.chat import router as chat_router
from backend.api.campus_locations import router as campus_locations_router
from backend.api.transport import router as transport_router
from backend.api.road_conditions import router as road_conditions_router
from backend.api.risk import router as risk_router, demo_router
from backend.api.weather import router as weather_router
from backend.api.phase3 import router as phase3_router
from backend.api.map import router as map_router
from backend.api.earthquakes import router as earthquakes_router
from backend.api.organization import router as organization_router
from backend.api.intelligence import router as intelligence_router
from backend.api.location import router as location_router
from backend.api.evidence import router as evidence_router
from backend.services.notification_service import register_lifecycle_notifications


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables (creates any brand-new tables).
    Base.metadata.create_all(bind=engine)
    # Additive, idempotent migration: add new columns to pre-existing tables
    # and backfill them (department, category, status). Safe on fresh DBs.
    ensure_schema(engine)
    # Seed initial mock campus resources
    db = SessionLocal()
    try:
        seed_organization(db)
        seed_resources(db)
        seed_disaster_domain(db)
        seed_users(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Disaster Prediction & Community Response System — Aditya Institute of Technology and Management",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS from the explicitly configured frontend origin. Development
# keeps the existing local Vite ports; production never inherits them.
origins = [origin.strip() for origin in settings.FRONTEND_URL.split(",") if origin.strip()]
if settings.ENVIRONMENT.strip().lower() not in {"production", "prod"}:
    origins.extend([
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5175", "http://127.0.0.1:5175",
        "http://localhost:5176", "http://127.0.0.1:5176",
        "http://localhost:3000",
    ])
origins = list(dict.fromkeys(origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "X-Auth-Token", "X-Client-Operation-Id", "X-GPS-Device-Token"],
)

# Include API Routers
app.include_router(incidents_router)
app.include_router(resources_router)
app.include_router(responses_router)
app.include_router(approvals_router)
app.include_router(dispatch_router)
app.include_router(audit_router)
app.include_router(simulation_router)
app.include_router(events_router)
app.include_router(routes_router)
app.include_router(auth_router)
app.include_router(telemetry_router)
app.include_router(voice_router)
app.include_router(system_router)
app.include_router(assignments_router)
app.include_router(notifications_router)
app.include_router(alerts_router)
app.include_router(disaster_domain_router)
app.include_router(chat_router)
app.include_router(campus_locations_router)
app.include_router(transport_router)
app.include_router(road_conditions_router)
app.include_router(risk_router)
app.include_router(weather_router)
app.include_router(demo_router)
app.include_router(phase3_router)
app.include_router(map_router)
app.include_router(earthquakes_router)
app.include_router(organization_router)
app.include_router(intelligence_router)
app.include_router(location_router)
app.include_router(evidence_router)
register_lifecycle_notifications()






@app.get("/health", tags=["System"])
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint returning system status, database connectivity,
    and available seeded resources count.
    """
    try:
        # Verify database query execution
        db.execute(text("SELECT 1"))
        resource_count = db.query(CampusResourceDB).count()
        db_status = "connected"
    except Exception:
        # Health responses are public operational signals; do not return SQL,
        # filesystem, or provider exception text to clients.
        db_status = "error"
        resource_count = 0

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
        "seeded_resources": resource_count,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
