"""
Daily arXiv ingestion job.
Fetches new papers from arXiv and stores them in the database.
"""
import asyncio
from datetime import date, timedelta
from typing import List, Dict, Any

from loguru import logger
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.models import Paper, PaperMetrics
from app.services.arxiv_service import arxiv_service

# Initialize logging
setup_logging()

settings = get_settings()


async def ingest_arxiv_papers(
    categories: List[str] | None = None,
    days_back: int = 1,
    max_per_category: int = 200,
) -> Dict[str, int]:
    """
    Ingest recent papers from arXiv.

    Args:
        categories: List of arXiv categories to fetch
        days_back: Number of days to look back
        max_per_category: Max papers per category

    Returns:
        Statistics dict with counts
    """
    if categories is None:
        categories = settings.arxiv_categories

    stats = {
        "total_fetched": 0,
        "new_papers": 0,
        "updated_papers": 0,
        "errors": 0,
    }

    db = SessionLocal()

    try:
        for category in categories:
            logger.info("Fetching papers", category=category)

            try:
                papers = await arxiv_service.fetch_recent_papers(
                    category=category,
                    max_results=max_per_category,
                    days_back=days_back,
                )

                stats["total_fetched"] += len(papers)
                logger.info("Fetched papers", category=category, count=len(papers))

                # Process papers in batches
                batch_size = 50
                for i in range(0, len(papers), batch_size):
                    batch = papers[i : i + batch_size]
                    batch_stats = _process_paper_batch(db, batch)
                    stats["new_papers"] += batch_stats["new"]
                    stats["updated_papers"] += batch_stats["updated"]
                    stats["errors"] += batch_stats["errors"]

            except Exception as e:
                logger.error("Error fetching category", category=category, error=str(e))
                stats["errors"] += 1

        logger.info("Ingestion complete", **stats)
        return stats

    finally:
        db.close()


def _process_paper_batch(
    db: Session,
    papers: List[Dict[str, Any]],
) -> Dict[str, int]:
    """Process a batch of papers."""
    stats = {"new": 0, "updated": 0, "errors": 0}

    for paper_data in papers:
        try:
            arxiv_id = paper_data["arxiv_id"]

            # Check if paper exists
            existing = db.query(Paper).filter(Paper.arxiv_id == arxiv_id).first()

            if existing:
                # Update if updated_date is newer
                if paper_data.get("updated_date") and existing.updated_date:
                    if paper_data["updated_date"] > existing.updated_date:
                        _update_paper(existing, paper_data)
                        stats["updated"] += 1
            else:
                # Create new paper
                paper = Paper(
                    arxiv_id=arxiv_id,
                    title=paper_data["title"],
                    abstract=paper_data["abstract"],
                    authors=paper_data["authors"],
                    published_date=paper_data["published_date"],
                    updated_date=paper_data.get("updated_date"),
                    primary_category=paper_data["primary_category"],
                    categories=paper_data["categories"],
                    pdf_url=paper_data["pdf_url"],
                    arxiv_url=paper_data["arxiv_url"],
                    doi=paper_data.get("doi"),
                    journal_ref=paper_data.get("journal_ref"),
                    comments=paper_data.get("comments"),
                )
                db.add(paper)
                db.flush()  # Get the ID

                # Create metrics record
                metrics = PaperMetrics(paper_id=paper.id)
                db.add(metrics)

                stats["new"] += 1

        except Exception as e:
            logger.warning(
                "Error processing paper",
                arxiv_id=paper_data.get("arxiv_id"),
                error=str(e),
            )
            stats["errors"] += 1

    db.commit()
    return stats


def _update_paper(paper: Paper, data: Dict[str, Any]):
    """Update existing paper with new data."""
    paper.title = data["title"]
    paper.abstract = data["abstract"]
    paper.authors = data["authors"]
    paper.updated_date = data.get("updated_date")
    paper.categories = data["categories"]
    paper.comments = data.get("comments")


async def main():
    """Run the ingestion job."""
    logger.info("Starting arXiv ingestion job")
    # Use 7 days back to get more papers initially
    stats = await ingest_arxiv_papers(days_back=7)
    logger.info("Job completed", **stats)


if __name__ == "__main__":
    asyncio.run(main())
