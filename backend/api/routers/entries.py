from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional
from uuid import UUID
from datetime import date, datetime
from sqlmodel import Session, select, func
from backend.db.database import get_session
from backend.api.auth import get_current_user, require_organizer_or_admin, require_teacher
from backend.scoring_engine.models_platform import User, Entry, Dancer, Competition, Feis, RoleType, EntryFlag
from backend.api.schemas import (
    EntryCreate, EntryUpdate, EntryResponse,
    BulkEntryCreate, BulkEntryResponse,
    EntryFlagCreate, EntryFlagResponse, FlaggedEntriesResponse, ResolveFlagRequest,
    ScratchEntryRequest, ScratchEntryResponse
)
from backend.services.number_cards import NumberCardData, generate_single_card_pdf
from backend.services.refund import scratch_entry

router = APIRouter()

def calculate_competition_age(dob: date, feis_date: date) -> int:
    """Calculate competition age."""
    age = feis_date.year - dob.year
    if (feis_date.month, feis_date.day) < (dob.month, dob.day):
        age -= 1
    return age

def get_school_name(session: Session, school_id: UUID) -> Optional[str]:
    """Get school name from teacher ID."""
    if not school_id:
        return None
    teacher = session.get(User, school_id)
    return teacher.name if teacher else None

