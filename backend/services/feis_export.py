"""
Feis Export/Import Service

Exports a complete feis to JSON format including:
- Feis metadata
- Settings and fee items  
- Stages and competitions
- Adjudicators, panels, and coverage
- Dancers and entries
- Orders and scores (optional)

Import creates missing records and links existing ones based on email/identifiers.
"""
from typing import Dict, List, Any, Optional, Tuple
from uuid import UUID, uuid4
from datetime import datetime, date, time
from sqlmodel import Session, select
import secrets
from passlib.context import CryptContext

from backend.scoring_engine.models_platform import (
    User, Feis, FeisSettings, FeeItem, Stage, Competition,
    FeisAdjudicator, JudgePanel, PanelMember, StageJudgeCoverage,
    Dancer, Entry, Order, OrderItem, FeisOrganizer,
    RoleType, CompetitionLevel, Gender, DanceType, CompetitionCategory,
    ScoringMethod, FeeCategory, PaymentStatus, CheckInStatus,
    AdjudicatorStatus, AvailabilityType
)
from backend.scoring_engine.models import Round, JudgeScore

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def export_feis(session: Session, feis_id: UUID) -> Dict[str, Any]:
    """
    Export a complete feis to a JSON-serializable dictionary.
    
    Returns a comprehensive snapshot that can be used for:
    - Archival
    - Cloning/templating
    - Migration between servers
    """
    feis = session.get(Feis, feis_id)
    if not feis:
        raise ValueError(f"Feis {feis_id} not found")
    
    # Get primary organizer info
    organizer = session.get(User, feis.organizer_id)
    
    # Export feis metadata
    export_data = {
        "export_version": "1.0",
        "exported_at": datetime.utcnow().isoformat(),
        "feis": {
            "id": str(feis.id),
            "name": feis.name,
            "date": feis.date.isoformat(),
            "location": feis.location,
            "stripe_account_id": feis.stripe_account_id,
            "organizer_email": organizer.email if organizer else None,
            "organizer_name": organizer.name if organizer else None,
        },
        "settings": None,
        "fee_items": [],
        "stages": [],
        "competitions": [],
        "adjudicators": [],
        "panels": [],
        "stage_coverage": [],
        "co_organizers": [],
        "dancers": [],
        "entries": [],
        "orders": [],
        "rounds": [],
        "scores": [],
    }
    
    # Export settings
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == feis.id)
    ).first()
    if settings:
        export_data["settings"] = {
            "base_entry_fee_cents": settings.base_entry_fee_cents,
            "per_competition_fee_cents": settings.per_competition_fee_cents,
            "family_max_cents": settings.family_max_cents,
            "late_fee_cents": settings.late_fee_cents,
            "late_fee_date": settings.late_fee_date.isoformat() if settings.late_fee_date else None,
            "change_fee_cents": settings.change_fee_cents,
            "registration_opens": settings.registration_opens.isoformat() if settings.registration_opens else None,
            "registration_closes": settings.registration_closes.isoformat() if settings.registration_closes else None,
            "global_dancer_cap": settings.global_dancer_cap,
            "enable_waitlist": settings.enable_waitlist,
            "waitlist_offer_hours": settings.waitlist_offer_hours,
            "allow_scratches": settings.allow_scratches,
            "scratch_refund_percent": settings.scratch_refund_percent,
            "scratch_deadline": settings.scratch_deadline.isoformat() if settings.scratch_deadline else None,
            "grades_judges_per_stage": settings.grades_judges_per_stage,
            "champs_judges_per_panel": settings.champs_judges_per_panel,
            "lunch_duration_minutes": settings.lunch_duration_minutes,
            "lunch_window_start": settings.lunch_window_start.isoformat() if settings.lunch_window_start else None,
            "lunch_window_end": settings.lunch_window_end.isoformat() if settings.lunch_window_end else None,
        }
    
    # Export fee items
    fee_items = session.exec(
        select(FeeItem).where(FeeItem.feis_id == feis.id)
    ).all()
    for item in fee_items:
        export_data["fee_items"].append({
            "id": str(item.id),
            "name": item.name,
            "description": item.description,
            "amount_cents": item.amount_cents,
            "category": item.category.value,
            "required": item.required,
            "max_quantity": item.max_quantity,
            "active": item.active,
        })
    
    # Export stages
    stages = session.exec(
        select(Stage).where(Stage.feis_id == feis.id).order_by(Stage.sequence)
    ).all()
    for stage in stages:
        export_data["stages"].append({
            "id": str(stage.id),
            "name": stage.name,
            "color": stage.color,
            "sequence": stage.sequence,
        })
    
    # Export competitions
    competitions = session.exec(
        select(Competition).where(Competition.feis_id == feis.id)
    ).all()
    for comp in competitions:
        export_data["competitions"].append({
            "id": str(comp.id),
            "name": comp.name,
            "min_age": comp.min_age,
            "max_age": comp.max_age,
            "level": comp.level.value,
            "gender": comp.gender.value if comp.gender else None,
            "code": comp.code,
            "category": comp.category.value,
            "is_mixed": comp.is_mixed,
            "description": comp.description,
            "allowed_levels": comp.allowed_levels,
            "dance_type": comp.dance_type.value if comp.dance_type else None,
            "tempo_bpm": comp.tempo_bpm,
            "bars": comp.bars,
            "scoring_method": comp.scoring_method.value,
            "price_cents": comp.price_cents,
            "max_entries": comp.max_entries,
            "fee_category": comp.fee_category.value,
            "stage_id": str(comp.stage_id) if comp.stage_id else None,
            "scheduled_time": comp.scheduled_time.isoformat() if comp.scheduled_time else None,
            "estimated_duration_minutes": comp.estimated_duration_minutes,
        })
    
    # Export adjudicators
    adjudicators = session.exec(
        select(FeisAdjudicator).where(FeisAdjudicator.feis_id == feis.id)
    ).all()
    for adj in adjudicators:
        linked_user = session.get(User, adj.user_id) if adj.user_id else None
        school_user = session.get(User, adj.school_affiliation_id) if adj.school_affiliation_id else None
        export_data["adjudicators"].append({
            "id": str(adj.id),
            "user_email": linked_user.email if linked_user else adj.email,
            "name": adj.name,
            "email": adj.email,
            "phone": adj.phone,
            "credential": adj.credential,
            "organization": adj.organization,
            "school_affiliation_email": school_user.email if school_user else None,
            "status": adj.status.value,
            "created_at": adj.created_at.isoformat(),
            "confirmed_at": adj.confirmed_at.isoformat() if adj.confirmed_at else None,
        })
    
    # Export panels
    panels = session.exec(
        select(JudgePanel).where(JudgePanel.feis_id == feis.id)
    ).all()
    for panel in panels:
        members = session.exec(
            select(PanelMember).where(PanelMember.panel_id == panel.id).order_by(PanelMember.sequence)
        ).all()
        member_list = []
        for member in members:
            adj = session.get(FeisAdjudicator, member.feis_adjudicator_id)
            if adj:
                member_list.append({
                    "adjudicator_name": adj.name,
                    "adjudicator_email": adj.email,
                    "sequence": member.sequence,
                })
        export_data["panels"].append({
            "id": str(panel.id),
            "name": panel.name,
            "description": panel.description,
            "members": member_list,
            "created_at": panel.created_at.isoformat(),
        })
    
    # Export stage coverage
    coverage_blocks = session.exec(
        select(StageJudgeCoverage).where(
            StageJudgeCoverage.stage_id.in_([s.id for s in stages])
        )
    ).all()
    for cov in coverage_blocks:
        stage = session.get(Stage, cov.stage_id)
        adj = session.get(FeisAdjudicator, cov.feis_adjudicator_id) if cov.feis_adjudicator_id else None
        panel = session.get(JudgePanel, cov.panel_id) if cov.panel_id else None
        export_data["stage_coverage"].append({
            "id": str(cov.id),
            "stage_name": stage.name if stage else None,
            "adjudicator_name": adj.name if adj else None,
            "adjudicator_email": adj.email if adj else None,
            "panel_name": panel.name if panel else None,
            "feis_day": cov.feis_day.isoformat(),
            "start_time": cov.start_time.isoformat(),
            "end_time": cov.end_time.isoformat(),
            "note": cov.note,
        })
    
    # Export co-organizers
    co_organizers = session.exec(
        select(FeisOrganizer).where(FeisOrganizer.feis_id == feis.id)
    ).all()
    for co_org in co_organizers:
        user = session.get(User, co_org.user_id)
        export_data["co_organizers"].append({
            "user_email": user.email if user else None,
            "user_name": user.name if user else None,
            "role": co_org.role,
            "can_edit_feis": co_org.can_edit_feis,
            "can_manage_entries": co_org.can_manage_entries,
            "can_manage_schedule": co_org.can_manage_schedule,
            "can_manage_adjudicators": co_org.can_manage_adjudicators,
            "can_add_organizers": co_org.can_add_organizers,
            "added_at": co_org.added_at.isoformat(),
        })
    
    # Export entries and dancers
    entries = session.exec(
        select(Entry)
        .join(Competition, Entry.competition_id == Competition.id)
        .where(Competition.feis_id == feis.id)
    ).all()
    
    dancer_ids = set()
    for entry in entries:
        dancer_ids.add(entry.dancer_id)
    
    # Export dancers
    for dancer_id in dancer_ids:
        dancer = session.get(Dancer, dancer_id)
        if not dancer:
            continue
        parent = session.get(User, dancer.parent_id)
        school = session.get(User, dancer.school_id) if dancer.school_id else None
        export_data["dancers"].append({
            "id": str(dancer.id),
            "parent_email": parent.email if parent else None,
            "parent_name": parent.name if parent else None,
            "school_email": school.email if school else None,
            "name": dancer.name,
            "dob": dancer.dob.isoformat(),
            "current_level": dancer.current_level.value,
            "gender": dancer.gender.value,
            "clrg_number": dancer.clrg_number,
            "is_adult": dancer.is_adult,
            "level_reel": dancer.level_reel.value if dancer.level_reel else None,
            "level_light_jig": dancer.level_light_jig.value if dancer.level_light_jig else None,
            "level_slip_jig": dancer.level_slip_jig.value if dancer.level_slip_jig else None,
            "level_single_jig": dancer.level_single_jig.value if dancer.level_single_jig else None,
            "level_treble_jig": dancer.level_treble_jig.value if dancer.level_treble_jig else None,
            "level_hornpipe": dancer.level_hornpipe.value if dancer.level_hornpipe else None,
            "level_traditional_set": dancer.level_traditional_set.value if dancer.level_traditional_set else None,
            "level_figure": dancer.level_figure.value if dancer.level_figure else None,
        })
    
    # Export entries
    for entry in entries:
        comp = session.get(Competition, entry.competition_id)
        dancer = session.get(Dancer, entry.dancer_id)
        export_data["entries"].append({
            "id": str(entry.id),
            "dancer_name": dancer.name if dancer else None,
            "dancer_parent_email": dancer.parent.email if dancer and dancer.parent else None,
            "competition_code": comp.code if comp else None,
            "competition_name": comp.name if comp else None,
            "competitor_number": entry.competitor_number,
            "paid": entry.paid,
            "pay_later": entry.pay_later,
            "check_in_status": entry.check_in_status.value,
            "checked_in_at": entry.checked_in_at.isoformat() if entry.checked_in_at else None,
            "cancelled": entry.cancelled,
            "cancelled_at": entry.cancelled_at.isoformat() if entry.cancelled_at else None,
            "cancellation_reason": entry.cancellation_reason,
            "refund_amount_cents": entry.refund_amount_cents,
        })
    
    # Export orders
    orders = session.exec(
        select(Order).where(Order.feis_id == feis.id)
    ).all()
    for order in orders:
        user = session.get(User, order.user_id)
        order_items = session.exec(
            select(OrderItem).where(OrderItem.order_id == order.id)
        ).all()
        items_data = []
        for item in order_items:
            fee_item = session.get(FeeItem, item.fee_item_id)
            items_data.append({
                "fee_item_name": fee_item.name if fee_item else None,
                "quantity": item.quantity,
                "unit_price_cents": item.unit_price_cents,
                "total_cents": item.total_cents,
            })
        export_data["orders"].append({
            "id": str(order.id),
            "user_email": user.email if user else None,
            "subtotal_cents": order.subtotal_cents,
            "qualifying_subtotal_cents": order.qualifying_subtotal_cents,
            "non_qualifying_subtotal_cents": order.non_qualifying_subtotal_cents,
            "family_discount_cents": order.family_discount_cents,
            "late_fee_cents": order.late_fee_cents,
            "total_cents": order.total_cents,
            "status": order.status.value,
            "refund_total_cents": order.refund_total_cents,
            "refunded_at": order.refunded_at.isoformat() if order.refunded_at else None,
            "refund_reason": order.refund_reason,
            "created_at": order.created_at.isoformat(),
            "paid_at": order.paid_at.isoformat() if order.paid_at else None,
            "items": items_data,
        })
    
    # Export rounds and scores
    for comp in competitions:
        rounds = session.exec(
            select(Round).where(Round.competition_id == comp.id)
        ).all()
        for round_obj in rounds:
            export_data["rounds"].append({
                "id": round_obj.id,
                "competition_code": comp.code,
                "name": round_obj.name,
                "sequence": round_obj.sequence,
            })
            
            scores = session.exec(
                select(JudgeScore).where(JudgeScore.round_id == round_obj.id)
            ).all()
            for score in scores:
                export_data["scores"].append({
                    "id": str(score.id),
                    "judge_id": score.judge_id,
                    "competitor_id": score.competitor_id,
                    "round_id": score.round_id,
                    "value": score.value,
                    "notes": score.notes,
                    "timestamp": score.timestamp.isoformat(),
                })
    
    return export_data


