# Database schema version: 3 (added password hashing, authentication)
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from backend.api.routes import router as api_router
from backend.db.database import create_db_and_tables, engine
from backend.scoring_engine.models_platform import User, Feis, Competition, Dancer, Entry, RoleType, CompetitionLevel
from backend.scoring_engine.models import Round
from sqlmodel import Session, select
from backend.admin import setup_admin
from backend.api.auth import hash_password
from datetime import date
import uuid

# Initial Data Seeding for MVP
def seed_data():
    with Session(engine) as session:
        # Check if we have a super admin
        # Use select statement for SQLModel compatibility
        statement = select(User).where(User.email == "admin@openfeis.org")
        existing_admin = session.exec(statement).first()
        
        if not existing_admin:
            admin = User(
                email="admin@openfeis.org",
                password_hash=hash_password("admin123"),  # Now properly hashed!
                role=RoleType.SUPER_ADMIN,
                name="System Administrator"
            )
            session.add(admin)
            session.commit()
            session.refresh(admin)
            
            # Create a Sample Feis
            feis = Feis(
                organizer_id=admin.id,
                name="Great Irish Feis 2025",
                date=date(2025, 11, 20),
                location="Dublin, Ireland"
            )
            session.add(feis)
            session.commit()
            session.refresh(feis)

            # Create a Competition
            comp = Competition(
                feis_id=feis.id,
                name="Boys U12 Championship",
                min_age=10,
                max_age=12,
                level=CompetitionLevel.CHAMPIONSHIP
            )
            session.add(comp)
            session.commit()
            session.refresh(comp)
            
            session.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    seed_data()
    yield

app = FastAPI(
    title="Open Feis API",
    description="Scoring engine and management for Irish Dance competitions.",
    version="0.3.0",
    lifespan=lifespan
)

# CORS middleware for frontend
# In production, Caddy handles CORS, but we keep localhost for development
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://openfeis.org",
    "https://www.openfeis.org",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

# Setup SQLAdmin (Moved logic to backend/admin.py to keep main clean)
setup_admin(app, engine)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Static file serving for production (when frontend is built)
# The frontend is built into frontend/dist during Docker build
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"

if FRONTEND_DIR.exists():
    # Serve static assets (js, css, images)
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")
    
    # Catch-all route for SPA - must be last!
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """Serve the Vue SPA for all non-API routes."""
        # Don't intercept API, admin, docs routes
        if full_path.startswith(("api/", "admin/", "docs", "redoc", "openapi.json")):
            return None
        
        # Try to serve the exact file first (for favicon.ico, etc.)
        file_path = FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        
        # Otherwise, serve index.html for SPA routing
        return FileResponse(FRONTEND_DIR / "index.html")
