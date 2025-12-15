from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from uuid import UUID
from sqlmodel import Session, select, func
from backend.db.database import get_session
from backend.api.auth import get_current_user
from backend.scoring_engine.models_platform import User, Dancer, Feis, Competition, WaitlistEntry, WaitlistStatus
from backend.api.schemas import WaitlistEntryResponse, WaitlistAddRequest, WaitlistStatusResponse
from backend.services.waitlist import add_to_waitlist, get_user_waitlist_entries, accept_waitlist_offer, cancel_waitlist_entry

router = APIRouter()

@router.post("/waitlist/add", response_model=WaitlistEntryResponse)
async def add_to_waitlist_endpoint(
    request: WaitlistAddRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Add a dancer to the waitlist."""
    # Verify dancer belongs to user
    dancer = session.get(Dancer, UUID(request.dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    if dancer.parent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this dancer")
    
    feis = session.get(Feis, UUID(request.feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    comp_id = UUID(request.competition_id) if request.competition_id else None
    comp = session.get(Competition, comp_id) if comp_id else None
    
    entry = add_to_waitlist(
        session,
        UUID(request.feis_id),
        UUID(request.dancer_id),
        current_user.id,
        comp_id
    )
    
    return WaitlistEntryResponse(
        id=str(entry.id),
        feis_id=str(entry.feis_id),
        feis_name=feis.name,
        dancer_id=str(entry.dancer_id),
        dancer_name=dancer.name,
        competition_id=str(entry.competition_id) if entry.competition_id else None,
        competition_name=comp.name if comp else None,
        position=entry.position,
        status=entry.status,
        offer_sent_at=entry.offer_sent_at,
        offer_expires_at=entry.offer_expires_at,
        created_at=entry.created_at
    )


@router.get("/waitlist/mine", response_model=List[WaitlistEntryResponse])
async def get_my_waitlist_entries(
    feis_id: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get waitlist entries for current user's dancers."""
    feis_uuid = UUID(feis_id) if feis_id else None
    entries = get_user_waitlist_entries(session, current_user.id, feis_uuid)
    
    results = []
    for entry in entries:
        dancer = session.get(Dancer, entry.dancer_id)
        feis = session.get(Feis, entry.feis_id)
        comp = session.get(Competition, entry.competition_id) if entry.competition_id else None
        
        results.append(WaitlistEntryResponse(
            id=str(entry.id),
            feis_id=str(entry.feis_id),
            feis_name=feis.name if feis else "Unknown",
            dancer_id=str(entry.dancer_id),
            dancer_name=dancer.name if dancer else "Unknown",
            competition_id=str(entry.competition_id) if entry.competition_id else None,
            competition_name=comp.name if comp else None,
            position=entry.position,
            status=entry.status,
            offer_sent_at=entry.offer_sent_at,
            offer_expires_at=entry.offer_expires_at,
            created_at=entry.created_at
        ))
    
    return results


@router.post("/waitlist/{waitlist_id}/accept")
async def accept_waitlist(
    waitlist_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Accept a waitlist offer."""
    success, message, entry = accept_waitlist_offer(
        session, UUID(waitlist_id), current_user.id
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {
        "success": True,
        "message": message,
        "entry_id": str(entry.id) if entry else None
    }


@router.post("/waitlist/{waitlist_id}/cancel")
async def cancel_waitlist(
    waitlist_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Cancel a waitlist entry."""
    success, message = cancel_waitlist_entry(session, UUID(waitlist_id), current_user.id)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}
