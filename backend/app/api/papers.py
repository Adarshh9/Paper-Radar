"""
Paper API endpoints.
"""
from datetime import date, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, desc, or_
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.dependencies import get_current_user_optional
from app.core.cache import cache
from app.models import Paper, PaperMetrics, PaperImplementation, PaperSummary, User
from app.schemas import (
    PaperListItem,
    PaperListResponse,
    PaperDetail,
    PaperSearchRequest,
)

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


@router.get("", response_model=PaperListResponse)
async def list_papers(
    category: Optional[str] = Query(None, description="Filter by category (e.g., cs.AI)"),
    date_from: Optional[date] = Query(None, description="Filter papers from this date"),
    date_to: Optional[date] = Query(None, description="Filter papers until this date"),
    sort_by: str = Query("rank_score", description="Sort by: rank_score, published_date, citations"),
    has_implementation: Optional[bool] = Query(None, description="Filter papers with implementations"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    List papers with filtering, sorting, and pagination.
    """
    # Build query
    query = db.query(Paper).options(
        joinedload(Paper.metrics),
        joinedload(Paper.summary),
        joinedload(Paper.implementations),
    )
    
    # Apply filters
    if category:
        query = query.filter(
            or_(
                Paper.primary_category == category,
                Paper.categories.contains([category])
            )
        )
    
    if date_from:
        query = query.filter(Paper.published_date >= date_from)
    
    if date_to:
        query = query.filter(Paper.published_date <= date_to)
    
    if has_implementation is True:
        query = query.join(Paper.implementations).group_by(Paper.id)
    
    # Get total count
    total = query.count()
    
    # Apply sorting
    if sort_by == "published_date":
        query = query.order_by(desc(Paper.published_date))
    elif sort_by == "citations":
        query = query.outerjoin(PaperMetrics).order_by(
            desc(func.coalesce(PaperMetrics.citation_count, 0))
        )
    else:  # rank_score (default)
        query = query.outerjoin(PaperMetrics).order_by(
            desc(func.coalesce(PaperMetrics.overall_rank_score, 0))
        )
    
    # Apply pagination
    offset = (page - 1) * page_size
    papers = query.offset(offset).limit(page_size).all()
    
    # Convert to response
    items = [paper_to_list_item(p) for p in papers]
    total_pages = (total + page_size - 1) // page_size
    
    return PaperListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/trending", response_model=List[PaperListItem])
async def get_trending_papers(
    timeframe: str = Query("week", description="Timeframe: day, week, month"),
    limit: int = Query(20, ge=1, le=50, description="Number of papers"),
    db: Session = Depends(get_db),
):
    """
    Get trending papers based on ranking score and recency.
    """
    # Calculate date threshold
    days_map = {"day": 1, "week": 7, "month": 30}
    days = days_map.get(timeframe, 7)
    threshold_date = date.today() - timedelta(days=days)
    
    # Check cache
    cache_key = f"trending:{timeframe}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    try:
        # First get paper IDs with their scores - rely on rank_score which handles recency decay
        paper_ids_query = (
            db.query(Paper.id)
            .outerjoin(PaperMetrics)
            .order_by(
                desc(func.coalesce(PaperMetrics.overall_rank_score, 0)),
                desc(Paper.published_date),
            )
            .limit(limit)
            .all()
        )
        
        paper_ids = [p[0] for p in paper_ids_query]
        
        if not paper_ids:
            return []
        
        # Then fetch full paper data with eager loading
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
        
        # Sort by rank score to maintain order
        papers_dict = {p.id: p for p in papers}
        ordered_papers = [papers_dict[pid] for pid in paper_ids if pid in papers_dict]
        
        items = [paper_to_list_item(p) for p in ordered_papers]
        
        # Cache for 15 minutes
        if items:
            cache.set(cache_key, [item.model_dump(mode='json') for item in items], ttl_seconds=900)
        
        return items
    except Exception as e:
        # Log error and return empty list
        from loguru import logger
        logger.error(f"Trending papers error: {e}")
        return []


@router.get("/categories")
async def get_categories(db: Session = Depends(get_db)):
    """
    Get available categories with paper counts.
    """
    # Check cache
    cache_key = "categories:list"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    # Query category counts
    result = (
        db.query(
            Paper.primary_category,
            func.count(Paper.id).label("count")
        )
        .group_by(Paper.primary_category)
        .order_by(desc("count"))
        .all()
    )
    
    categories = [
        {"category": row[0], "count": row[1]}
        for row in result
    ]
    
    # Cache for 6 hours
    cache.set(cache_key, categories, ttl_seconds=21600)
    
    return categories


@router.get("/{paper_id}", response_model=PaperDetail)
async def get_paper_detail(
    paper_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get full paper details including metrics, summary, and implementations.
    """
    # Check cache
    cache_key = f"paper:{paper_id}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    paper = (
        db.query(Paper)
        .options(
            joinedload(Paper.metrics),
            joinedload(Paper.summary),
            joinedload(Paper.implementations),
        )
        .filter(Paper.id == paper_id)
        .first()
    )
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found",
        )
    
    # Cache for 1 hour
    response = PaperDetail.model_validate(paper)
    cache.set(cache_key, response.model_dump(mode='json'), ttl_seconds=3600)
    
    return response


@router.post("/search", response_model=PaperListResponse)
async def search_papers(
    request: PaperSearchRequest,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Search papers by keyword with filters.
    Uses PostgreSQL full-text search on title and abstract.
    """
    # Build search query
    search_term = f"%{request.query}%"
    
    query = db.query(Paper).options(
        joinedload(Paper.metrics),
        joinedload(Paper.summary),
        joinedload(Paper.implementations),
    ).filter(
        or_(
            Paper.title.ilike(search_term),
            Paper.abstract.ilike(search_term),
        )
    )
    
    # Apply additional filters
    if request.categories:
        query = query.filter(Paper.primary_category.in_(request.categories))
    
    if request.date_from:
        query = query.filter(Paper.published_date >= request.date_from)
    
    if request.date_to:
        query = query.filter(Paper.published_date <= request.date_to)
    
    if request.has_implementation:
        query = query.join(Paper.implementations).group_by(Paper.id)
    
    if request.min_citations:
        query = query.join(PaperMetrics).filter(
            PaperMetrics.citation_count >= request.min_citations
        )
    
    # Get total and paginate
    total = query.count()
    
    # Order by relevance (rank score) and recency
    query = query.outerjoin(PaperMetrics).order_by(
        desc(func.coalesce(PaperMetrics.overall_rank_score, 0)),
        desc(Paper.published_date),
    )
    
    offset = (page - 1) * page_size
    papers = query.offset(offset).limit(page_size).all()
    
    items = [paper_to_list_item(p) for p in papers]
    total_pages = (total + page_size - 1) // page_size
    
    return PaperListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
