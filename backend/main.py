from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.config import settings
from backend.database.database import engine, Base, get_db, SessionLocal
from backend.database.seed import seed_resources
from backend.database.models import CampusResourceDB
from backend.api.incidents import router as incidents_router
from backend.api.resources import router as resources_router
from backend.api.responses import router as responses_router
from backend.api.approvals import router as approvals_router
from backend.api.audit import router as audit_router
from backend.api.dispatch import router as dispatch_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables
    Base.metadata.create_all(bind=engine)
    # Seed initial mock campus resources
    db = SessionLocal()
    try:
        seed_resources(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="AI Multi-Agent Campus Emergency Response & Resource Coordination System",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
origins = [
    settings.FRONTEND_URL,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(incidents_router)
app.include_router(resources_router)
app.include_router(responses_router)
app.include_router(approvals_router)
app.include_router(audit_router)
app.include_router(dispatch_router)





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
    except Exception as e:
        db_status = f"error: {str(e)}"
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
