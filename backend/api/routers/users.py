from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from uuid import UUID
from sqlmodel import Session, select, func
from backend.scoring_engine.models_platform import User, Dancer, Entry, RoleType
from backend.db.database import get_session
from backend.api.schemas import (
    UserUpdate, UserResponse,
    DancerCreate, DancerUpdate, DancerResponse
)
from backend.api.auth import (
    get_current_user,
    require_organizer_or_admin,
    require_admin
)

router = APIRouter()

# ============= User Management Endpoints =============

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    session: Session = Depends(get_session),
    role: Optional[RoleType] = None,
    search: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(require_organizer_or_admin())
):
    """
    List users with optional filters.
    
    - role: Filter by role (teacher, organizer, etc.)
    - search: Search by email or name (partial match)
    - limit: Maximum number of results (default 50)
    """
    statement = select(User)
    
    if role:
        statement = statement.where(User.role == role)
    
    if search:
        search_lower = f"%{search.lower()}%"
        statement = statement.where(
            (func.lower(User.email).like(search_lower)) |
            (func.lower(User.name).like(search_lower))
        )
    
    statement = statement.limit(limit)
    users = session.exec(statement).all()
    
    return [
        UserResponse(
            id=str(u.id),
            email=u.email,
            name=u.name,
            role=u.role,
            email_verified=u.email_verified
        )
        for u in users
    ]


@router.get("/teachers", response_model=List[UserResponse])
async def list_teachers(
    session: Session = Depends(get_session),
    search: Optional[str] = None
):
    """
    List all teachers (for school selection dropdown).
    
    Returns users with role=teacher, searchable by name.
    """
    statement = select(User).where(User.role == RoleType.TEACHER)
    
    if search:
        search_lower = f"%{search.lower()}%"
        statement = statement.where(func.lower(User.name).like(search_lower))
    
    teachers = session.exec(statement.order_by(User.name)).all()
    
    return [
        UserResponse(
            id=str(u.id),
            email=u.email,
            name=u.name,
            role=u.role,
            email_verified=u.email_verified
        )
        for u in teachers
    ]

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str, 
    user_data: UserUpdate, 
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin())
):
    """Update a user's name or role. Requires super_admin role."""
    user = session.get(User, UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_data.name is not None:
        user.name = user_data.name
    if user_data.role is not None:
        user.role = user_data.role
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        email_verified=user.email_verified
    )


# ============= Dancer Endpoints =============

