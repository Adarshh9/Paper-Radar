"""
Unified data pipeline for Paper Radar.
Runs ingestion, enrichment, and ranking in sequence with proper error handling.

Usage:
    uv run python -m scripts.run_pipeline          # Run full pipeline
    uv run python -m scripts.run_pipeline --quick  # Quick mode (fewer papers)
    uv run python -m scripts.run_pipeline --init   # Initialize database first
"""
import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from loguru import logger

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings
from app.core.database import init_db, SessionLocal
from app.core.logging import setup_logging
from app.models import Paper, PaperMetrics

settings = get_settings()


def utcnow():
    """Get current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


async def run_ingestion(days_back: int = 7, max_per_category: int = 200) -> Dict[str, Any]:
    """Run arXiv paper ingestion."""
    from scripts.ingest_arxiv_daily import ingest_arxiv_papers
    
    logger.info("=" * 60)
    logger.info("STAGE 1: Paper Ingestion from arXiv")
    logger.info("=" * 60)
    
    try:
        stats = await ingest_arxiv_papers(
            days_back=days_back,
            max_per_category=max_per_category,
        )
        logger.info("Ingestion complete", **stats)
        return stats
    except Exception as e:
        logger.error("Ingestion failed", error=str(e))
        return {"error": str(e)}


async def run_semantic_scholar_enrichment(limit: int = 100) -> Dict[str, Any]:
    """Run Semantic Scholar citation enrichment."""
    from scripts.enrich_semantic_scholar import enrich_papers_with_semantic_scholar
    
    logger.info("=" * 60)
    logger.info("STAGE 2: Semantic Scholar Enrichment")
    logger.info("=" * 60)
    
    try:
        stats = await enrich_papers_with_semantic_scholar(
            limit=limit,
            update_existing=False,  # Only enrich new papers to avoid rate limits
        )
        logger.info("S2 Enrichment complete", **stats)
        return stats
    except Exception as e:
        logger.error("S2 Enrichment failed", error=str(e))
        return {"error": str(e)}


async def run_github_discovery(limit: int = 50) -> Dict[str, Any]:
    """Run GitHub implementation discovery."""
    logger.info("=" * 60)
    logger.info("STAGE 3: GitHub Implementation Discovery")
    logger.info("=" * 60)
    
    try:
        # Import and run discover_implementations
        from scripts.discover_implementations import discover_implementations
        stats = await discover_implementations(limit=limit)
        logger.info("GitHub discovery complete", **stats)
        return stats
    except ImportError:
        logger.warning("GitHub discovery script not available, skipping")
        return {"skipped": True}
    except Exception as e:
        logger.error("GitHub discovery failed", error=str(e))
        return {"error": str(e)}


async def run_summary_generation(limit: int = 20) -> Dict[str, Any]:
    """Run AI summary generation."""
    logger.info("=" * 60)
    logger.info("STAGE 4: AI Summary Generation")
    logger.info("=" * 60)
    
    if not settings.groq_api_key:
        logger.warning("GROQ_API_KEY not set, skipping summary generation")
        return {"skipped": True, "reason": "No API key"}
    
    try:
        from scripts.generate_summaries import generate_summaries
        stats = await generate_summaries(limit=limit)
        logger.info("Summary generation complete", **stats)
        return stats
    except ImportError:
        logger.warning("Summary generation script not available, skipping")
        return {"skipped": True}
    except Exception as e:
        logger.error("Summary generation failed", error=str(e))
        return {"error": str(e)}


def run_ranking_calculation() -> Dict[str, Any]:
    """Calculate ranking scores for all papers."""
    logger.info("=" * 60)
    logger.info("STAGE 5: Ranking Score Calculation")
    logger.info("=" * 60)
    
    try:
        from scripts.calculate_ranking_scores import calculate_ranking_scores
        stats = calculate_ranking_scores()
        logger.info("Ranking calculation complete", **stats)
        return stats
    except ImportError:
        # Implement basic ranking inline
        logger.info("Running basic ranking calculation...")
        return calculate_basic_ranking()
    except Exception as e:
        logger.error("Ranking calculation failed", error=str(e))
        return {"error": str(e)}


def calculate_basic_ranking() -> Dict[str, int]:
    """Basic ranking calculation when the full script is not available."""
    from datetime import date, timedelta
    
    db = SessionLocal()
    stats = {"updated": 0}
    
    try:
        papers = db.query(Paper).all()
        today = date.today()
        
        for paper in papers:
            metrics = paper.metrics
            if not metrics:
                metrics = PaperMetrics(paper_id=paper.id)
                db.add(metrics)
            
            # Calculate age in days
            age_days = (today - paper.published_date).days
            
            # Freshness boost (papers < 7 days get 3x, < 30 days get 1.5x)
            if age_days < 7:
                freshness_multiplier = 3.0
            elif age_days < 30:
                freshness_multiplier = 1.5
            else:
                freshness_multiplier = 1.0
            
            # Base score from citations (log scale)
            import math
            citation_score = math.log10(metrics.citation_count + 1) * 10
            
            # Velocity bonus
            velocity_score = metrics.citation_velocity_7d * 2
            
            # Implementation bonus
            impl_score = 20 if paper.implementations else 0
            
            # GitHub stars bonus
            stars_score = min(metrics.github_stars / 10, 20)
            
            # Calculate overall score
            raw_score = citation_score + velocity_score + impl_score + stars_score
            metrics.overall_rank_score = raw_score * freshness_multiplier
            
            stats["updated"] += 1
        
        db.commit()
        logger.info("Basic ranking complete", **stats)
        return stats
    finally:
        db.close()


def get_database_stats() -> Dict[str, int]:
    """Get current database statistics."""
    db = SessionLocal()
    try:
        from app.models import PaperSummary
        return {
            "total_papers": db.query(Paper).count(),
            "papers_with_citations": db.query(Paper).join(PaperMetrics).filter(
                PaperMetrics.citation_count > 0
            ).count(),
            "papers_with_implementations": db.query(Paper).filter(
                Paper.implementations.any()
            ).count(),
            "papers_with_summaries": db.query(PaperSummary).count(),
        }
    finally:
        db.close()


async def main():
    """Run the full data pipeline."""
    parser = argparse.ArgumentParser(description="Paper Radar Data Pipeline")
    parser.add_argument(
        "--quick", action="store_true",
        help="Quick mode - process fewer papers"
    )
    parser.add_argument(
        "--init", action="store_true",
        help="Initialize database before running pipeline"
    )
    parser.add_argument(
        "--skip-enrichment", action="store_true",
        help="Skip Semantic Scholar enrichment (to avoid rate limits)"
    )
    parser.add_argument(
        "--skip-summaries", action="store_true",
        help="Skip AI summary generation"
    )
    parser.add_argument(
        "--days-back", type=int, default=7,
        help="Number of days to fetch papers for (default: 7)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    
    logger.info("=" * 60)
    logger.info("PAPER RADAR DATA PIPELINE")
    logger.info(f"Mode: {'Quick' if args.quick else 'Full'}")
    logger.info(f"Using local storage: {settings.use_local_storage}")
    logger.info(f"Data directory: {settings.data_directory}")
    logger.info("=" * 60)
    
    # Initialize database if requested or if using local storage
    if args.init or settings.use_local_storage:
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized")
    
    # Set limits based on mode
    if args.quick:
        ingestion_max = 50
        enrichment_limit = 30
        github_limit = 20
        summary_limit = 10
    else:
        ingestion_max = 200
        enrichment_limit = 100
        github_limit = 50
        summary_limit = 30
    
    start_time = utcnow()
    results = {}
    
    # Stage 1: Ingestion
    results["ingestion"] = await run_ingestion(
        days_back=args.days_back,
        max_per_category=ingestion_max,
    )
    
    # Stage 2: Semantic Scholar Enrichment (optional)
    if not args.skip_enrichment:
        results["enrichment"] = await run_semantic_scholar_enrichment(
            limit=enrichment_limit,
        )
    else:
        logger.info("Skipping Semantic Scholar enrichment")
        results["enrichment"] = {"skipped": True}
    
    # Stage 3: GitHub Discovery
    results["github"] = await run_github_discovery(limit=github_limit)
    
    # Stage 4: Summary Generation (optional)
    if not args.skip_summaries:
        results["summaries"] = await run_summary_generation(limit=summary_limit)
    else:
        logger.info("Skipping summary generation")
        results["summaries"] = {"skipped": True}
    
    # Stage 5: Ranking
    results["ranking"] = run_ranking_calculation()
    
    # Final summary
    end_time = utcnow()
    duration = (end_time - start_time).total_seconds()
    
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info(f"Duration: {duration:.1f} seconds")
    logger.info("=" * 60)
    
    # Show database stats
    stats = get_database_stats()
    logger.info("Database Statistics:")
    logger.info(f"  Total papers: {stats['total_papers']}")
    logger.info(f"  With citations: {stats['papers_with_citations']}")
    logger.info(f"  With implementations: {stats['papers_with_implementations']}")
    logger.info(f"  With summaries: {stats['papers_with_summaries']}")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())
