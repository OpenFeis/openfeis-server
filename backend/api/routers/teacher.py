from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import List, Optional
from uuid import UUID
from sqlmodel import Session, select, func
import csv
import io
from backend.db.database import get_session
from backend.api.auth import get_current_user, require_teacher
from backend.scoring_engine.models_platform import User, Dancer, Entry, Competition, Feis, RoleType, AdvancementNotice, EntryFlag
from backend.api.schemas import TeacherDashboardResponse, SchoolRosterResponse, SchoolStudentInfo, TeacherStudentEntry, LinkDancerToSchoolRequest

router = APIRouter()

@router.get("/teacher/dashboard", response_model=TeacherDashboardResponse)
async def get_teacher_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_teacher())
):
    """Get teacher dashboard data."""
    # Get all students
    students = session.exec(
        select(Dancer).where(Dancer.school_id == current_user.id)
    ).all()
    
    student_ids = [s.id for s in students]
    
    # Get entries
    entries = session.exec(
        select(Entry).where(Entry.dancer_id.in_(student_ids))
    ).all() if student_ids else []
    
    # Count entries by feis
    entries_by_feis = {}
    for entry in entries:
        comp = session.get(Competition, entry.competition_id)
        if comp:
            feis_id = str(comp.feis_id)
            entries_by_feis[feis_id] = entries_by_feis.get(feis_id, 0) + 1
    
    # Count pending advancements
    pending_adv = session.exec(
        select(func.count(AdvancementNotice.id))
        .where(AdvancementNotice.dancer_id.in_(student_ids))
        .where(AdvancementNotice.acknowledged == False)
        .where(AdvancementNotice.overridden == False)
    ).one() if student_ids else 0
    
    # Get recent entries (last 20)
    recent = []
    for entry in entries[:20]:
        dancer = session.get(Dancer, entry.dancer_id)
        comp = session.get(Competition, entry.competition_id)
        feis = session.get(Feis, comp.feis_id) if comp else None
        
        flag = session.exec(
            select(EntryFlag)
            .where(EntryFlag.entry_id == entry.id)
            .where(EntryFlag.resolved == False)
        ).first()
        
        recent.append(TeacherStudentEntry(
            entry_id=str(entry.id),
            dancer_id=str(entry.dancer_id),
            dancer_name=dancer.name if dancer else "Unknown",
            competition_id=str(entry.competition_id),
            competition_name=comp.name if comp else "Unknown",
            level=comp.level if comp else None,
            competitor_number=entry.competitor_number,
            paid=entry.paid,
            feis_id=str(comp.feis_id) if comp else "",
            feis_name=feis.name if feis else "Unknown",
            feis_date=feis.date if feis else None,
            is_flagged=flag is not None,
            flag_id=str(flag.id) if flag else None
        ))
    
    return TeacherDashboardResponse(
        teacher_id=str(current_user.id),
        teacher_name=current_user.name,
        total_students=len(students),
        total_entries=len(entries),
        entries_by_feis=entries_by_feis,
        pending_advancements=pending_adv,
        recent_entries=recent
    )


@router.get("/teacher/roster", response_model=SchoolRosterResponse)
async def get_school_roster(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_teacher())
):
    """Get all students in the teacher's school."""
    dancers = session.exec(
        select(Dancer).where(Dancer.school_id == current_user.id)
    ).all()
    
    students = []
    for dancer in dancers:
        parent = session.get(User, dancer.parent_id)
        entry_count = session.exec(
            select(func.count(Entry.id)).where(Entry.dancer_id == dancer.id)
        ).one()
        
        pending_adv = session.exec(
            select(func.count(AdvancementNotice.id))
            .where(AdvancementNotice.dancer_id == dancer.id)
            .where(AdvancementNotice.acknowledged == False)
            .where(AdvancementNotice.overridden == False)
        ).one()
        
        students.append(SchoolStudentInfo(
            id=str(dancer.id),
            name=dancer.name,
            dob=dancer.dob,
            current_level=dancer.current_level,
            gender=dancer.gender,
            parent_name=parent.name if parent else "Unknown",
            entry_count=entry_count,
            pending_advancements=pending_adv
        ))
    
    return SchoolRosterResponse(
        school_id=str(current_user.id),
        teacher_name=current_user.name,
        total_students=len(students),
        students=students
    )


