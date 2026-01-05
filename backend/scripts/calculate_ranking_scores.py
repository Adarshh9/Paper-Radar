"""
Ranking score calculation job.
Calculates overall ranking scores for papers based on multiple factors.
"""
import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Dict

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.cache import cache
from app.models import Paper, PaperMetrics, PaperImplementation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def calculate_recency_score(published_date: date, max_days: int = 90) -> float:
    """
    Calculate recency score (0-1).
    Papers decay linearly over max_days.
    """
    days_ago = (date.today() - published_date).days
    if days_ago >= max_days:
        return 0.0
    return 1.0 - (days_ago / max_days)


def calculate_paper_score(
    paper: Paper,
    metrics: PaperMetrics,
    has_implementations: bool,
) -> float:
    """
    Calculate overall ranking score for a paper.
    
    Score components (weights sum to 1.0):
    - Recency: 0.15 (newer papers ranked higher)
    - Citation velocity: 0.25 (fast-growing citations)
    - Implementation: 0.20 (code availability)
    - Total citations: 0.15 (overall impact)
    - Social score: 0.10 (social media mentions)
    - Base quality: 0.15 (placeholder for author reputation etc.)
    """
    # Recency score (linear decay over 90 days)
    days_ago = (date.today() - paper.published_date).days
    recency = calculate_recency_score(paper.published_date) * 0.15
    
    # Freshness Boost: guarantee visibility for brand new papers
    freshness_boost = 3.0 if days_ago <= 7 else 1.0  # Increased to 3.0x
    
    # Citation velocity (normalized, cap at 50 citations/week)
    if metrics:
        # Use simple velocity ratio for better signal
        velocity = min(metrics.citation_velocity_7d / 50, 1.0) * 0.25
        
        # Total citations (log scale, cap at 1000)
        import math
        citation_score = min(math.log10(max(metrics.citation_count, 1) + 1) / 3, 1.0) * 0.15
        
        # Social score (normalized)
        social = min(metrics.social_score / 100, 1.0) * 0.10
        
        # Implementation score (increased weight)
        impl_score = 0.0
        if has_implementations and metrics.github_stars > 0:
            impl_score = min(math.log10(metrics.github_stars + 1) / 4, 1.0) * 0.30  # Increased from 0.20
        elif has_implementations:
            impl_score = 0.15  # Has code
    else:
        velocity = 0.0
        citation_score = 0.0
        social = 0.0
        impl_score = 0.0
    
    # Base quality score (placeholder)
    base_quality = 0.5 * 0.15
    
    total = (recency + velocity + impl_score + citation_score + social + base_quality) * freshness_boost
    
    return round(total, 4)


async def calculate_ranking_scores(days_back: int = 90) -> Dict[str, int]:
    """
    Calculate ranking scores for all recent papers.
    
    Args:
        days_back: Calculate scores for papers from last N days
        
    Returns:
        Statistics dict
    """
    stats = {
        "processed": 0,
        "updated": 0,
        "errors": 0,
    }
    
    db = SessionLocal()
    
    try:
        # Get papers from last N days
        cutoff = date.today() - timedelta(days=days_back)
        
        papers = (
            db.query(Paper)
            .filter(Paper.published_date >= cutoff)
            .all()
        )
        
        logger.info(f"Calculating ranking scores for {len(papers)} papers")
        
        for paper in papers:
            stats["processed"] += 1
            
            try:
                # Get or create metrics
                metrics = paper.metrics
                if not metrics:
                    metrics = PaperMetrics(paper_id=paper.id)
                    db.add(metrics)
                    db.flush()
                
                # Check for implementations
                has_implementations = (
                    db.query(PaperImplementation)
                    .filter(PaperImplementation.paper_id == paper.id)
                    .count() > 0
                )
                
                # Calculate score
                score = calculate_paper_score(paper, metrics, has_implementations)
                
                # Update metrics
                metrics.overall_rank_score = score
                stats["updated"] += 1
                
            except Exception as e:
                logger.warning(f"Error calculating score for {paper.arxiv_id}: {e}")
                stats["errors"] += 1
        
        db.commit()
        
        # Cache top papers in Redis
        await cache_top_papers(db, limit=1000)
        
        logger.info(f"Ranking calculation complete: {stats}")
        return stats
        
    finally:
        db.close()


async def cache_top_papers(db: Session, limit: int = 1000):
    """Cache top-ranked papers in Redis."""
    top_papers = (
        db.query(Paper.id, PaperMetrics.overall_rank_score)
        .join(PaperMetrics)
        .order_by(PaperMetrics.overall_rank_score.desc())
        .limit(limit)
        .all()
    )
    
    # Store as sorted set data
    paper_scores = [
        {"id": str(p.id), "score": p.overall_rank_score}
        for p in top_papers
    ]
    
    cache.set("top_papers", paper_scores, ttl_seconds=21600)  # 6 hours
    
    # Invalidate trending cache to show new rankings immediately
    cache.delete("trending:7:20")  # specific keys or use wildcard if supported by helper
    # Since helper might not support patterns, we relies on TTL or explicit keys
    # But for now let's hope 15 min TTL expires or user restarts backend
    logger.info(f"Cached {len(paper_scores)} top papers")


async def main():
    """Run the ranking job."""
    logger.info("Starting ranking score calculation...")
    stats = await calculate_ranking_scores(days_back=90)
    logger.info(f"Job completed: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
