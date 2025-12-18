from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from uuid import UUID
from sqlmodel import Session, select, func
from backend.db.database import get_session
from backend.api.auth import get_current_user, require_admin, require_organizer_or_admin
from backend.scoring_engine.models_platform import (
    SiteSettings, User, Feis, Competition, RoleType, Dancer, Entry,
    CompetitionLevel, Gender, DanceType, ScoringMethod, CompetitionCategory
)
from backend.api.schemas import (
    SiteSettingsResponse, SiteSettingsUpdate,
    SyllabusGenerationRequest, SyllabusGenerationResponse,
    DemoDataStatus, DemoDataSummary
)
from backend.services.email import get_site_settings
from backend.services.demo_data import has_demo_data, populate_demo_data, delete_demo_data
from backend.utils.competition_codes import generate_competition_code
from backend.services.scheduling import get_dance_type_from_name, get_default_tempo

router = APIRouter()

def format_level_name(level: str) -> str:
    """Format level name for display."""
    return level.replace('_', ' ').title()

@router.get("/admin/settings", response_model=SiteSettingsResponse)
async def get_settings(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin())
):
    """Get site settings. Requires super_admin role."""
    settings = get_site_settings(session)
    
    return SiteSettingsResponse(
        resend_configured=bool(settings.resend_api_key),
        resend_from_email=settings.resend_from_email,
        site_name=settings.site_name,
        site_url=settings.site_url
    )


@router.put("/admin/settings", response_model=SiteSettingsResponse)
async def update_settings(
    settings_data: SiteSettingsUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin())
):
    """Update site settings. Requires super_admin role."""
    settings = get_site_settings(session)
    
    if settings_data.resend_api_key is not None:
        settings.resend_api_key = settings_data.resend_api_key
    if settings_data.resend_from_email is not None:
        settings.resend_from_email = settings_data.resend_from_email
    if settings_data.site_name is not None:
        settings.site_name = settings_data.site_name
    if settings_data.site_url is not None:
        settings.site_url = settings_data.site_url
    
    session.add(settings)
    session.commit()
    session.refresh(settings)
    
    return SiteSettingsResponse(
        resend_configured=bool(settings.resend_api_key),
        resend_from_email=settings.resend_from_email,
        site_name=settings.site_name,
        site_url=settings.site_url
    )


