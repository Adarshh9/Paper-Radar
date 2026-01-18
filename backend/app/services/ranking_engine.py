"""
Advanced Ranking Engine with field-normalized scoring.
Implements sophisticated multi-factor scoring for paper relevance.
"""
import math
import asyncio
from datetime import date, timedelta, datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import numpy as np
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.cache import cache
from app.models import Paper, PaperMetrics, PaperImplementation


class RankingFactors(Enum):
    """Enumeration of ranking factors with their weights."""
    CITATION_MOMENTUM = 0.25
    IMPLEMENTATION_QUALITY = 0.20
    AUTHOR_CREDIBILITY = 0.15
    NOVELTY = 0.15
    REPRODUCIBILITY = 0.10
    COMMUNITY_ENGAGEMENT = 0.10
    RECENCY = 0.05


@dataclass
class FieldStats:
    """Statistics for a specific field/category."""
    category: str
    citation_percentiles: List[float]
    velocity_percentiles: List[float]
    mean_citations: float
    std_citations: float
    paper_count: int
    
    
@dataclass
class PaperScoreBreakdown:
    """Detailed breakdown of a paper's score."""
    paper_id: str
    total_score: float
    citation_momentum: float
    implementation_quality: float
    author_credibility: float
    novelty: float
    reproducibility: float
    community_engagement: float
    recency: float
    field_percentile: float


