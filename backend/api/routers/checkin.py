from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import List
from uuid import UUID
from sqlmodel import Session, select, func
from backend.db.database import get_session
from backend.api.auth import get_current_user, require_organizer_or_admin
from backend.scoring_engine.models_platform import User, Entry, Dancer, Competition, CheckInStatus
from backend.api.schemas import CheckInRequest, CheckInResponse, BulkCheckInRequest, BulkCheckInResponse, StageMonitorResponse, StageMonitorEntry
from backend.services.checkin import check_in_entry, undo_check_in
import qrcode
import io

router = APIRouter()

@router.post("/checkin", response_model=CheckInResponse)
async def check_in_dancer(
    request: CheckInRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Check in a dancer for their competition."""
    success, message, entry = check_in_entry(session, UUID(request.entry_id))
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    dancer = session.get(Dancer, entry.dancer_id)
    comp = session.get(Competition, entry.competition_id)
    
    return CheckInResponse(
        entry_id=str(entry.id),
        dancer_name=dancer.name if dancer else "Unknown",
        competitor_number=entry.competitor_number,
        competition_name=comp.name if comp else "Unknown",
        status=entry.check_in_status,
        checked_in_at=entry.checked_in_at,
        message=message
    )


@router.post("/checkin/by-number", response_model=CheckInResponse)
async def check_in_by_number(
    feis_id: str,
    competitor_number: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Check in a dancer by their competitor number."""
    entry = session.exec(
        select(Entry)
        .join(Competition)
        .where(Competition.feis_id == UUID(feis_id))
        .where(Entry.competitor_number == competitor_number)
    ).first()
    
    if not entry:
        raise HTTPException(status_code=404, detail=f"No entry found with number {competitor_number}")
    
    success, message, entry = check_in_entry(session, entry.id)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    dancer = session.get(Dancer, entry.dancer_id)
    comp = session.get(Competition, entry.competition_id)
    
    return CheckInResponse(
        entry_id=str(entry.id),
        dancer_name=dancer.name if dancer else "Unknown",
        competitor_number=entry.competitor_number,
        competition_name=comp.name if comp else "Unknown",
        status=entry.check_in_status,
        checked_in_at=entry.checked_in_at,
        message=message
    )


@router.post("/checkin/bulk", response_model=BulkCheckInResponse)
async def bulk_check_in(
    request: BulkCheckInRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Check in multiple dancers at once."""
    results = []
    successful = 0
    failed = 0
    
    for entry_id_str in request.entry_ids:
        success, message, entry = check_in_entry(session, UUID(entry_id_str))
        
        if success:
            successful += 1
        else:
            failed += 1
        
        dancer = session.get(Dancer, entry.dancer_id) if entry else None
        comp = session.get(Competition, entry.competition_id) if entry else None
        
        results.append(CheckInResponse(
            entry_id=entry_id_str,
            dancer_name=dancer.name if dancer else "Unknown",
            competitor_number=entry.competitor_number if entry else None,
            competition_name=comp.name if comp else "Unknown",
            status=entry.check_in_status if entry else CheckInStatus.NOT_CHECKED_IN,
            checked_in_at=entry.checked_in_at if entry else None,
            message=message
        ))
    
    return BulkCheckInResponse(
        successful=successful,
        failed=failed,
        results=results
    )


@router.post("/checkin/{entry_id}/undo", response_model=CheckInResponse)
async def undo_check_in_endpoint(
    entry_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Undo a check-in."""
    success, message, entry = undo_check_in(session, UUID(entry_id))
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    dancer = session.get(Dancer, entry.dancer_id)
    comp = session.get(Competition, entry.competition_id)
    
    return CheckInResponse(
        entry_id=str(entry.id),
        dancer_name=dancer.name if dancer else "Unknown",
        competitor_number=entry.competitor_number,
        competition_name=comp.name if comp else "Unknown",
        status=entry.check_in_status,
        checked_in_at=entry.checked_in_at,
        message=message
    )


@router.get("/checkin/qr/{dancer_id}")
async def generate_checkin_qr_code(
    dancer_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Generate a QR code for dancer check-in."""
    dancer = session.get(Dancer, UUID(dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    # Parents can only get QR for their own dancers
    if current_user.role == RoleType.PARENT and dancer.parent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Generate QR code with dancer ID
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(f"dancer:{dancer_id}")
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    return StreamingResponse(buf, media_type="image/png")