@router.post("/entries", response_model=EntryResponse)
async def create_entry(
    entry_data: EntryCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Create a single entry (register dancer for competition)."""
    dancer = session.get(Dancer, UUID(entry_data.dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    # Parents can only register their own dancers
    if current_user.role == RoleType.PARENT and dancer.parent_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only register your own dancers")
    
    competition = session.get(Competition, UUID(entry_data.competition_id))
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    # Check for duplicate entry
    existing = session.exec(
        select(Entry)
        .where(Entry.dancer_id == dancer.id)
        .where(Entry.competition_id == competition.id)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Dancer is already registered for this competition")
    
    entry = Entry(
        dancer_id=dancer.id,
        competition_id=competition.id,
        paid=False,
        pay_later=entry_data.pay_later
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    
    return EntryResponse(
        id=str(entry.id),
        dancer_id=str(entry.dancer_id),
        dancer_name=dancer.name,
        dancer_school=get_school_name(session, dancer.school_id),
        competition_id=str(entry.competition_id),
        competition_name=competition.name,
        competitor_number=entry.competitor_number,
        paid=entry.paid,
        pay_later=entry.pay_later
    )


@router.post("/entries/batch", response_model=BulkEntryResponse)
async def create_bulk_entries(
    entry_data: BulkEntryCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Create multiple entries at once (bulk registration)."""
    dancer = session.get(Dancer, UUID(entry_data.dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    # Parents can only register their own dancers
    if current_user.role == RoleType.PARENT and dancer.parent_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only register your own dancers")
    
    created_entries = []
    for comp_id_str in entry_data.competition_ids:
        competition = session.get(Competition, UUID(comp_id_str))
        if not competition:
            continue
        
        # Check for duplicate
        existing = session.exec(
            select(Entry)
            .where(Entry.dancer_id == dancer.id)
            .where(Entry.competition_id == competition.id)
        ).first()
        if existing:
            continue
        
        entry = Entry(
            dancer_id=dancer.id,
            competition_id=competition.id,
            paid=False,
            pay_later=entry_data.pay_later
        )
        session.add(entry)
        created_entries.append((entry, competition))
    
    session.commit()
    
    entry_responses = []
    for entry, competition in created_entries:
        session.refresh(entry)
        entry_responses.append(EntryResponse(
            id=str(entry.id),
            dancer_id=str(entry.dancer_id),
            dancer_name=dancer.name,
            dancer_school=get_school_name(session, dancer.school_id),
            competition_id=str(entry.competition_id),
            competition_name=competition.name,
            competitor_number=entry.competitor_number,
            paid=entry.paid,
            pay_later=entry.pay_later
        ))
    
    return BulkEntryResponse(
        created_count=len(entry_responses),
        entries=entry_responses,
        message=f"Successfully registered for {len(entry_responses)} competitions"
    )


@router.get("/entries", response_model=List[EntryResponse])
async def list_entries(
    feis_id: Optional[str] = None,
    dancer_id: Optional[str] = None,
    competition_id: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """List entries with optional filters."""
    statement = select(Entry)
    
    if competition_id:
        statement = statement.where(Entry.competition_id == UUID(competition_id))
    elif feis_id:
        # Filter by feis requires join
        statement = statement.join(Competition).where(Competition.feis_id == UUID(feis_id))
    
    if dancer_id:
        statement = statement.where(Entry.dancer_id == UUID(dancer_id))
    
    entries = session.exec(statement).all()
    
    result = []
    for entry in entries:
        dancer = session.get(Dancer, entry.dancer_id)
        competition = session.get(Competition, entry.competition_id)
        if dancer and competition:
            result.append(EntryResponse(
                id=str(entry.id),
                dancer_id=str(entry.dancer_id),
                dancer_name=dancer.name,
                dancer_school=get_school_name(session, dancer.school_id),
                competition_id=str(entry.competition_id),
                competition_name=competition.name,
                competitor_number=entry.competitor_number,
                paid=entry.paid,
                pay_later=entry.pay_later
            ))
    
    return result


@router.put("/entries/{entry_id}", response_model=EntryResponse)
async def update_entry(
    entry_id: str,
    entry_data: EntryUpdate,
    session: Session = Depends(get_session)
):
    """Update an entry (assign number, mark paid)."""
    entry = session.get(Entry, UUID(entry_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    if entry_data.competitor_number is not None:
        entry.competitor_number = entry_data.competitor_number
    if entry_data.paid is not None:
        entry.paid = entry_data.paid
    
    session.add(entry)
    session.commit()
    session.refresh(entry)
    
    dancer = session.get(Dancer, entry.dancer_id)
    competition = session.get(Competition, entry.competition_id)
    
    return EntryResponse(
        id=str(entry.id),
        dancer_id=str(entry.dancer_id),
        dancer_name=dancer.name if dancer else "Unknown",
        dancer_school=get_school_name(session, dancer.school_id) if dancer else None,
        competition_id=str(entry.competition_id),
        competition_name=competition.name if competition else "Unknown",
        competitor_number=entry.competitor_number,
        paid=entry.paid,
        pay_later=entry.pay_later
    )


@router.delete("/entries/{entry_id}")
async def delete_entry(
    entry_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Delete an entry (cancel registration)."""
    entry = session.get(Entry, UUID(entry_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    dancer = session.get(Dancer, entry.dancer_id)
    
    # Parents can only delete their own dancers' entries
    if current_user.role == RoleType.PARENT and dancer and dancer.parent_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete entries for your own dancers")
    
    session.delete(entry)
    session.commit()
    
    return {"message": "Entry deleted successfully"}


@router.get("/entries/{entry_id}/number-card")
async def generate_single_number_card(
    entry_id: str,
    session: Session = Depends(get_session),
    base_url: str = Query("https://openfeis.com"),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Generate a PDF with a single number card (for reprints)."""
    entry = session.get(Entry, UUID(entry_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    if entry.competitor_number is None:
        raise HTTPException(status_code=400, detail="Entry does not have a competitor number")
    
    dancer = session.get(Dancer, entry.dancer_id)
    competition = session.get(Competition, entry.competition_id)
    feis = session.get(Feis, competition.feis_id) if competition else None
    
    if not dancer or not competition or not feis:
        raise HTTPException(status_code=404, detail="Associated records not found")
    
    # Get all entries for this dancer in this feis
    all_feis_competitions = session.exec(
        select(Competition).where(Competition.feis_id == feis.id)
    ).all()
    comp_ids = [c.id for c in all_feis_competitions]
    
    dancer_entries = session.exec(
        select(Entry)
        .where(Entry.dancer_id == dancer.id)
        .where(Entry.competition_id.in_(comp_ids))
    ).all()
    
    comp_map = {c.id: c for c in all_feis_competitions}
    competition_codes = []
    for e in dancer_entries:
        comp = comp_map.get(e.competition_id)
        if comp:
            competition_codes.append(comp.name[:20])
    
    comp_age = calculate_competition_age(dancer.dob, feis.date)
    
    card = NumberCardData(
        dancer_id=str(dancer.id),
        dancer_name=dancer.name,
        school_name=get_school_name(session, dancer.school_id),
        competitor_number=entry.competitor_number,
        age_group=f"U{comp_age}",
        level=dancer.current_level.value.title(),
        competition_codes=competition_codes,
        feis_name=feis.name,
        feis_date=feis.date
    )
    
    pdf_buffer = generate_single_card_pdf(card, base_url=base_url)
    
    safe_name = "".join(c for c in dancer.name if c.isalnum() or c in " -_").strip()
    filename = f"NumberCard_{entry.competitor_number}_{safe_name}.pdf"
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/me/entries", response_model=List[EntryResponse])
async def get_my_entries(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get all entries for current user's dancers."""
    dancers = session.exec(
        select(Dancer).where(Dancer.parent_id == current_user.id)
    ).all()
    
    if not dancers:
        return []
    
    dancer_ids = [d.id for d in dancers]
    dancer_map = {d.id: d for d in dancers}
    
    entries = session.exec(
        select(Entry).where(Entry.dancer_id.in_(dancer_ids))
    ).all()
    
    result = []
    for entry in entries:
        dancer = dancer_map.get(entry.dancer_id)
        competition = session.get(Competition, entry.competition_id)
        if dancer and competition:
            result.append(EntryResponse(
                id=str(entry.id),
                dancer_id=str(entry.dancer_id),
                dancer_name=dancer.name,
                dancer_school=get_school_name(session, dancer.school_id),
                competition_id=str(entry.competition_id),
                competition_name=competition.name,
                competitor_number=entry.competitor_number,
                paid=entry.paid,
                pay_later=entry.pay_later
            ))
    
    return result


# ============= Flag Routes =============

@router.post("/entries/{entry_id}/flag", response_model=EntryFlagResponse)
async def flag_entry(
    entry_id: str,
    flag_data: EntryFlagCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_teacher())
):
    """
    Flag an entry for organizer review.
    
    Teachers can flag entries they believe are incorrect.
    """
    entry = session.get(Entry, UUID(entry_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Check if already flagged
    existing = session.exec(
        select(EntryFlag)
        .where(EntryFlag.entry_id == entry.id)
        .where(EntryFlag.resolved == False)
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Entry already has an unresolved flag")
    
    # Create flag
    flag = EntryFlag(
        entry_id=entry.id,
        flagged_by=current_user.id,
        reason=flag_data.reason,
        flag_type=flag_data.flag_type
    )
    
    session.add(flag)
    session.commit()
    session.refresh(flag)
    
    dancer = session.get(Dancer, entry.dancer_id)
    competition = session.get(Competition, entry.competition_id)
    
    return EntryFlagResponse(
        id=str(flag.id),
        entry_id=str(flag.entry_id),
        dancer_name=dancer.name if dancer else "Unknown",
        competition_name=competition.name if competition else "Unknown",
        flagged_by=str(flag.flagged_by),
        flagged_by_name=current_user.name,
        reason=flag.reason,
        flag_type=flag.flag_type,
        resolved=flag.resolved,
        resolved_by=str(flag.resolved_by) if flag.resolved_by else None,
        resolved_by_name=None,
        resolved_at=flag.resolved_at,
        resolution_note=flag.resolution_note,
        created_at=flag.created_at
    )


@router.post("/flags/{flag_id}/resolve")
async def resolve_flag(
    flag_id: str,
    resolve_data: ResolveFlagRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Resolve a flagged entry."""
    flag = session.get(EntryFlag, UUID(flag_id))
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    
    flag.resolved = True
    flag.resolved_by = current_user.id
    flag.resolved_at = datetime.utcnow()
    flag.resolution_note = resolve_data.resolution_note
    
    session.add(flag)
    session.commit()
    
    return {"success": True, "message": "Flag resolved"}


@router.post("/entries/{entry_id}/scratch", response_model=ScratchEntryResponse)
async def scratch_entry_endpoint(
    entry_id: str,
    request: ScratchEntryRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Scratch (cancel) an entry with refund processing."""
    entry = session.get(Entry, UUID(entry_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Verify user owns this entry (or is admin/organizer)
    dancer = session.get(Dancer, entry.dancer_id)
    competition = session.get(Competition, entry.competition_id)
    feis = session.get(Feis, competition.feis_id) if competition else None
    
    is_owner = dancer and dancer.parent_id == current_user.id
    is_admin = current_user.role in [RoleType.SUPER_ADMIN, RoleType.ORGANIZER]
    is_feis_owner = feis and feis.organizer_id == current_user.id
    
    if not (is_owner or is_admin or is_feis_owner):
        raise HTTPException(status_code=403, detail="Not authorized to scratch this entry")
    
    result = scratch_entry(session, UUID(entry_id), current_user.id, request.reason)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    
    return ScratchEntryResponse(
        entry_id=result.entry_id,
        dancer_name=result.dancer_name,
        competition_name=result.competition_name,
        refund_amount_cents=result.refund_amount_cents,
        message=result.message
    )