class AdvancedRankingEngine:
    """
    Next-generation paper ranking with field-normalized scoring.
    
    Features:
    - Field-normalized metrics (AI papers vs Theory papers have different patterns)
    - Exponential growth detection for citation momentum
    - Implementation quality scoring beyond just GitHub stars
    - Novelty detection to identify breakthrough papers
    - Adaptive freshness boost (not too aggressive for preprints)
    """
    
    WEIGHTS = {
        "citation_momentum": 0.25,
        "implementation_quality": 0.20,
        "author_credibility": 0.15,
        "novelty": 0.15,
        "reproducibility": 0.10,
        "community_engagement": 0.10,
        "recency": 0.05,
    }
    
    # Field-specific citation thresholds (median citations after 30 days)
    FIELD_CITATION_BASELINES = {
        "cs.AI": 15,
        "cs.LG": 20,
        "cs.CV": 25,
        "cs.CL": 18,
        "cs.NE": 8,
        "stat.ML": 12,
        "default": 10,
    }
    
    # Maximum freshness boost (reduced from 3.0 to prevent low-quality preprint promotion)
    MAX_FRESHNESS_BOOST = 1.5
    
    def __init__(self, db: Session):
        self.db = db
        self._field_stats_cache: Dict[str, FieldStats] = {}
    
    async def calculate_paper_score(
        self,
        paper: Paper,
        metrics: Optional[PaperMetrics] = None,
    ) -> PaperScoreBreakdown:
        """
        Calculate comprehensive ranking score for a paper.
        
        Returns a detailed breakdown of all scoring factors.
        """
        if metrics is None:
            metrics = paper.metrics
        
        # Get field statistics for normalization
        field_stats = await self._get_field_stats(paper.primary_category)
        
        # Calculate individual components
        citation_momentum = await self._calculate_citation_momentum(paper, metrics, field_stats)
        impl_quality = await self._calculate_implementation_quality(paper)
        author_credibility = await self._calculate_author_credibility(paper)
        novelty = await self._calculate_novelty(paper, field_stats)
        reproducibility = self._calculate_reproducibility(paper)
        community = self._calculate_community_engagement(metrics)
        recency = self._calculate_recency(paper.published_date)
        
        # Calculate field percentile
        field_percentile = self._calculate_field_percentile(
            metrics.citation_count if metrics else 0,
            metrics.citation_velocity_7d if metrics else 0,
            field_stats
        )
        
        # Adaptive freshness boost (less aggressive than before)
        days_old = (date.today() - paper.published_date).days
        freshness_boost = self._calculate_freshness_boost(days_old, metrics)
        
        # Weighted sum with freshness adjustment
        raw_score = (
            self.WEIGHTS["citation_momentum"] * citation_momentum +
            self.WEIGHTS["implementation_quality"] * impl_quality +
            self.WEIGHTS["author_credibility"] * author_credibility +
            self.WEIGHTS["novelty"] * novelty +
            self.WEIGHTS["reproducibility"] * reproducibility +
            self.WEIGHTS["community_engagement"] * community +
            self.WEIGHTS["recency"] * recency
        )
        
        total_score = min(raw_score * freshness_boost, 1.0)
        
        return PaperScoreBreakdown(
            paper_id=str(paper.id),
            total_score=round(total_score, 4),
            citation_momentum=round(citation_momentum, 4),
            implementation_quality=round(impl_quality, 4),
            author_credibility=round(author_credibility, 4),
            novelty=round(novelty, 4),
            reproducibility=round(reproducibility, 4),
            community_engagement=round(community, 4),
            recency=round(recency, 4),
            field_percentile=round(field_percentile, 4),
        )
    
    async def _get_field_stats(self, category: str, days: int = 90) -> FieldStats:
        """Get or compute field statistics for normalization."""
        cache_key = f"field_stats:{category}:{days}"
        
        if category in self._field_stats_cache:
            return self._field_stats_cache[category]
        
        # Check Redis/file cache
        cached = cache.get(cache_key)
        if cached:
            stats = FieldStats(**cached)
            self._field_stats_cache[category] = stats
            return stats
        
        # Compute statistics from database
        cutoff = date.today() - timedelta(days=days)
        
        papers_with_metrics = (
            self.db.query(Paper, PaperMetrics)
            .join(PaperMetrics)
            .filter(
                Paper.primary_category == category,
                Paper.published_date >= cutoff
            )
            .all()
        )
        
        if not papers_with_metrics:
            # Return default stats
            return FieldStats(
                category=category,
                citation_percentiles=[0] * 100,
                velocity_percentiles=[0] * 100,
                mean_citations=0,
                std_citations=1,
                paper_count=0,
            )
        
        citations = [m.citation_count for _, m in papers_with_metrics]
        velocities = [m.citation_velocity_7d for _, m in papers_with_metrics]
        
        stats = FieldStats(
            category=category,
            citation_percentiles=list(np.percentile(citations, range(100))),
            velocity_percentiles=list(np.percentile(velocities, range(100))),
            mean_citations=float(np.mean(citations)),
            std_citations=float(np.std(citations)) or 1.0,
            paper_count=len(papers_with_metrics),
        )
        
        # Cache for 6 hours
        cache.set(cache_key, {
            "category": stats.category,
            "citation_percentiles": stats.citation_percentiles,
            "velocity_percentiles": stats.velocity_percentiles,
            "mean_citations": stats.mean_citations,
            "std_citations": stats.std_citations,
            "paper_count": stats.paper_count,
        }, ttl_seconds=21600)
        
        self._field_stats_cache[category] = stats
        return stats
    
    async def _calculate_citation_momentum(
        self,
        paper: Paper,
        metrics: Optional[PaperMetrics],
        field_stats: FieldStats,
    ) -> float:
        """
        Calculate citation momentum with exponential growth detection.
        
        Uses field-normalized percentile ranking instead of hardcoded thresholds.
        """
        if not metrics:
            return 0.0
        
        velocity = metrics.citation_velocity_7d
        total_citations = metrics.citation_count
        
        # Get weekly citation history if available
        citations_history = await self._get_citation_history(paper)
        
        if citations_history and len(citations_history) >= 4:
            # Detect exponential growth
            recent_avg = np.mean(citations_history[-4:])
            older_avg = np.mean(citations_history[:-4]) if len(citations_history) > 4 else recent_avg / 2
            
            if older_avg > 0 and recent_avg > older_avg * 1.5:
                # Exponential growth detected!
                return 1.0
            
            # Calculate growth rate
            if older_avg > 0:
                growth_rate = (recent_avg - older_avg) / older_avg
                growth_score = min(growth_rate / 2, 1.0)  # 200% growth = max score
            else:
                growth_score = min(recent_avg / 10, 1.0)
        else:
            growth_score = 0.0
        
        # Field-normalized velocity score
        if field_stats.paper_count > 0:
            velocity_percentile = self._percentile_rank(velocity, field_stats.velocity_percentiles)
        else:
            # Fallback to baseline
            baseline = self.FIELD_CITATION_BASELINES.get(
                paper.primary_category,
                self.FIELD_CITATION_BASELINES["default"]
            )
            velocity_percentile = min(velocity / baseline, 1.0)
        
        # Combine growth detection and velocity percentile
        return (growth_score * 0.4) + (velocity_percentile * 0.6)
    
    async def _get_citation_history(self, paper: Paper) -> List[int]:
        """Get weekly citation counts for trend analysis."""
        cache_key = f"citation_history:{paper.id}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        # For now, return empty list (would need historical data storage)
        # In production, this would query a time-series database
        return []
    
    async def _calculate_implementation_quality(self, paper: Paper) -> float:
        """
        Calculate implementation quality beyond just GitHub stars.
        
        Considers: tests, documentation, commit frequency, issue resolution.
        """
        if not paper.implementations:
            return 0.0
        
        scores = []
        for impl in paper.implementations:
            quality_signals = {}
            
            # Star score (logarithmic, capped)
            if impl.stars:
                quality_signals["stars"] = min(math.log10(impl.stars + 1) / 4, 1.0)
            else:
                quality_signals["stars"] = 0.0
            
            # Recency of updates
            if impl.last_updated:
                days_since_update = (datetime.now() - impl.last_updated).days
                quality_signals["activity"] = max(0, 1.0 - (days_since_update / 180))
            else:
                quality_signals["activity"] = 0.3  # Default for unknown
            
            # Language bonus (Python implementations are often more accessible)
            language_bonus = {
                "Python": 0.2,
                "Jupyter Notebook": 0.15,
                "PyTorch": 0.2,
            }
            quality_signals["language"] = language_bonus.get(impl.language, 0.1)
            
            # Check for quality indicators (async would query GitHub API)
            quality_indicators = await self._check_repo_quality(impl)
            quality_signals.update(quality_indicators)
            
            # Weight the signals
            weights = {
                "stars": 0.3,
                "activity": 0.2,
                "language": 0.1,
                "has_tests": 0.15,
                "has_docs": 0.15,
                "issue_resolution": 0.1,
            }
            
            impl_score = sum(
                quality_signals.get(k, 0) * v
                for k, v in weights.items()
            )
            scores.append(impl_score)
        
        return max(scores) if scores else 0.0
    
    async def _check_repo_quality(self, impl: PaperImplementation) -> Dict[str, float]:
        """Check repository quality indicators (tests, docs, etc.)."""
        # Check cache first
        cache_key = f"repo_quality:{impl.repo_url}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        # Default quality indicators
        # In production, would query GitHub API
        quality = {
            "has_tests": 0.5,  # Assume average
            "has_docs": 0.5,
            "issue_resolution": 0.5,
        }
        
        # Cache for 24 hours
        cache.set(cache_key, quality, ttl_seconds=86400)
        return quality
    
    async def _calculate_author_credibility(self, paper: Paper) -> float:
        """
        Calculate author credibility score.
        
        Based on h-index, affiliations, and publication history.
        """
        # Check cache
        cache_key = f"author_credibility:{paper.id}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        if not paper.authors:
            return 0.3  # Default for unknown
        
        # Simple heuristic based on author count and affiliations
        author_count = len(paper.authors) if isinstance(paper.authors, list) else 1
        
        # More authors from diverse institutions often indicates collaboration
        collaboration_score = min(author_count / 5, 1.0) * 0.3
        
        # Check for known affiliations (simplified)
        affiliation_score = 0.5  # Default
        
        total = collaboration_score + (affiliation_score * 0.7)
        
        # Cache for 7 days
        cache.set(cache_key, total, ttl_seconds=604800)
        return total
    
    async def _calculate_novelty(self, paper: Paper, field_stats: FieldStats) -> float:
        """
        Calculate novelty score - how different is this from existing work.
        
        Uses semantic similarity to recent papers (lower similarity = more novel).
        """
        # Check cache
        cache_key = f"novelty:{paper.id}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        # Get paper embedding if available
        # In production, would use sentence-transformers
        embedding = await self._get_paper_embedding(paper)
        
        if embedding is not None:
            # Compare to recent papers in the field
            recent_embeddings = await self._get_recent_paper_embeddings(
                paper.primary_category,
                exclude_id=paper.id
            )
            
            if recent_embeddings:
                similarities = [
                    self._cosine_similarity(embedding, e)
                    for e in recent_embeddings
                ]
                avg_similarity = np.mean(similarities)
                novelty_score = 1.0 - avg_similarity
            else:
                novelty_score = 0.5
        else:
            # Fallback: keyword-based novelty
            novelty_score = await self._keyword_novelty(paper)
        
        # Cache for 24 hours
        cache.set(cache_key, novelty_score, ttl_seconds=86400)
        return novelty_score
    
    async def _get_paper_embedding(self, paper: Paper) -> Optional[np.ndarray]:
        """Get paper embedding from cache or generate."""
        cache_key = f"embedding:{paper.id}"
        cached = cache.get(cache_key)
        if cached:
            return np.array(cached)
        return None  # Would generate with embedding service
    
    async def _get_recent_paper_embeddings(
        self,
        category: str,
        exclude_id: str,
        limit: int = 100
    ) -> List[np.ndarray]:
        """Get embeddings for recent papers in category."""
        # Would fetch from vector database
        return []
    
    async def _keyword_novelty(self, paper: Paper) -> float:
        """Fallback novelty calculation using keywords."""
        # Simple heuristic based on abstract length and unique terms
        abstract_words = set(paper.abstract.lower().split())
        common_ml_terms = {
            "neural", "network", "learning", "model", "training",
            "data", "loss", "optimization", "gradient", "feature",
        }
        unique_ratio = len(abstract_words - common_ml_terms) / max(len(abstract_words), 1)
        return min(unique_ratio * 2, 1.0)
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
    
    def _calculate_reproducibility(self, paper: Paper) -> float:
        """Calculate reproducibility score."""
        score = 0.0
        
        # Has code implementation
        if paper.implementations:
            score += 0.5
        
        # Has methodology in summary
        if paper.summary and paper.summary.methodology:
            score += 0.25
        
        # Has results/experiments
        if paper.summary and paper.summary.results_summary:
            score += 0.25
        
        return score
    
    def _calculate_community_engagement(self, metrics: Optional[PaperMetrics]) -> float:
        """Calculate community engagement score."""
        if not metrics:
            return 0.0
        
        # Social score (normalized)
        social = min(metrics.social_score / 100, 1.0) * 0.5
        
        # GitHub engagement
        github = min(math.log10(metrics.github_stars + 1) / 4, 1.0) * 0.5 if metrics.github_stars else 0.0
        
        return social + github
    
    def _calculate_recency(self, published_date: date, max_days: int = 90) -> float:
        """Calculate recency score with smooth decay."""
        days_ago = (date.today() - published_date).days
        if days_ago >= max_days:
            return 0.0
        
        # Smooth exponential decay instead of linear
        decay_rate = 0.03  # ~50% at 23 days
        return math.exp(-decay_rate * days_ago)
    
    def _calculate_freshness_boost(
        self,
        days_old: int,
        metrics: Optional[PaperMetrics]
    ) -> float:
        """
        Calculate adaptive freshness boost.
        
        Less aggressive than before to prevent low-quality preprint promotion.
        """
        if days_old > 30:
            return 1.0  # No boost for older papers
        
        # Base boost for fresh papers
        base_boost = 1.0 + (1 - days_old / 30) * 0.5  # Max 1.5x for day 0
        
        # Reduce boost if paper has no traction
        if metrics:
            if metrics.citation_count == 0 and metrics.github_stars == 0:
                # No traction yet - minimal boost to avoid promoting low-quality
                return min(base_boost, 1.1)
            
            # Has some traction - allow moderate boost
            traction_score = min(
                (metrics.citation_count / 5 + metrics.github_stars / 50),
                1.0
            )
            return 1.0 + (base_boost - 1.0) * traction_score
        
        return 1.0  # No boost without metrics
    
    def _calculate_field_percentile(
        self,
        citation_count: int,
        velocity: int,
        field_stats: FieldStats
    ) -> float:
        """Calculate combined field percentile."""
        if field_stats.paper_count == 0:
            return 0.5
        
        citation_percentile = self._percentile_rank(
            citation_count,
            field_stats.citation_percentiles
        )
        velocity_percentile = self._percentile_rank(
            velocity,
            field_stats.velocity_percentiles
        )
        
        return (citation_percentile * 0.4) + (velocity_percentile * 0.6)
    
    def _percentile_rank(self, value: float, percentiles: List[float]) -> float:
        """Get percentile rank of a value."""
        if not percentiles:
            return 0.5
        
        for i, p in enumerate(percentiles):
            if value <= p:
                return i / 100
        return 1.0