@router.get("/teacher/entries", response_model=List[TeacherStudentEntry])
async def get_teacher_student_entries(
    feis_id: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_teacher())
):
    """Get all entries for students in the teacher's school."""
    dancers = session.exec(
        select(Dancer).where(Dancer.school_id == current_user.id)
    ).all()
    
    dancer_ids = [d.id for d in dancers]
    
    if not dancer_ids:
        return []
    
    entries = session.exec(select(Entry).where(Entry.dancer_id.in_(dancer_ids))).all()
    
    results = []
    for entry in entries:
        comp = session.get(Competition, entry.competition_id)
        if not comp:
            continue
        
        if feis_id and str(comp.feis_id) != feis_id:
            continue
        
        dancer = session.get(Dancer, entry.dancer_id)
        feis = session.get(Feis, comp.feis_id)
        
        flag = session.exec(
            select(EntryFlag)
            .where(EntryFlag.entry_id == entry.id)
            .where(EntryFlag.resolved == False)
        ).first()
        
        results.append(TeacherStudentEntry(
            entry_id=str(entry.id),
            dancer_id=str(entry.dancer_id),
            dancer_name=dancer.name if dancer else "Unknown",
            competition_id=str(entry.competition_id),
            competition_name=comp.name,
            level=comp.level,
            competitor_number=entry.competitor_number,
            paid=entry.paid,
            feis_id=str(comp.feis_id),
            feis_name=feis.name if feis else "Unknown",
            feis_date=feis.date if feis else None,
            is_flagged=flag is not None,
            flag_id=str(flag.id) if flag else None
        ))
    
    return results


@router.post("/dancers/{dancer_id}/link-school")
async def link_dancer_to_school(
    dancer_id: str,
    link_data: LinkDancerToSchoolRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Link a dancer to a school (teacher)."""
    dancer = session.get(Dancer, UUID(dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    teacher = session.get(User, UUID(link_data.school_id))
    if not teacher or teacher.role != RoleType.TEACHER:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    # Check permissions
    is_parent = dancer.parent_id == current_user.id
    is_teacher = UUID(link_data.school_id) == current_user.id
    is_admin = current_user.role in [RoleType.SUPER_ADMIN, RoleType.ORGANIZER]
    
    if not (is_parent or is_teacher or is_admin):
        raise HTTPException(status_code=403, detail="Not authorized to link this dancer")
    
    dancer.school_id = teacher.id
    session.add(dancer)
    session.commit()
    
    return {"success": True, "message": f"Dancer linked to {teacher.name}'s school"}


@router.delete("/dancers/{dancer_id}/unlink-school")
async def unlink_dancer_from_school(
    dancer_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Remove a dancer from their school."""
    dancer = session.get(Dancer, UUID(dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    # Check permissions
    is_parent = dancer.parent_id == current_user.id
    is_teacher = dancer.school_id == current_user.id
    is_admin = current_user.role in [RoleType.SUPER_ADMIN, RoleType.ORGANIZER]
    
    if not (is_parent or is_teacher or is_admin):
        raise HTTPException(status_code=403, detail="Not authorized to unlink this dancer")
    
    dancer.school_id = None
    session.add(dancer)
    session.commit()
    
    return {"success": True, "message": "Dancer unlinked from school"}


@router.get("/teacher/export")
async def export_teacher_entries(
    feis_id: Optional[str] = None,
    format: str = "csv",
    session: Session = Depends(get_session),
    current_user: User = Depends(require_teacher())
):
    """Export teacher's student entries to CSV or JSON."""
    dancers = session.exec(
        select(Dancer).where(Dancer.school_id == current_user.id)
    ).all()
    
    dancer_ids = [d.id for d in dancers]
    
    if not dancer_ids:
        if format == "csv":
            return StreamingResponse(
                io.StringIO("No entries found"),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=school_entries.csv"}
            )
        return {"entries": []}
    
    entries = session.exec(
        select(Entry).where(Entry.dancer_id.in_(dancer_ids))
    ).all()
    
    export_data = []
    for entry in entries:
        comp = session.get(Competition, entry.competition_id)
        if not comp:
            continue
        
        if feis_id and str(comp.feis_id) != feis_id:
            continue
        
        dancer = session.get(Dancer, entry.dancer_id)
        feis = session.get(Feis, comp.feis_id)
        
        export_data.append({
            "dancer_name": dancer.name if dancer else "Unknown",
            "competition_name": comp.name,
            "level": comp.level.value,
            "feis_name": feis.name if feis else "Unknown",
            "feis_date": str(feis.date) if feis else "",
            "competitor_number": entry.competitor_number or "",
            "paid": "Yes" if entry.paid else "No"
        })
    
    if format == "json":
        return {"entries": export_data}
    
    # CSV export
    output = io.StringIO()
    if export_data:
        writer = csv.DictWriter(output, fieldnames=export_data[0].keys())
        writer.writeheader()
        writer.writerows(export_data)
    
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=school_entries.csv"}
    )
