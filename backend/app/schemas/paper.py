"""
Pydantic schemas for Paper API requests and responses.
"""
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# Author schema
class AuthorSchema(BaseModel):
    """Author information."""
    name: str
    affiliations: List[str] = []


# Paper schemas
class PaperBase(BaseModel):
    """Base paper fields."""
    arxiv_id: str
    title: str
    abstract: str
    authors: List[AuthorSchema]
    published_date: date
    primary_category: str
    categories: List[str]
    pdf_url: str
    arxiv_url: str


class PaperCreate(PaperBase):
    """Schema for creating a paper."""
    updated_date: Optional[date] = None
    doi: Optional[str] = None
    journal_ref: Optional[str] = None
    comments: Optional[str] = None


class PaperMetricsResponse(BaseModel):
    """Paper metrics response."""
    citation_count: int = 0
    citation_velocity_7d: int = 0
    github_stars: int = 0
    github_repos_count: int = 0
    huggingface_downloads: Optional[int] = None
    overall_rank_score: float = 0.0
    
    class Config:
        from_attributes = True


class PaperImplementationResponse(BaseModel):
    """Paper implementation response."""
    id: UUID
    source: str
    repo_url: str
    repo_name: str
    stars: int = 0
    description: Optional[str] = None
    language: Optional[str] = None
    
    class Config:
        from_attributes = True


class PaperSummaryResponse(BaseModel):
    """Paper summary response."""
    one_line_summary: str
    eli5: Optional[str] = None
    key_innovation: Optional[str] = None
    problem_statement: Optional[str] = None
    methodology: Optional[str] = None
    real_world_use_cases: Optional[str] = None
    limitations: Optional[str] = None
    results_summary: Optional[str] = None
    pros: Optional[str] = None  # New: advantages/strengths
    cons: Optional[str] = None  # New: disadvantages/weaknesses
    generated_by: str
    generated_at: datetime
    quality_score: Optional[float] = None
    
    class Config:
        from_attributes = True


class PaperListItem(BaseModel):
    """Paper item for list views (minimal data)."""
    id: UUID
    arxiv_id: str
    title: str
    authors: List[AuthorSchema]
    published_date: date
    primary_category: str
    categories: List[str]
    pdf_url: str
    arxiv_url: str
    
    # Optional enriched data
    one_line_summary: Optional[str] = None
    citation_count: int = 0
    citation_velocity_7d: int = 0
    github_stars: int = 0
    has_implementation: bool = False
    
    class Config:
        from_attributes = True


class PaperDetail(PaperBase):
    """Full paper detail response."""
    id: UUID
    updated_date: Optional[date] = None
    doi: Optional[str] = None
    journal_ref: Optional[str] = None
    comments: Optional[str] = None
    created_at: datetime
    
    # Related data
    metrics: Optional[PaperMetricsResponse] = None
    summary: Optional[PaperSummaryResponse] = None
    implementations: List[PaperImplementationResponse] = []
    
    class Config:
        from_attributes = True


class PaperListResponse(BaseModel):
    """Paginated paper list response."""
    items: List[PaperListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaperSearchRequest(BaseModel):
    """Paper search request body."""
    query: str = Field(..., min_length=2, max_length=500)
    categories: Optional[List[str]] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    has_implementation: Optional[bool] = None
    min_citations: Optional[int] = None