async def calculate_field_normalized_scores(db: Session, days_back: int = 90) -> Dict[str, int]:
    """
    Calculate field-normalized ranking scores for all recent papers.
    
    This is the main entry point for the ranking job.
    """
    stats = {
        "processed": 0,
        "updated": 0,
        "errors": 0,
    }
    
    engine = AdvancedRankingEngine(db)
    cutoff = date.today() - timedelta(days=days_back)
    
    papers = (
        db.query(Paper)
        .filter(Paper.published_date >= cutoff)
        .all()
    )
    
    logger.info(f"Calculating advanced ranking scores for {len(papers)} papers")
    
    for paper in papers:
        stats["processed"] += 1
        
        try:
            # Get or create metrics
            metrics = paper.metrics
            if not metrics:
                metrics = PaperMetrics(paper_id=paper.id)
                db.add(metrics)
                db.flush()
            
            # Calculate advanced score
            breakdown = await engine.calculate_paper_score(paper, metrics)
            
            # Update metrics
            metrics.overall_rank_score = breakdown.total_score
            stats["updated"] += 1
            
            # Log high-scoring papers
            if breakdown.total_score > 0.8:
                logger.info(
                    f"High-scoring paper: {paper.arxiv_id}",
                    score=breakdown.total_score,
                    momentum=breakdown.citation_momentum,
                    novelty=breakdown.novelty,
                )
            
        except Exception as e:
            logger.warning(f"Error calculating score for {paper.arxiv_id}: {e}")
            stats["errors"] += 1
    
    db.commit()
    logger.info(f"Advanced ranking calculation complete: {stats}")
    return stats
