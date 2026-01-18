"""
Semantic Scholar enrichment job.
Fetches citation data and enriches papers with Semantic Scholar information.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict

from loguru import logger
from sqlalchemy import or_

from app.core.database import SessionLocal
from app.core.logging import setup_logging
from app.models import Paper, PaperMetrics
from app.services.semantic_scholar_service import semantic_scholar_service

# Initialize logging
setup_logging()


def utcnow():
    """Get current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


async def enrich_papers_with_semantic_scholar(
    limit: int = 500,
    update_existing: bool = True,
) -> Dict[str, int]:
    """
    Enrich papers with Semantic Scholar data.

    Args:
        limit: Maximum papers to process
        update_existing: Whether to update papers that already have S2 data

    Returns:
        Statistics dict
    """
    stats = {
        "processed": 0,
        "enriched": 0,
        "not_found": 0,
        "updated": 0,
        "errors": 0,
        "skipped_rate_limit": 0,
    }

    db = SessionLocal()

    try:
        # Get papers to enrich
        query = db.query(Paper)

        if not update_existing:
            # Only papers without Semantic Scholar ID
            query = query.filter(Paper.semantic_scholar_id.is_(None))
        else:
            # Include papers that haven't been updated in 24 hours
            cutoff = utcnow() - timedelta(hours=24)
            query = query.outerjoin(PaperMetrics).filter(
                or_(
                    Paper.semantic_scholar_id.is_(None),
                    PaperMetrics.last_metrics_update < cutoff,
                    PaperMetrics.last_metrics_update.is_(None),
                )
            )

        # Prioritize recent papers
        papers = query.order_by(Paper.published_date.desc()).limit(limit).all()

        logger.info("Processing papers for S2 enrichment", count=len(papers))

        for paper in papers:
            stats["processed"] += 1

            try:
                # Get paper details from Semantic Scholar
                s2_data = await semantic_scholar_service.get_paper_details(paper.arxiv_id)

                if s2_data is None:
                    stats["not_found"] += 1
                    continue
                
                # Check if we got rate limited (returns empty dict)
                if s2_data == "RATE_LIMITED":
                    stats["skipped_rate_limit"] += 1
                    logger.warning("Rate limited, stopping enrichment early")
                    break

                # Update paper with S2 ID
                if not paper.semantic_scholar_id:
                    paper.semantic_scholar_id = s2_data.get("paperId")
                    stats["enriched"] += 1
                else:
                    stats["updated"] += 1

                # Update metrics
                metrics = paper.metrics
                if not metrics:
                    metrics = PaperMetrics(paper_id=paper.id)
                    db.add(metrics)

                metrics.citation_count = s2_data.get("citationCount", 0)

                # Calculate citation velocity if we have the paper ID
                if s2_data.get("paperId"):
                    velocity = await semantic_scholar_service.get_citation_velocity(
                        s2_data["paperId"]
                    )
                    metrics.citation_velocity_7d = velocity

                metrics.last_metrics_update = utcnow()

                # Commit periodically to avoid large transactions
                if stats["processed"] % 50 == 0:
                    db.commit()
                    logger.info("Progress", processed=stats["processed"])

            except Exception as e:
                logger.warning(
                    "Error enriching paper",
                    arxiv_id=paper.arxiv_id,
                    error=str(e),
                )
                stats["errors"] += 1

        db.commit()
        logger.info("Enrichment complete", **stats)
        return stats

    finally:
        db.close()


async def main():
    """Run the enrichment job."""
    logger.info("Starting Semantic Scholar enrichment job")
    stats = await enrich_papers_with_semantic_scholar(limit=500)
    logger.info("Job completed", **stats)


if __name__ == "__main__":
    asyncio.run(main())
