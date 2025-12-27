# Database schema version: 4.3 (data migration to fix enum values)
import os
import secrets
from pathlib import Path
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from backend.api.routes import router as api_router
from backend.api.websocket import manager as ws_manager
from backend.db.database import create_db_and_tables, engine
from backend.scoring_engine.models_platform import User, Feis, Competition, Dancer, Entry, RoleType, CompetitionLevel
from backend.scoring_engine.models import Round
from sqlmodel import Session, select
from backend.api.auth import hash_password
from datetime import date
import uuid
import logging

logger = logging.getLogger(__name__)

# In local/venue mode, allow all origins for network access
LOCAL_MODE = os.getenv("OPENFEIS_LOCAL_MODE", "false").lower() == "true"

# Initial Data Seeding for MVP
def seed_data():
    with Session(engine) as session:
        seed_admin_email = os.getenv("OPENFEIS_SEED_ADMIN_EMAIL", "admin@openfeis.org")
        seed_admin_password = os.getenv("OPENFEIS_SEED_ADMIN_PASSWORD")

        # Default dev password (local mode only). In non-local mode we generate a random
        # password if one is not provided via env var.
        default_local_password = "admin123"
        if not seed_admin_password:
            if LOCAL_MODE:
                seed_admin_password = default_local_password
                logger.warning(
                    "OPENFEIS_SEED_ADMIN_PASSWORD is not set; using default local admin password for %s. "
                    "Change it immediately in any non-local deployment.",
                    seed_admin_email,
                )
            else:
                seed_admin_password = secrets.token_urlsafe(18)
                logger.warning(
                    "OPENFEIS_SEED_ADMIN_PASSWORD is not set; generated an initial admin password for %s: %s",
                    seed_admin_email,
                    seed_admin_password,
                )

        # Check if we have a super admin
        # Use select statement for SQLModel compatibility
        statement = select(User).where(User.email == seed_admin_email)
        existing_admin = session.exec(statement).first()
        
        if not existing_admin:
            admin = User(
                email=seed_admin_email,
                password_hash=hash_password(seed_admin_password),
                role=RoleType.SUPER_ADMIN,
                name="System Administrator",
                email_verified=True  # Admin starts verified
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
                level=CompetitionLevel.OPEN_CHAMPIONSHIP
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
    version="0.5.0",
    lifespan=lifespan
)

# CORS middleware for frontend
# In production, Caddy handles CORS, but we keep localhost for development
if LOCAL_MODE:
    # Local mode: allow any origin (devices on local network)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        # We use Bearer tokens (Authorization header), not cookies.
        # Browsers disallow allow_credentials with wildcard origins anyway.
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Production mode: restrict to known origins
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

@app.get("/health")
async def health_check():
    return {"status": "ok"}


# ============= WebSocket Endpoint for Real-Time Score Updates =============

@app.websocket("/ws/scores")
async def websocket_scores(
    websocket: WebSocket,
    competition_id: str = Query(None, description="Subscribe to a specific competition")
):
    """
    WebSocket endpoint for real-time score updates.
    
    Connect to receive live score broadcasts:
    - ws://server:8000/ws/scores - receive all score updates
    - ws://server:8000/ws/scores?competition_id=xxx - receive only updates for a specific competition
    
    Message types received:
    - {"type": "score_submitted", "competition_id": str, "entry_id": str, "value": float, ...}
    - {"type": "results_updated", "competition_id": str}
    - {"type": "ping"} - keepalive
    
    Send messages:
    - {"type": "subscribe", "competition_id": str} - subscribe to a competition
    - {"type": "unsubscribe", "competition_id": str} - unsubscribe from a competition
    - {"type": "pong"} - keepalive response
    """
    await ws_manager.connect(websocket, competition_id)
    
    try:
        while True:
            # Receive and handle client messages
            data = await websocket.receive_json()
            
            msg_type = data.get("type")
            
            if msg_type == "subscribe":
                comp_id = data.get("competition_id")
                if comp_id:
                    await ws_manager.subscribe_to_competition(websocket, comp_id)
                    await websocket.send_json({
                        "type": "subscribed",
                        "competition_id": comp_id
                    })
            
            elif msg_type == "unsubscribe":
                comp_id = data.get("competition_id")
                if comp_id:
                    await ws_manager.unsubscribe_from_competition(websocket, comp_id)
                    await websocket.send_json({
                        "type": "unsubscribed", 
                        "competition_id": comp_id
                    })
            
            elif msg_type == "pong":
                # Keepalive response - client is still connected
                pass
            
            elif msg_type == "ping":
                # Client requested a ping - respond with pong
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)


@app.get("/ws/stats")
async def websocket_stats():
    """Get WebSocket connection statistics (for debugging)."""
    return ws_manager.get_stats()

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
        # Don't intercept API/docs routes
        if full_path.startswith(("api/", "docs", "redoc", "openapi.json")):
            return None
        
        # Try to serve the exact file first (for favicon.ico, etc.)
        file_path = FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        
        # Otherwise, serve index.html for SPA routing
        return FileResponse(FRONTEND_DIR / "index.html")