@router.post("/admin/syllabus/generate", response_model=SyllabusGenerationResponse)
async def generate_syllabus(
    request: SyllabusGenerationRequest, 
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Auto-generate syllabus competitions. Requires organizer or super_admin role."""
    feis = session.get(Feis, UUID(request.feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check ownership (unless super_admin)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only generate syllabus for your own feis")
    
    count = 0
    
    # Determine age configs to process
    age_configs = []
    
    if request.selected_ages:
        for age_str in request.selected_ages:
            if age_str.lower() == "adult":
                age_configs.append({
                    "label": "Adult",
                    "min_age": 25,
                    "max_age": 99,
                    "code_age": 99,
                    "is_over": False, # Adults usually treated as U99 or similar
                    "is_adult": True
                })
            elif age_str.startswith("U"):
                try:
                    val = int(age_str[1:])
                    age_configs.append({
                        "label": age_str,
                        "min_age": 0, # Allow dancing up
                        "max_age": val,
                        "code_age": val,
                        "is_over": False,
                        "is_adult": False
                    })
                except ValueError:
                    continue
            elif age_str.startswith("O"):
                try:
                    val = int(age_str[1:])
                    age_configs.append({
                        "label": age_str,
                        "min_age": val + 1,
                        "max_age": 99,
                        "code_age": val, # Pass the reference age (e.g. 15 for O15)
                        "is_over": True,
                        "is_adult": False
                    })
                except ValueError:
                    continue
    else:
        # Legacy loop behavior (U-ages only, step 2)
        current_age = request.min_age
        while current_age <= request.max_age:
            age_configs.append({
                "label": f"U{current_age}",
                "min_age": current_age - 2,
                "max_age": current_age,
                "code_age": current_age,
                "is_over": False,
                "is_adult": False
            })
            current_age += 2
            
    # ===== SOLO DANCES =====
    for age_config in age_configs:
        age_group = age_config["label"]
        min_age_val = age_config["min_age"]
        max_age_val = age_config["max_age"]
        
        for gender in request.genders:
            for level in request.levels:
                # Skip championship levels in solo loop - they are one event per age/gender
                if level in (CompetitionLevel.PRELIMINARY_CHAMPIONSHIP, CompetitionLevel.OPEN_CHAMPIONSHIP):
                    continue
                    
                for dance in request.dances:
                    # Handle open (non-gendered) competitions - 'other' means open to all
                    is_open = gender.value == 'other'
                    if is_open:
                        comp_name = f"{age_group} {dance} ({format_level_name(level.value)})"
                    else:
                        gender_label = "Boys" if gender.value == 'male' else "Girls"
                        comp_name = f"{gender_label} {age_group} {dance} ({format_level_name(level.value)})"
                    
                    # Map dance name to DanceType enum
                    dance_type = get_dance_type_from_name(dance)
                    tempo = get_default_tempo(dance_type)
                    
                    # Generate competition code
                    code = generate_competition_code(
                        level=level.value,
                        min_age=age_config["code_age"],
                        dance_type=dance_type.value if dance_type else None,
                        is_over=age_config["is_over"],
                        gender=gender.value if gender else None
                    )
                    
                    comp = Competition(
                        feis_id=feis.id,
                        name=comp_name,
                        min_age=min_age_val,
                        max_age=max_age_val,
                        level=level,
                        gender=None if is_open else gender,  # Open competitions have no gender restriction
                        code=code,
                        category=CompetitionCategory.SOLO,
                        is_mixed=False,
                        # New fields
                        dance_type=dance_type,
                        tempo_bpm=tempo,
                        bars=48,  # Standard
                        scoring_method=request.scoring_method,
                        price_cents=request.price_cents
                    )
                    session.add(comp)
                    count += 1
    
    # ===== FIGURE/CEILI DANCES =====
    # Figure dances are NOT leveled - they're open to all grade levels, divided by age only
    if request.figure_dances:
        figure_dance_map = {
            "2-Hand": DanceType.TWO_HAND,
            "3-Hand": DanceType.THREE_HAND,
            "4-Hand": DanceType.FOUR_HAND,
            "6-Hand": DanceType.SIX_HAND,
            "8-Hand": DanceType.EIGHT_HAND,
        }
        
        for age_config in age_configs:
            age_group = age_config["label"]
            min_age_val = age_config["min_age"]
            max_age_val = age_config["max_age"]
            
            for fig_dance in request.figure_dances:
                dance_type = figure_dance_map.get(fig_dance)
                if not dance_type:
                    continue
                
                # Create girls-only figure competition (standard)
                comp_name = f"Girls {age_group} {fig_dance}"
                code = generate_competition_code(
                    level="novice",  # Use novice as placeholder since figure dances aren't leveled
                    min_age=age_config["code_age"],
                    dance_type=dance_type.value,
                    is_over=age_config["is_over"],
                    is_mixed=False
                )
                
                # Only add suffix if not using the new figure dance format (ending in FD/FM)
                if not (code.endswith("FD") or code.endswith("FM")):
                    code += "G"  # Add 'G' suffix for girls
                
                comp = Competition(
                    feis_id=feis.id,
                    name=comp_name,
                    min_age=min_age_val,
                    max_age=max_age_val,
                    level=CompetitionLevel.NOVICE,  # Placeholder - figure dances are open level
                    gender=Gender.FEMALE,
                    code=code,
                    category=CompetitionCategory.FIGURE,
                    is_mixed=False,
                    dance_type=dance_type,
                    tempo_bpm=113,  # Figure dances typically 113 bpm
                    bars=48,
                    scoring_method=ScoringMethod.SOLO,  # Figure dances use solo scoring
                    price_cents=request.price_cents
                )
                session.add(comp)
                count += 1
                
                # Create mixed figure competition if enabled
                if request.include_mixed_figure:
                    comp_name = f"Mixed {age_group} {fig_dance}"
                    code = generate_competition_code(
                        level="novice",
                        min_age=age_config["code_age"],
                        dance_type=dance_type.value,
                        is_over=age_config["is_over"],
                        is_mixed=True
                    )
                    
                    # Only add suffix if not using the new figure dance format
                    if not (code.endswith("FD") or code.endswith("FM")):
                        code += "M"  # Add 'M' suffix for mixed
                    
                    comp = Competition(
                        feis_id=feis.id,
                        name=comp_name,
                        min_age=min_age_val,
                        max_age=max_age_val,
                        level=CompetitionLevel.NOVICE,  # Placeholder - figure dances are open level
                        gender=None,  # Mixed - no gender restriction
                        code=code,
                        category=CompetitionCategory.FIGURE,
                        is_mixed=True,
                        dance_type=dance_type,
                        tempo_bpm=113,
                        bars=48,
                        scoring_method=ScoringMethod.SOLO,
                        price_cents=request.price_cents
                    )
                    session.add(comp)
                    count += 1
    
    # ===== CHAMPIONSHIPS =====
    # Find championship levels in the main levels list
    champ_levels = [l for l in request.levels if l in (CompetitionLevel.PRELIMINARY_CHAMPIONSHIP, CompetitionLevel.OPEN_CHAMPIONSHIP)]
    
    # Also support the legacy include_championships/championship_types flags
    if request.include_championships and request.championship_types:
        champ_level_map = {
            "prelim": CompetitionLevel.PRELIMINARY_CHAMPIONSHIP,
            "open": CompetitionLevel.OPEN_CHAMPIONSHIP,
        }
        for ct in request.championship_types:
            level = champ_level_map.get(ct)
            if level and level not in champ_levels:
                champ_levels.append(level)
        
    if champ_levels:
        for age_config in age_configs:
            age_group = age_config["label"]
            min_age_val = age_config["min_age"]
            max_age_val = age_config["max_age"]
            
            for gender in request.genders:
                for level in champ_levels:
                    # Handle open (non-gendered) championships
                    is_open = gender.value == 'other'
                    champ_label = "Preliminary Championship" if level == CompetitionLevel.PRELIMINARY_CHAMPIONSHIP else "Open Championship"
                    if is_open:
                        comp_name = f"{age_group} {champ_label}"
                    else:
                        gender_label = "Boys" if gender.value == 'male' else "Girls"
                        comp_name = f"{gender_label} {age_group} {champ_label}"
                    
                    code = generate_competition_code(
                        level=level.value,
                        min_age=age_config["code_age"],
                        is_over=age_config["is_over"],
                        gender=gender.value if gender else None
                    )
                    
                    comp = Competition(
                        feis_id=feis.id,
                        name=comp_name,
                        min_age=min_age_val,
                        max_age=max_age_val,
                        level=level,
                        gender=None if is_open else gender,  # Open championships have no gender restriction
                        code=code,
                        category=CompetitionCategory.CHAMPIONSHIP,
                        is_mixed=False,
                        dance_type=None,  # Championships have multiple dances
                        tempo_bpm=None,
                        bars=48,
                        scoring_method=ScoringMethod.CHAMPIONSHIP,
                        price_cents=request.price_cents * 2  # Championships typically cost more
                    )
                    session.add(comp)
                    count += 1
    
    session.commit()
    
    return SyllabusGenerationResponse(
        generated_count=count,
        message=f"Successfully created {count} competitions for {feis.name}."
    )


@router.get("/admin/demo-data/status", response_model=DemoDataStatus)
async def get_demo_data_status(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """
    Check if demo data exists in the system.
    Super Admin only.
    """
    has_data = has_demo_data(session)
    return DemoDataStatus(
        has_demo_data=has_data,
        message="Demo data is present in the database." if has_data else "No demo data found."
    )


@router.post("/admin/demo-data/populate", response_model=DemoDataSummary)
async def populate_demo_data_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """
    Populate the database with comprehensive demo data.
    
    Creates:
    - 1 demo organizer, 8 teachers, 6 adjudicators
    - 3 feiseanna:
      - Shamrock Classic Feis (60 days out, ~250 dancers)
      - Celtic Pride Championships (90 days out, ~103 dancers)  
      - Emerald Isle Fall Feis (7 days ago, ~100 dancers, with complete results)
    - Full syllabus with competitions for each feis
    - Realistic registrations, schedules, and (for past feis) scores
    
    Super Admin only.
    """
    if has_demo_data(session):
        return DemoDataSummary(
            success=False,
            message="Demo data already exists. Delete existing demo data first."
        )
    
    try:
        summary = populate_demo_data(session)
        return DemoDataSummary(
            success=True,
            message=f"Successfully created demo data: {summary['feiseanna']} feiseanna, {summary['dancers']} dancers, {summary['entries']} entries.",
            **summary
        )
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to populate demo data: {str(e)}"
        )


@router.delete("/admin/demo-data", response_model=DemoDataSummary)
async def delete_demo_data_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """
    Delete all demo data from the database.
    
    Identifies demo data by email patterns (demo_*@openfeis.demo).
    This will delete:
    - All demo users (organizers, teachers, parents, adjudicators)
    - All feiseanna created by demo organizers
    - All dancers belonging to demo parents
    - All associated entries, scores, etc.
    
    Super Admin only.
    """
    if not has_demo_data(session):
        return DemoDataSummary(
            success=False,
            message="No demo data found to delete."
        )
    
    try:
        summary = delete_demo_data(session)
        return DemoDataSummary(
            success=True,
            message=f"Successfully deleted demo data: {summary['users_deleted']} users, {summary['feiseanna_deleted']} feiseanna, {summary['dancers_deleted']} dancers.",
            feiseanna=summary["feiseanna_deleted"],
            dancers=summary["dancers_deleted"],
            entries=summary["entries_deleted"],
            scores=summary["scores_deleted"]
        )
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete demo data: {str(e)}"
        )
