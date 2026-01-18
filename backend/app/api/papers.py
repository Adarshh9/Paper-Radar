"""
Paper API endpoints.
"""
from datetime import date, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, desc, or_, String
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.cache import cache
from app.models import Paper, PaperMetrics
from app.schemas import (
    PaperListItem,
    PaperListResponse,
    PaperDetail,
    PaperSearchRequest,
)

router = APIRouter()


# Request/Response models for paper submission
class PaperSubmitRequest(BaseModel):
    url: str  # arXiv URL (abs or pdf)


class PaperSubmitResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    paper_id: Optional[str] = None
    arxiv_id: Optional[str] = None
    title: Optional[str] = None
    already_exists: bool = False


def paper_to_list_item(paper: Paper) -> PaperListItem:
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
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category"),
    date_from: Optional[date] = Query(None, description="Filter papers from this date"),
    date_to: Optional[date] = Query(None, description="Filter papers until this date"),
    has_implementation: Optional[bool] = Query(None, description="Filter papers with implementations"),
    sort_by: str = Query("rank_score", description="Sort by: rank_score, published_date, citations"),
    db: Session = Depends(get_db),
):
    """
    List papers with pagination and filtering.
    """
    # Build query
    query = db.query(Paper).options(
        joinedload(Paper.metrics),
        joinedload(Paper.summary),
        joinedload(Paper.implementations),
    )
    if category:
        # Filter by primary category or check if category is in categories JSON array
        # Use LIKE for JSON array compatibility with SQLite
        query = query.filter(
            or_(
                Paper.primary_category == category,
                Paper.categories.cast(String).like(f'%"{category}"%')
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
    timeframe: str = Query("quarter", description="Timeframe: week, month, quarter, half_year, year"),
    limit: int = Query(10, ge=1, le=50, description="Number of papers to return"),
    db: Session = Depends(get_db),
):
    """
    Get trending papers based on rank score.
    """
    # Calculate date threshold - updated ranges without "all time"
    days_map = {
        "week": 7, 
        "month": 30, 
        "quarter": 90, 
        "half_year": 180, 
        "year": 365,
    }
    days = days_map.get(timeframe, 90)  # Default to 3 months
    
    # Check cache
    cache_key = f"trending:{timeframe}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    try:
        # Build base query
        query = (
            db.query(Paper.id)
            .outerjoin(PaperMetrics)
        )
        
        # Apply date filter (always apply, no "all time" option)
        threshold_date = date.today() - timedelta(days=days)
        query = query.filter(Paper.published_date >= threshold_date)
        
        paper_ids_query = (
            query
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
    Get list of all paper categories with counts.
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
    Get detailed information about a specific paper.
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
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """
    Search papers by title and abstract.
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


@router.post("/submit", response_model=PaperSubmitResponse)
async def submit_paper(
    request: PaperSubmitRequest,
    db: Session = Depends(get_db),
):
    """
    Submit a paper URL for community contribution.
    
    Accepts arXiv URLs in formats:
    - https://arxiv.org/abs/2512.24880
    - https://arxiv.org/pdf/2512.24880
    - https://arxiv.org/pdf/2512.24880.pdf
    
    The paper will be fetched, indexed, and enriched with:
    - AI-generated summaries (using full paper context when available)
    - GitHub implementation discovery
    - Citation metrics
    """
    from app.services.paper_submission_service import paper_submission_service
    
    result = await paper_submission_service.submit_paper(request.url)
    
    return PaperSubmitResponse(**result)