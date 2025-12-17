"""
Main API Router - Combines all sub-routers into the main application router.

All route implementations have been extracted to domain-specific routers in backend/api/routers/.
This file only handles router aggregation.
"""
from fastapi import APIRouter

# Import all routers
from backend.api.routers import auth as auth_router
from backend.api.routers import users as users_router
from backend.api.routers import sync as sync_router
from backend.api.routers import admin as admin_router
from backend.api.routers import waitlist as waitlist_router
from backend.api.routers import checkin as checkin_router
from backend.api.routers import scoring as scoring_router
from backend.api.routers import competitions as competitions_router
from backend.api.routers import entries as entries_router
from backend.api.routers import advancement as advancement_router
from backend.api.routers import checkout as checkout_router
from backend.api.routers import scheduling as scheduling_router
from backend.api.routers import teacher as teacher_router
from backend.api.routers import feis as feis_router
from backend.api.routers import feis_operations as feis_operations_router
from backend.api.routers import adjudicators as adjudicators_router
from backend.api.routers import panels as panels_router

# Create main router
router = APIRouter()

# Include all sub-routers
router.include_router(auth_router.router, tags=["auth"])
router.include_router(users_router.router, tags=["users"])
router.include_router(sync_router.router, tags=["sync"])
router.include_router(admin_router.router, tags=["admin"])
router.include_router(waitlist_router.router, tags=["waitlist"])
router.include_router(checkin_router.router, tags=["checkin"])
router.include_router(scoring_router.router, tags=["scoring"])
router.include_router(competitions_router.router, tags=["competitions"])
router.include_router(entries_router.router, tags=["entries"])
router.include_router(advancement_router.router, tags=["advancement"])
router.include_router(checkout_router.router, tags=["checkout"])
router.include_router(scheduling_router.router, tags=["scheduling"])
router.include_router(teacher_router.router, tags=["teacher"])
router.include_router(feis_router.router, tags=["feis"])
router.include_router(feis_operations_router.router, tags=["feis-operations"])
router.include_router(adjudicators_router.router, tags=["adjudicators"])
router.include_router(panels_router.router, tags=["panels"])
