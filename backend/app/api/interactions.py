"""
User interactions API endpoints.
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, UserInteraction, Paper
from app.schemas import InteractionCreate, InteractionResponse
from app.schemas.paper import PaperListItem

router = APIRouter()


@router.post("", response_model=InteractionResponse, status_code=status.HTTP_201_CREATED)
async def create_interaction(
    request: InteractionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Record a user interaction with a paper.
    """
    # Verify paper exists
    paper = db.query(Paper).filter(Paper.id == request.paper_id).first()
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found",
        )
    
    # Handle unsave action
    if request.interaction_type == "unsave":
        # Delete existing save interaction
        db.query(UserInteraction).filter(
            UserInteraction.user_id == current_user.id,
            UserInteraction.paper_id == request.paper_id,
            UserInteraction.interaction_type == "save",
        ).delete()
        db.commit()
        
        # Return a dummy response for unsave
        return InteractionResponse(
            id=UUID("00000000-0000-0000-0000-000000000000"),
            paper_id=request.paper_id,
            interaction_type="unsave",
            created_at=paper.created_at,  # Just use any datetime
        )
    
    # For save, check if already saved
    if request.interaction_type == "save":
        existing = db.query(UserInteraction).filter(
            UserInteraction.user_id == current_user.id,
            UserInteraction.paper_id == request.paper_id,
            UserInteraction.interaction_type == "save",
        ).first()
        
        if existing:
            return InteractionResponse.model_validate(existing)
    
    # Create interaction
    interaction = UserInteraction(
        user_id=current_user.id,
        paper_id=request.paper_id,
        interaction_type=request.interaction_type,
        interaction_metadata=request.metadata,
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    
    return interaction


@router.get("/saved", response_model=List[PaperListItem])
async def get_saved_papers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get papers saved by the current user.
    """
    # Get saved paper IDs
    saved_interactions = (
        db.query(UserInteraction)
        .filter(
            UserInteraction.user_id == current_user.id,
            UserInteraction.interaction_type == "save",
        )
        .order_by(desc(UserInteraction.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    
    paper_ids = [i.paper_id for i in saved_interactions]
    
    if not paper_ids:
        return []
    
    # Get papers with related data
    papers = (
        db.query(Paper)
        .options(
            joinedload(Paper.metrics),
            joinedload(Paper.summary),
            joinedload(Paper.implementations),
        )
        .filter(Paper.id.in_(paper_ids))
        .all()
    )
    
    # Maintain order from interactions
    paper_map = {p.id: p for p in papers}
    ordered_papers = [paper_map[pid] for pid in paper_ids if pid in paper_map]
    
    # Convert to response
    from app.api.papers import paper_to_list_item
    return [paper_to_list_item(p) for p in ordered_papers]


@router.get("/history", response_model=List[InteractionResponse])
async def get_interaction_history(
    interaction_type: str = Query(None, description="Filter by type"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get user's interaction history.
    """
    query = db.query(UserInteraction).filter(
        UserInteraction.user_id == current_user.id
    )
    
    if interaction_type:
        query = query.filter(UserInteraction.interaction_type == interaction_type)
    
    interactions = (
        query
        .order_by(desc(UserInteraction.created_at))
        .limit(limit)
        .all()
    )
    
    return interactions
