"""
Judge Panel Management API

Endpoints for creating and managing judge panels (3-judge, 5-judge, etc.).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from uuid import UUID
from datetime import datetime

from backend.db.database import get_session
from backend.api.auth import require_organizer_or_admin
from backend.api.schemas import (
    JudgePanelCreate,
    JudgePanelUpdate,
    JudgePanelResponse,
    JudgePanelListResponse,
    PanelMemberResponse
)
from backend.scoring_engine.models_platform import (
    User,
    Feis,
    JudgePanel,
    PanelMember,
    FeisAdjudicator
)

router = APIRouter(tags=["panels"])


@router.get("/feis/{feis_id}/panels", response_model=JudgePanelListResponse)
async def list_panels(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """Get all panels for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Get all panels for this feis with their members
    panels = session.exec(
        select(JudgePanel)
        .where(JudgePanel.feis_id == feis.id)
        .order_by(JudgePanel.created_at)
    ).all()
    
    result = []
    for panel in panels:
        # Get members for this panel
        members_data = session.exec(
            select(PanelMember, FeisAdjudicator)
            .join(FeisAdjudicator, PanelMember.feis_adjudicator_id == FeisAdjudicator.id)
            .where(PanelMember.panel_id == panel.id)
            .order_by(PanelMember.sequence)
        ).all()
        
        members = []
        for member, adjudicator in members_data:
            members.append(PanelMemberResponse(
                id=str(member.id),
                feis_adjudicator_id=str(member.feis_adjudicator_id),
                adjudicator_name=adjudicator.name,
                credential=adjudicator.credential,
                sequence=member.sequence
            ))
        
        result.append(JudgePanelResponse(
            id=str(panel.id),
            feis_id=str(panel.feis_id),
            name=panel.name,
            description=panel.description,
            members=members,
            member_count=len(members),
            created_at=panel.created_at,
            updated_at=panel.updated_at
        ))
    
    return JudgePanelListResponse(
        feis_id=str(feis.id),
        feis_name=feis.name,
        total_panels=len(result),
        panels=result
    )


@router.post("/feis/{feis_id}/panels", response_model=JudgePanelResponse)
async def create_panel(
    feis_id: str,
    panel_data: JudgePanelCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Create a new judge panel."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Validate that all adjudicators exist
    for member in panel_data.members:
        adj = session.get(FeisAdjudicator, UUID(member.feis_adjudicator_id))
        if not adj:
            raise HTTPException(
                status_code=400,
                detail=f"Adjudicator {member.feis_adjudicator_id} not found"
            )
        if adj.feis_id != feis.id:
            raise HTTPException(
                status_code=400,
                detail=f"Adjudicator {member.feis_adjudicator_id} is not on this feis roster"
            )
    
    # Create panel
    panel = JudgePanel(
        feis_id=feis.id,
        name=panel_data.name,
        description=panel_data.description
    )
    session.add(panel)
    session.flush()  # Get the panel ID
    
    # Add members
    members = []
    for member_data in panel_data.members:
        member = PanelMember(
            panel_id=panel.id,
            feis_adjudicator_id=UUID(member_data.feis_adjudicator_id),
            sequence=member_data.sequence
        )
        session.add(member)
        members.append(member)
    
    session.commit()
    session.refresh(panel)
    
    # Build response
    member_responses = []
    for member in members:
        adj = session.get(FeisAdjudicator, member.feis_adjudicator_id)
        member_responses.append(PanelMemberResponse(
            id=str(member.id),
            feis_adjudicator_id=str(member.feis_adjudicator_id),
            adjudicator_name=adj.name if adj else "Unknown",
            credential=adj.credential if adj else None,
            sequence=member.sequence
        ))
    
    return JudgePanelResponse(
        id=str(panel.id),
        feis_id=str(panel.feis_id),
        name=panel.name,
        description=panel.description,
        members=member_responses,
        member_count=len(member_responses),
        created_at=panel.created_at,
        updated_at=panel.updated_at
    )


@router.put("/panels/{panel_id}", response_model=JudgePanelResponse)
async def update_panel(
    panel_id: str,
    panel_data: JudgePanelUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Update a judge panel."""
    panel = session.get(JudgePanel, UUID(panel_id))
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    # Update basic fields
    if panel_data.name is not None:
        panel.name = panel_data.name
    if panel_data.description is not None:
        panel.description = panel_data.description
    
    # Update members if provided
    if panel_data.members is not None:
        # Delete existing members
        existing_members = session.exec(
            select(PanelMember).where(PanelMember.panel_id == panel.id)
        ).all()
        for member in existing_members:
            session.delete(member)
        
        # Add new members
        for member_data in panel_data.members:
            adj = session.get(FeisAdjudicator, UUID(member_data.feis_adjudicator_id))
            if not adj:
                raise HTTPException(
                    status_code=400,
                    detail=f"Adjudicator {member_data.feis_adjudicator_id} not found"
                )
            
            member = PanelMember(
                panel_id=panel.id,
                feis_adjudicator_id=UUID(member_data.feis_adjudicator_id),
                sequence=member_data.sequence
            )
            session.add(member)
    
    panel.updated_at = datetime.utcnow()
    session.add(panel)
    session.commit()
    session.refresh(panel)
    
    # Build response
    members_data = session.exec(
        select(PanelMember, FeisAdjudicator)
        .join(FeisAdjudicator, PanelMember.feis_adjudicator_id == FeisAdjudicator.id)
        .where(PanelMember.panel_id == panel.id)
        .order_by(PanelMember.sequence)
    ).all()
    
    member_responses = []
    for member, adj in members_data:
        member_responses.append(PanelMemberResponse(
            id=str(member.id),
            feis_adjudicator_id=str(member.feis_adjudicator_id),
            adjudicator_name=adj.name,
            credential=adj.credential,
            sequence=member.sequence
        ))
    
    return JudgePanelResponse(
        id=str(panel.id),
        feis_id=str(panel.feis_id),
        name=panel.name,
        description=panel.description,
        members=member_responses,
        member_count=len(member_responses),
        created_at=panel.created_at,
        updated_at=panel.updated_at
    )


@router.delete("/panels/{panel_id}")
async def delete_panel(
    panel_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Delete a judge panel."""
    panel = session.get(JudgePanel, UUID(panel_id))
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")
    
    # Check if panel is currently assigned to any stages
    from backend.scoring_engine.models_platform import StageJudgeCoverage
    coverage = session.exec(
        select(StageJudgeCoverage).where(StageJudgeCoverage.panel_id == panel.id)
    ).first()
    
    if coverage:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete panel that is currently assigned to stages. Remove stage assignments first."
        )
    
    # Delete members (cascade should handle this, but explicit is safer)
    members = session.exec(
        select(PanelMember).where(PanelMember.panel_id == panel.id)
    ).all()
    for member in members:
        session.delete(member)
    
    session.delete(panel)
    session.commit()
    
    return {"message": f"Panel '{panel.name}' deleted successfully"}

