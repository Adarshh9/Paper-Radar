"""
Personalized recommendations API.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_user_optional
from app.core.cache import cache
from app.models import User, UserPreferences, UserInteraction, Paper, PaperMetrics
from app.schemas.paper import PaperListItem

router = APIRouter()


def paper_to_list_item(paper: Paper) -> PaperListItem:
    """Convert Paper model to PaperListItem schema."""
    return PaperListItem(
        id=paper.id,
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        authors=paper.authors,
        published_date=paper.published_date,
        primary_category=paper.primary_category,
        categories=paper.categories,
        pdf_url=paper.pdf_url,
        arxiv_url=paper.arxiv_url,
        one_line_summary=paper.summary.one_line_summary if paper.summary else None,
        citation_count=paper.metrics.citation_count if paper.metrics else 0,
        citation_velocity_7d=paper.metrics.citation_velocity_7d if paper.metrics else 0,
        github_stars=paper.metrics.github_stars if paper.metrics else 0,
        has_implementation=len(paper.implementations) > 0 if paper.implementations else False,
    )


@router.get("", response_model=List[PaperListItem])
async def get_recommendations(
    limit: int = Query(20, ge=1, le=50),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """
    Get personalized paper recommendations.
    
    For authenticated users: Based on interests and past interactions.
    For anonymous users: Returns trending papers.
    """
    if not current_user:
        # Return trending papers for anonymous users
        return await get_anonymous_recommendations(limit, db)
    
    # Check cache
    cache_key = f"recommendations:{current_user.id}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    # Get user preferences
    preferences = db.query(UserPreferences).filter(
        UserPreferences.user_id == current_user.id
    ).first()
    
    interested_categories = preferences.interested_categories if preferences else []
    
    # Get papers user has already interacted with
    interacted_paper_ids = (
        db.query(UserInteraction.paper_id)
        .filter(UserInteraction.user_id == current_user.id)
        .distinct()
        .all()
    )
    interacted_ids = [pid[0] for pid in interacted_paper_ids]
    
    # Build recommendation query
    query = db.query(Paper).options(
        joinedload(Paper.metrics),
        joinedload(Paper.summary),
        joinedload(Paper.implementations),
    )
    
    # Filter by user's interested categories if they have any
    if interested_categories:
        query = query.filter(Paper.primary_category.in_(interested_categories))
    
    # Exclude already interacted papers
    if interacted_ids:
        query = query.filter(~Paper.id.in_(interacted_ids))
    
    # Apply paper maturity filter
    if preferences and preferences.paper_maturity == "with_implementation":
        query = query.join(Paper.implementations).group_by(Paper.id)
    
    # Order by ranking score
    query = query.outerjoin(PaperMetrics).order_by(
        desc(func.coalesce(PaperMetrics.overall_rank_score, 0))
    )
    
    papers = query.limit(limit).all()
    
    # If not enough papers, supplement with trending
    if len(papers) < limit:
        additional_needed = limit - len(papers)
        existing_ids = [p.id for p in papers] + interacted_ids
        
        additional = (
            db.query(Paper)
            .options(
                joinedload(Paper.metrics),
                joinedload(Paper.summary),
                joinedload(Paper.implementations),
            )
            .filter(~Paper.id.in_(existing_ids))
            .outerjoin(PaperMetrics)
            .order_by(desc(func.coalesce(PaperMetrics.overall_rank_score, 0)))
            .limit(additional_needed)
            .all()
        )
        papers.extend(additional)
    
    items = [paper_to_list_item(p) for p in papers]
    
    # Cache for 1 hour
    cache.set(cache_key, [item.model_dump() for item in items], ttl_seconds=3600)
    
    return items


async def get_anonymous_recommendations(limit: int, db: Session) -> List[PaperListItem]:
    """
    Get recommendations for anonymous users (trending papers).
    """
    cache_key = f"recommendations:anonymous:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    papers = (
        db.query(Paper)
        .options(
            joinedload(Paper.metrics),
            joinedload(Paper.summary),
            joinedload(Paper.implementations),
        )
        .outerjoin(PaperMetrics)
        .order_by(desc(func.coalesce(PaperMetrics.overall_rank_score, 0)))
        .limit(limit)
        .all()
    )
    
    items = [paper_to_list_item(p) for p in papers]
    
    # Cache for 30 minutes
    cache.set(cache_key, [item.model_dump() for item in items], ttl_seconds=1800)
    
    return items


@router.get("/similar/{paper_id}", response_model=List[PaperListItem])
async def get_similar_papers(
    paper_id: str,
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """
    Get papers similar to a given paper.
    Based on category overlap and citation relationships.
    """
    from uuid import UUID
    
    # Get source paper
    source_paper = db.query(Paper).filter(Paper.id == UUID(paper_id)).first()
    if not source_paper:
        return []
    
    # Find papers in same categories
    similar = (
        db.query(Paper)
        .options(
            joinedload(Paper.metrics),
            joinedload(Paper.summary),
            joinedload(Paper.implementations),
        )
        .filter(
            Paper.id != source_paper.id,
            Paper.primary_category == source_paper.primary_category,
        )
        .outerjoin(PaperMetrics)
        .order_by(desc(func.coalesce(PaperMetrics.overall_rank_score, 0)))
        .limit(limit)
        .all()
    )
    
    return [paper_to_list_item(p) for p in similar]