@router.get("/dancers", response_model=List[DancerResponse])
async def list_dancers(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """List all dancers."""
    dancers = session.exec(select(Dancer)).all()
    return [
        DancerResponse(
            id=str(d.id),
            name=d.name,
            dob=d.dob,
            current_level=d.current_level,
            gender=d.gender,
            clrg_number=d.clrg_number,
            parent_id=str(d.parent_id),
            school_id=str(d.school_id) if d.school_id else None
        )
        for d in dancers
    ]


@router.get("/dancers/mine", response_model=List[DancerResponse])
async def list_my_dancers(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """List dancers belonging to the current logged-in parent."""
    dancers = session.exec(
        select(Dancer).where(Dancer.parent_id == current_user.id)
    ).all()
    return [
        DancerResponse(
            id=str(d.id),
            name=d.name,
            dob=d.dob,
            current_level=d.current_level,
            gender=d.gender,
            clrg_number=d.clrg_number,
            parent_id=str(d.parent_id),
            school_id=str(d.school_id) if d.school_id else None,
            level_reel=d.level_reel,
            level_light_jig=d.level_light_jig,
            level_slip_jig=d.level_slip_jig,
            level_single_jig=d.level_single_jig,
            level_treble_jig=d.level_treble_jig,
            level_hornpipe=d.level_hornpipe,
            level_traditional_set=d.level_traditional_set,
            level_figure=d.level_figure,
            is_adult=d.is_adult
        )
        for d in dancers
    ]


@router.post("/dancers", response_model=DancerResponse)
async def create_dancer(
    dancer_data: DancerCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new dancer profile. The dancer is automatically linked to the 
    current logged-in user as the parent.
    """
    dancer = Dancer(
        parent_id=current_user.id,
        name=dancer_data.name,
        dob=dancer_data.dob,
        gender=dancer_data.gender,
        current_level=dancer_data.current_level,
        clrg_number=dancer_data.clrg_number,
        school_id=UUID(dancer_data.school_id) if dancer_data.school_id else None,
        # Per-dance levels
        level_reel=dancer_data.level_reel,
        level_light_jig=dancer_data.level_light_jig,
        level_slip_jig=dancer_data.level_slip_jig,
        level_single_jig=dancer_data.level_single_jig,
        level_treble_jig=dancer_data.level_treble_jig,
        level_hornpipe=dancer_data.level_hornpipe,
        level_traditional_set=dancer_data.level_traditional_set,
        level_figure=dancer_data.level_figure,
        is_adult=dancer_data.is_adult
    )
    session.add(dancer)
    session.commit()
    session.refresh(dancer)
    
    return DancerResponse(
        id=str(dancer.id),
        name=dancer.name,
        dob=dancer.dob,
        current_level=dancer.current_level,
        gender=dancer.gender,
        clrg_number=dancer.clrg_number,
        parent_id=str(dancer.parent_id),
        school_id=str(dancer.school_id) if dancer.school_id else None,
        level_reel=dancer.level_reel,
        level_light_jig=dancer.level_light_jig,
        level_slip_jig=dancer.level_slip_jig,
        level_single_jig=dancer.level_single_jig,
        level_treble_jig=dancer.level_treble_jig,
        level_hornpipe=dancer.level_hornpipe,
        level_traditional_set=dancer.level_traditional_set,
        level_figure=dancer.level_figure,
        is_adult=dancer.is_adult
    )


@router.put("/dancers/{dancer_id}", response_model=DancerResponse)
async def update_dancer(
    dancer_id: str,
    dancer_data: DancerUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Update a dancer profile. Parents can only update their own dancers.
    """
    dancer = session.get(Dancer, UUID(dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    # Parents can only update their own dancers
    if current_user.role == RoleType.PARENT and dancer.parent_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only update your own dancers")
    
    # Apply updates
    if dancer_data.name is not None:
        dancer.name = dancer_data.name
    if dancer_data.dob is not None:
        dancer.dob = dancer_data.dob
    if dancer_data.gender is not None:
        dancer.gender = dancer_data.gender
    if dancer_data.current_level is not None:
        dancer.current_level = dancer_data.current_level
    if dancer_data.clrg_number is not None:
        dancer.clrg_number = dancer_data.clrg_number
    if dancer_data.school_id is not None:
        dancer.school_id = UUID(dancer_data.school_id) if dancer_data.school_id else None
    # Per-dance levels
    if dancer_data.level_reel is not None:
        dancer.level_reel = dancer_data.level_reel
    if dancer_data.level_light_jig is not None:
        dancer.level_light_jig = dancer_data.level_light_jig
    if dancer_data.level_slip_jig is not None:
        dancer.level_slip_jig = dancer_data.level_slip_jig
    if dancer_data.level_single_jig is not None:
        dancer.level_single_jig = dancer_data.level_single_jig
    if dancer_data.level_treble_jig is not None:
        dancer.level_treble_jig = dancer_data.level_treble_jig
    if dancer_data.level_hornpipe is not None:
        dancer.level_hornpipe = dancer_data.level_hornpipe
    if dancer_data.level_traditional_set is not None:
        dancer.level_traditional_set = dancer_data.level_traditional_set
    if dancer_data.level_figure is not None:
        dancer.level_figure = dancer_data.level_figure
    if dancer_data.is_adult is not None:
        dancer.is_adult = dancer_data.is_adult
    
    session.add(dancer)
    session.commit()
    session.refresh(dancer)
    
    return DancerResponse(
        id=str(dancer.id),
        name=dancer.name,
        dob=dancer.dob,
        current_level=dancer.current_level,
        gender=dancer.gender,
        clrg_number=dancer.clrg_number,
        parent_id=str(dancer.parent_id),
        school_id=str(dancer.school_id) if dancer.school_id else None,
        level_reel=dancer.level_reel,
        level_light_jig=dancer.level_light_jig,
        level_slip_jig=dancer.level_slip_jig,
        level_single_jig=dancer.level_single_jig,
        level_treble_jig=dancer.level_treble_jig,
        level_hornpipe=dancer.level_hornpipe,
        level_traditional_set=dancer.level_traditional_set,
        level_figure=dancer.level_figure,
        is_adult=dancer.is_adult
    )


@router.delete("/dancers/{dancer_id}")
async def delete_dancer(
    dancer_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a dancer profile. Parents can only delete their own dancers.
    Will fail if the dancer has any existing entries.
    """
    dancer = session.get(Dancer, UUID(dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    # Parents can only delete their own dancers
    if current_user.role == RoleType.PARENT and dancer.parent_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own dancers")
    
    # Check if dancer has any entries
    entry_count = session.exec(
        select(func.count(Entry.id)).where(Entry.dancer_id == dancer.id)
    ).one()
    
    if entry_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete dancer with {entry_count} existing registration(s). Please delete entries first."
        )
    
    session.delete(dancer)
    session.commit()
    
    return {"message": f"Dancer '{dancer.name}' deleted successfully"}
