"""
Paper model and related tables.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Column, String, Text, Date, DateTime, Float, Integer,
    Boolean, ForeignKey, Index, JSON
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from app.core.database import Base


class Paper(Base):
    """Core paper metadata from arXiv."""
    
    __tablename__ = "papers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    arxiv_id = Column(String(50), unique=True, nullable=False, index=True)
    semantic_scholar_id = Column(String(50), nullable=True, index=True)
    
    title = Column(Text, nullable=False)
    abstract = Column(Text, nullable=False)
    authors = Column(JSON, nullable=False)  # [{"name": "X", "affiliations": ["Y"]}]
    
    published_date = Column(Date, nullable=False, index=True)
    updated_date = Column(Date, nullable=True)
    
    primary_category = Column(String(20), nullable=False, index=True)
    categories = Column(ARRAY(String), nullable=False)
    
    pdf_url = Column(String(500), nullable=False)
    arxiv_url = Column(String(500), nullable=False)
    doi = Column(String(100), nullable=True)
    journal_ref = Column(String(500), nullable=True)
    comments = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    metrics = relationship("PaperMetrics", back_populates="paper", uselist=False)
    implementations = relationship("PaperImplementation", back_populates="paper")
    summary = relationship("PaperSummary", back_populates="paper", uselist=False)
    
    # Note: Full-text search with gin_trgm_ops requires pg_trgm extension
    # Add via Alembic migration: CREATE EXTENSION IF NOT EXISTS pg_trgm;


class PaperMetrics(Base):
    """Metrics and ranking scores for papers."""
    
    __tablename__ = "paper_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id"), unique=True)
    
    citation_count = Column(Integer, default=0, nullable=False)
    citation_velocity_7d = Column(Integer, default=0, nullable=False)
    arxiv_download_count = Column(Integer, default=0, nullable=True)
    
    github_stars = Column(Integer, default=0, nullable=False)
    github_repos_count = Column(Integer, default=0, nullable=False)
    huggingface_downloads = Column(Integer, default=0, nullable=True)
    
    social_score = Column(Float, default=0.0, nullable=False)
    overall_rank_score = Column(Float, default=0.0, nullable=False, index=True)
    
    last_metrics_update = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    paper = relationship("Paper", back_populates="metrics")


class PaperImplementation(Base):
    """GitHub repos and HuggingFace models linked to papers."""
    
    __tablename__ = "paper_implementations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id"), index=True)
    
    source = Column(String(20), nullable=False)  # "github", "huggingface", "paperswithcode"
    repo_url = Column(String(500), nullable=False)
    repo_name = Column(String(200), nullable=False)
    stars = Column(Integer, default=0, nullable=False)
    description = Column(Text, nullable=True)
    language = Column(String(50), nullable=True)  # Programming language
    last_updated = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    paper = relationship("Paper", back_populates="implementations")


class PaperSummary(Base):
    """AI-generated summaries for papers."""
    
    __tablename__ = "paper_summaries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id"), unique=True)
    
    one_line_summary = Column(Text, nullable=False)
    eli5 = Column(Text, nullable=True)
    key_innovation = Column(Text, nullable=True)
    problem_statement = Column(Text, nullable=True)
    methodology = Column(Text, nullable=True)
    real_world_use_cases = Column(Text, nullable=True)
    limitations = Column(Text, nullable=True)
    results_summary = Column(Text, nullable=True)
    
    generated_by = Column(String(50), nullable=False)  # "groq-llama3-70b"
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    quality_score = Column(Float, nullable=True)
    
    # Relationships
    paper = relationship("Paper", back_populates="summary")


class PaperRelationship(Base):
    """Relationships between papers (citations, related)."""
    
    __tablename__ = "paper_relationships"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id"), index=True)
    target_paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id"), index=True)
    
    relationship_type = Column(String(20), nullable=False)  # "cites", "cited_by", "related"
    confidence_score = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