def import_feis(
    session: Session,
    import_data: Dict[str, Any],
    importing_user: User,
    include_orders: bool = True
) -> Dict[str, Any]:
    """
    Import a feis from exported JSON data.
    
    Creates missing records and links existing ones based on email/identifiers.
    Returns a summary report of what was created vs. linked.
    
    Args:
        session: Database session
        import_data: Exported feis data dictionary
        importing_user: User performing the import (becomes primary organizer)
        include_orders: Whether to import order history
    
    Returns:
        Summary report with counts of created/linked records
    """
    report = {
        "success": True,
        "feis_id": None,
        "feis_name": None,
        "created": {
            "users": 0,
            "dancers": 0,
            "stages": 0,
            "competitions": 0,
            "adjudicators": 0,
            "panels": 0,
            "entries": 0,
            "orders": 0,
        },
        "linked": {
            "users": 0,
            "dancers": 0,
            "adjudicators": 0,
        },
        "skipped": {
            "dancers": 0,
            "orders": 0,
        },
        "errors": [],
    }
    
    try:
        # Create new feis with importing user as organizer
        feis_data = import_data["feis"]
        new_feis = Feis(
            name=feis_data["name"],
            date=date.fromisoformat(feis_data["date"]),
            location=feis_data["location"],
            organizer_id=importing_user.id,
        )
        session.add(new_feis)
        session.flush()
        
        report["feis_id"] = str(new_feis.id)
        report["feis_name"] = new_feis.name
        
        # Import settings
        if import_data.get("settings"):
            settings_data = import_data["settings"]
            settings = FeisSettings(
                feis_id=new_feis.id,
                base_entry_fee_cents=settings_data.get("base_entry_fee_cents", 2500),
                per_competition_fee_cents=settings_data.get("per_competition_fee_cents", 1000),
                family_max_cents=settings_data.get("family_max_cents"),
                late_fee_cents=settings_data.get("late_fee_cents", 500),
                late_fee_date=date.fromisoformat(settings_data["late_fee_date"]) if settings_data.get("late_fee_date") else None,
                change_fee_cents=settings_data.get("change_fee_cents", 1000),
                registration_opens=datetime.fromisoformat(settings_data["registration_opens"]) if settings_data.get("registration_opens") else None,
                registration_closes=datetime.fromisoformat(settings_data["registration_closes"]) if settings_data.get("registration_closes") else None,
                global_dancer_cap=settings_data.get("global_dancer_cap"),
                enable_waitlist=settings_data.get("enable_waitlist", True),
                waitlist_offer_hours=settings_data.get("waitlist_offer_hours", 48),
                allow_scratches=settings_data.get("allow_scratches", True),
                scratch_refund_percent=settings_data.get("scratch_refund_percent", 50),
                scratch_deadline=datetime.fromisoformat(settings_data["scratch_deadline"]) if settings_data.get("scratch_deadline") else None,
                grades_judges_per_stage=settings_data.get("grades_judges_per_stage", 1),
                champs_judges_per_panel=settings_data.get("champs_judges_per_panel", 3),
                lunch_duration_minutes=settings_data.get("lunch_duration_minutes", 30),
                lunch_window_start=time.fromisoformat(settings_data["lunch_window_start"]) if settings_data.get("lunch_window_start") else None,
                lunch_window_end=time.fromisoformat(settings_data["lunch_window_end"]) if settings_data.get("lunch_window_end") else None,
            )
            session.add(settings)
        
        # Import fee items
        fee_item_map = {}  # old_id -> new record
        for item_data in import_data.get("fee_items", []):
            fee_item = FeeItem(
                feis_id=new_feis.id,
                name=item_data["name"],
                description=item_data.get("description"),
                amount_cents=item_data["amount_cents"],
                category=FeeCategory(item_data["category"]),
                required=item_data.get("required", False),
                max_quantity=item_data.get("max_quantity", 1),
                active=item_data.get("active", True),
            )
            session.add(fee_item)
            session.flush()
            fee_item_map[item_data["id"]] = fee_item
        
        # Import stages
        stage_map = {}  # old_id -> new record
        for stage_data in import_data.get("stages", []):
            stage = Stage(
                feis_id=new_feis.id,
                name=stage_data["name"],
                color=stage_data.get("color"),
                sequence=stage_data["sequence"],
            )
            session.add(stage)
            session.flush()
            stage_map[stage_data["id"]] = stage
            report["created"]["stages"] += 1
        
        # Import/find users (parents, teachers)
        user_cache = {}  # email -> User
        def get_or_create_user(email: str, name: str, role: RoleType = RoleType.PARENT) -> Tuple[User, bool]:
            """Get existing user by email or create placeholder. Returns (user, was_created)."""
            if email in user_cache:
                return user_cache[email], False
            
            existing = session.exec(
                select(User).where(User.email == email)
            ).first()
            
            if existing:
                user_cache[email] = existing
                return existing, False
            
            # Create placeholder user with random password
            temp_password = secrets.token_urlsafe(16)
            new_user = User(
                email=email,
                name=name,
                password_hash=pwd_context.hash(temp_password),
                role=role,
                email_verified=False,
            )
            session.add(new_user)
            session.flush()
            user_cache[email] = new_user
            return new_user, True
        
        # Import dancers
        dancer_map = {}  # old_id -> new record
        for dancer_data in import_data.get("dancers", []):
            parent_email = dancer_data.get("parent_email")
            if not parent_email:
                report["skipped"]["dancers"] += 1
                continue
            
            parent, created = get_or_create_user(
                parent_email,
                dancer_data.get("parent_name", "Parent"),
                RoleType.PARENT
            )
            if created:
                report["created"]["users"] += 1
            else:
                report["linked"]["users"] += 1
            
            # Check if dancer already exists for this parent
            existing_dancer = session.exec(
                select(Dancer).where(
                    Dancer.parent_id == parent.id,
                    Dancer.name == dancer_data["name"],
                    Dancer.dob == date.fromisoformat(dancer_data["dob"])
                )
            ).first()
            
            if existing_dancer:
                dancer_map[dancer_data["id"]] = existing_dancer
                report["linked"]["dancers"] += 1
                continue
            
            # Get or create school
            school = None
            if dancer_data.get("school_email"):
                school, created = get_or_create_user(
                    dancer_data["school_email"],
                    "School",  # Will be updated if they have an account
                    RoleType.TEACHER
                )
                if created:
                    report["created"]["users"] += 1
            
            # Create new dancer
            dancer = Dancer(
                parent_id=parent.id,
                school_id=school.id if school else None,
                name=dancer_data["name"],
                dob=date.fromisoformat(dancer_data["dob"]),
                current_level=CompetitionLevel(dancer_data["current_level"]),
                gender=Gender(dancer_data["gender"]),
                clrg_number=dancer_data.get("clrg_number"),
                is_adult=dancer_data.get("is_adult", False),
                level_reel=CompetitionLevel(dancer_data["level_reel"]) if dancer_data.get("level_reel") else None,
                level_light_jig=CompetitionLevel(dancer_data["level_light_jig"]) if dancer_data.get("level_light_jig") else None,
                level_slip_jig=CompetitionLevel(dancer_data["level_slip_jig"]) if dancer_data.get("level_slip_jig") else None,
                level_single_jig=CompetitionLevel(dancer_data["level_single_jig"]) if dancer_data.get("level_single_jig") else None,
                level_treble_jig=CompetitionLevel(dancer_data["level_treble_jig"]) if dancer_data.get("level_treble_jig") else None,
                level_hornpipe=CompetitionLevel(dancer_data["level_hornpipe"]) if dancer_data.get("level_hornpipe") else None,
                level_traditional_set=CompetitionLevel(dancer_data["level_traditional_set"]) if dancer_data.get("level_traditional_set") else None,
                level_figure=CompetitionLevel(dancer_data["level_figure"]) if dancer_data.get("level_figure") else None,
            )
            session.add(dancer)
            session.flush()
            dancer_map[dancer_data["id"]] = dancer
            report["created"]["dancers"] += 1
        
        # Import competitions
        comp_map = {}  # old_id -> new record, also code -> new record
        comp_code_map = {}  # code -> new record
        for comp_data in import_data.get("competitions", []):
            stage = stage_map.get(comp_data.get("stage_id")) if comp_data.get("stage_id") else None
            
            competition = Competition(
                feis_id=new_feis.id,
                name=comp_data["name"],
                min_age=comp_data["min_age"],
                max_age=comp_data["max_age"],
                level=CompetitionLevel(comp_data["level"]),
                gender=Gender(comp_data["gender"]) if comp_data.get("gender") else None,
                code=comp_data.get("code"),
                category=CompetitionCategory(comp_data.get("category", "SOLO")),
                is_mixed=comp_data.get("is_mixed", False),
                description=comp_data.get("description"),
                allowed_levels=comp_data.get("allowed_levels"),
                dance_type=DanceType(comp_data["dance_type"]) if comp_data.get("dance_type") else None,
                tempo_bpm=comp_data.get("tempo_bpm"),
                bars=comp_data.get("bars", 48),
                scoring_method=ScoringMethod(comp_data.get("scoring_method", "SOLO")),
                price_cents=comp_data.get("price_cents", 1000),
                max_entries=comp_data.get("max_entries"),
                fee_category=FeeCategory(comp_data.get("fee_category", "QUALIFYING")),
                stage_id=stage.id if stage else None,
                scheduled_time=datetime.fromisoformat(comp_data["scheduled_time"]) if comp_data.get("scheduled_time") else None,
                estimated_duration_minutes=comp_data.get("estimated_duration_minutes"),
            )
            session.add(competition)
            session.flush()
            comp_map[comp_data["id"]] = competition
            if comp_data.get("code"):
                comp_code_map[comp_data["code"]] = competition
            report["created"]["competitions"] += 1
        
        # Import adjudicators
        adj_map = {}  # old_id -> new record, also name+email -> new record
        adj_lookup = {}  # (name, email) -> new record
        for adj_data in import_data.get("adjudicators", []):
            email = adj_data.get("user_email") or adj_data.get("email")
            
            # Try to find existing user
            user = None
            if email:
                user = session.exec(
                    select(User).where(User.email == email)
                ).first()
                if user:
                    report["linked"]["adjudicators"] += 1
            
            # Get school affiliation if provided
            school_affiliation = None
            if adj_data.get("school_affiliation_email"):
                school, created = get_or_create_user(
                    adj_data["school_affiliation_email"],
                    "School",
                    RoleType.TEACHER
                )
                school_affiliation = school
                if created:
                    report["created"]["users"] += 1
            
            # Create adjudicator roster entry
            feis_adj = FeisAdjudicator(
                feis_id=new_feis.id,
                user_id=user.id if user else None,
                name=adj_data["name"],
                email=email,
                phone=adj_data.get("phone"),
                credential=adj_data.get("credential"),
                organization=adj_data.get("organization"),
                school_affiliation_id=school_affiliation.id if school_affiliation else None,
                status=AdjudicatorStatus(adj_data.get("status", "INVITED")),
                created_at=datetime.fromisoformat(adj_data["created_at"]) if adj_data.get("created_at") else datetime.utcnow(),
                confirmed_at=datetime.fromisoformat(adj_data["confirmed_at"]) if adj_data.get("confirmed_at") else None,
            )
            session.add(feis_adj)
            session.flush()
            adj_map[adj_data["id"]] = feis_adj
            adj_lookup[(adj_data["name"], email)] = feis_adj
            report["created"]["adjudicators"] += 1
        
        # Import panels
        panel_map = {}  # old_id -> new record
        panel_name_map = {}  # name -> new record
        for panel_data in import_data.get("panels", []):
            panel = JudgePanel(
                feis_id=new_feis.id,
                name=panel_data["name"],
                description=panel_data.get("description"),
                created_at=datetime.fromisoformat(panel_data["created_at"]) if panel_data.get("created_at") else datetime.utcnow(),
            )
            session.add(panel)
            session.flush()
            
            # Add panel members
            for member_data in panel_data.get("members", []):
                adj_key = (member_data["adjudicator_name"], member_data.get("adjudicator_email"))
                feis_adj = adj_lookup.get(adj_key)
                if feis_adj:
                    panel_member = PanelMember(
                        panel_id=panel.id,
                        feis_adjudicator_id=feis_adj.id,
                        sequence=member_data.get("sequence", 0),
                    )
                    session.add(panel_member)
            
            panel_map[panel_data["id"]] = panel
            panel_name_map[panel_data["name"]] = panel
            report["created"]["panels"] += 1
        
        session.flush()
        
        # Import stage coverage
        for cov_data in import_data.get("stage_coverage", []):
            stage_name = cov_data.get("stage_name")
            stage = next((s for s in stage_map.values() if s.name == stage_name), None)
            if not stage:
                continue
            
            # Find adjudicator or panel
            feis_adj = None
            panel = None
            if cov_data.get("adjudicator_name") and cov_data.get("adjudicator_email"):
                adj_key = (cov_data["adjudicator_name"], cov_data["adjudicator_email"])
                feis_adj = adj_lookup.get(adj_key)
            
            if cov_data.get("panel_name"):
                panel = panel_name_map.get(cov_data["panel_name"])
            
            coverage = StageJudgeCoverage(
                stage_id=stage.id,
                feis_adjudicator_id=feis_adj.id if feis_adj else None,
                panel_id=panel.id if panel else None,
                feis_day=date.fromisoformat(cov_data["feis_day"]),
                start_time=time.fromisoformat(cov_data["start_time"]),
                end_time=time.fromisoformat(cov_data["end_time"]),
                note=cov_data.get("note"),
            )
            session.add(coverage)
        
        # Import co-organizers
        for co_org_data in import_data.get("co_organizers", []):
            user_email = co_org_data.get("user_email")
            if not user_email:
                continue
            
            user, created = get_or_create_user(
                user_email,
                co_org_data.get("user_name", "Co-Organizer"),
                RoleType.ORGANIZER
            )
            if created:
                report["created"]["users"] += 1
            
            co_org = FeisOrganizer(
                feis_id=new_feis.id,
                user_id=user.id,
                role=co_org_data.get("role", "co_organizer"),
                can_edit_feis=co_org_data.get("can_edit_feis", False),
                can_manage_entries=co_org_data.get("can_manage_entries", False),
                can_manage_schedule=co_org_data.get("can_manage_schedule", False),
                can_manage_adjudicators=co_org_data.get("can_manage_adjudicators", False),
                can_add_organizers=co_org_data.get("can_add_organizers", False),
                added_by=importing_user.id,
                added_at=datetime.fromisoformat(co_org_data["added_at"]) if co_org_data.get("added_at") else datetime.utcnow(),
            )
            session.add(co_org)
        
        # Import entries
        entry_map = {}  # old_id -> new record
        for entry_data in import_data.get("entries", []):
            # Find dancer
            parent_email = entry_data.get("dancer_parent_email")
            dancer_name = entry_data.get("dancer_name")
            if not parent_email or not dancer_name:
                continue
            
            # Try to match dancer
            dancer = None
            for old_id, d in dancer_map.items():
                if d.name == dancer_name and d.parent.email == parent_email:
                    dancer = d
                    break
            
            if not dancer:
                continue
            
            # Find competition by code or name
            comp_code = entry_data.get("competition_code")
            comp_name = entry_data.get("competition_name")
            comp = comp_code_map.get(comp_code) if comp_code else None
            if not comp and comp_name:
                comp = next((c for c in comp_map.values() if c.name == comp_name), None)
            
            if not comp:
                continue
            
            entry = Entry(
                dancer_id=dancer.id,
                competition_id=comp.id,
                competitor_number=entry_data.get("competitor_number"),
                paid=entry_data.get("paid", False),
                pay_later=entry_data.get("pay_later", False),
                check_in_status=CheckInStatus(entry_data.get("check_in_status", "NOT_CHECKED_IN")),
                checked_in_at=datetime.fromisoformat(entry_data["checked_in_at"]) if entry_data.get("checked_in_at") else None,
                cancelled=entry_data.get("cancelled", False),
                cancelled_at=datetime.fromisoformat(entry_data["cancelled_at"]) if entry_data.get("cancelled_at") else None,
                cancellation_reason=entry_data.get("cancellation_reason"),
                refund_amount_cents=entry_data.get("refund_amount_cents", 0),
            )
            session.add(entry)
            session.flush()
            entry_map[entry_data["id"]] = entry
            report["created"]["entries"] += 1
        
        # Import orders (if requested)
        if include_orders:
            for order_data in import_data.get("orders", []):
                user_email = order_data.get("user_email")
                if not user_email:
                    continue
                
                user, created = get_or_create_user(user_email, "Parent", RoleType.PARENT)
                if created:
                    report["created"]["users"] += 1
                
                order = Order(
                    feis_id=new_feis.id,
                    user_id=user.id,
                    subtotal_cents=order_data.get("subtotal_cents", 0),
                    qualifying_subtotal_cents=order_data.get("qualifying_subtotal_cents", 0),
                    non_qualifying_subtotal_cents=order_data.get("non_qualifying_subtotal_cents", 0),
                    family_discount_cents=order_data.get("family_discount_cents", 0),
                    late_fee_cents=order_data.get("late_fee_cents", 0),
                    total_cents=order_data.get("total_cents", 0),
                    status=PaymentStatus(order_data.get("status", "PENDING")),
                    refund_total_cents=order_data.get("refund_total_cents", 0),
                    refunded_at=datetime.fromisoformat(order_data["refunded_at"]) if order_data.get("refunded_at") else None,
                    refund_reason=order_data.get("refund_reason"),
                    created_at=datetime.fromisoformat(order_data["created_at"]) if order_data.get("created_at") else datetime.utcnow(),
                    paid_at=datetime.fromisoformat(order_data["paid_at"]) if order_data.get("paid_at") else None,
                )
                session.add(order)
                session.flush()
                
                # Add order items
                for item_data in order_data.get("items", []):
                    # Try to match fee item by name
                    fee_item = next(
                        (fi for fi in fee_item_map.values() if fi.name == item_data.get("fee_item_name")),
                        None
                    )
                    if fee_item:
                        order_item = OrderItem(
                            order_id=order.id,
                            fee_item_id=fee_item.id,
                            quantity=item_data.get("quantity", 1),
                            unit_price_cents=item_data.get("unit_price_cents", 0),
                            total_cents=item_data.get("total_cents", 0),
                        )
                        session.add(order_item)
                
                report["created"]["orders"] += 1
        
        # Import rounds and scores
        for round_data in import_data.get("rounds", []):
            comp_code = round_data.get("competition_code")
            comp = comp_code_map.get(comp_code)
            if not comp:
                continue
            
            round_obj = Round(
                id=round_data["id"],
                competition_id=comp.id,
                name=round_data["name"],
                sequence=round_data["sequence"],
            )
            session.add(round_obj)
        
        session.flush()
        
        for score_data in import_data.get("scores", []):
            score = JudgeScore(
                judge_id=score_data["judge_id"],
                competitor_id=score_data["competitor_id"],
                round_id=score_data["round_id"],
                value=score_data["value"],
                notes=score_data.get("notes"),
                timestamp=datetime.fromisoformat(score_data["timestamp"]) if score_data.get("timestamp") else datetime.utcnow(),
            )
            session.add(score)
        
        session.commit()
        
    except Exception as e:
        report["success"] = False
        report["errors"].append(str(e))
        session.rollback()
    
    return report

