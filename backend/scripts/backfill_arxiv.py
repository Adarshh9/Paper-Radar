"""
Backfill script for bulk arXiv paper ingestion.
Allows fetching papers from a specified time range (e.g., last 3 months).

Usage:
    uv run python -m scripts.backfill_arxiv --months 3
    uv run python -m scripts.backfill_arxiv --days 90
    uv run python -m scripts.backfill_arxiv --start 2025-10-01 --end 2025-12-31
"""
import argparse
import asyncio
from datetime import date, datetime, timedelta
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


async def backfill_papers(
    start_date: date,
    end_date: date,
    categories: List[str] | None = None,
    max_per_category: int = 1000,
    batch_delay: float = 3.0,
) -> Dict[str, int]:
    """
    Backfill papers from arXiv for a date range.
    
    Args:
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)
        categories: List of arXiv categories to fetch
        max_per_category: Maximum papers to fetch per category
        batch_delay: Delay between API calls in seconds
        
    Returns:
        Statistics dict
    """
    if categories is None:
        categories = settings.arxiv_categories
    
    stats = {
        "total_fetched": 0,
        "new_papers": 0,
        "existing_papers": 0,
        "errors": 0,
    }
    
    db = SessionLocal()
    
    try:
        logger.info(f"Starting backfill from {start_date} to {end_date}")
        logger.info(f"Categories: {categories}")
        
        for category in categories:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing category: {category}")
            logger.info(f"{'='*60}")
            
            try:
                # Fetch papers for date range
                papers = await arxiv_service.fetch_papers_by_date_range(
                    start_date=start_date,
                    end_date=end_date,
                    category=category,
                    max_results=max_per_category,
                )
                
                stats["total_fetched"] += len(papers)
                logger.info(f"Fetched {len(papers)} papers from {category}")
                
                # Process papers in batches
                batch_size = 50
                for i in range(0, len(papers), batch_size):
                    batch = papers[i : i + batch_size]
                    batch_stats = _process_paper_batch(db, batch)
                    
                    stats["new_papers"] += batch_stats["new"]
                    stats["existing_papers"] += batch_stats["existing"]
                    stats["errors"] += batch_stats["errors"]
                    
                    logger.info(f"  Batch {i//batch_size + 1}: +{batch_stats['new']} new, {batch_stats['existing']} existing")
                
                # Rate limit between categories
                await asyncio.sleep(batch_delay)
                
            except Exception as e:
                logger.error(f"Error processing category {category}: {e}")
                stats["errors"] += 1
        
        logger.info(f"\n{'='*60}")
        logger.info("BACKFILL COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Total fetched: {stats['total_fetched']}")
        logger.info(f"New papers added: {stats['new_papers']}")
        logger.info(f"Already existing: {stats['existing_papers']}")
        logger.info(f"Errors: {stats['errors']}")
        
        return stats
        
    finally:
        db.close()


def _process_paper_batch(
    db: Session,
    papers: List[Dict[str, Any]],
) -> Dict[str, int]:
    """Process a batch of papers."""
    stats = {"new": 0, "existing": 0, "errors": 0}
    
    for paper_data in papers:
        try:
            arxiv_id = paper_data["arxiv_id"]
            
            # Check if paper exists
            existing = db.query(Paper).filter(Paper.arxiv_id == arxiv_id).first()
            
            if existing:
                stats["existing"] += 1
                continue
            
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
            db.flush()
            
            # Create metrics record
            metrics = PaperMetrics(paper_id=paper.id)
            db.add(metrics)
            
            stats["new"] += 1
            
        except Exception as e:
            logger.warning(f"Error processing paper {paper_data.get('arxiv_id')}: {e}")
            stats["errors"] += 1
    
    db.commit()
    return stats


def parse_date(date_str: str) -> date:
    """Parse date string in YYYY-MM-DD format."""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


async def main():
    parser = argparse.ArgumentParser(
        description="Backfill arXiv papers for a specified time range"
    )
    
    # Time range options
    parser.add_argument(
        "--months", type=int, default=None,
        help="Number of months to look back (e.g., --months 3 for last 3 months)"
    )
    parser.add_argument(
        "--days", type=int, default=None,
        help="Number of days to look back (e.g., --days 90)"
    )
    parser.add_argument(
        "--start", type=str, default=None,
        help="Start date in YYYY-MM-DD format"
    )
    parser.add_argument(
        "--end", type=str, default=None,
        help="End date in YYYY-MM-DD format (defaults to today)"
    )
    
    # Other options
    parser.add_argument(
        "--categories", type=str, nargs="+", default=None,
        help="Categories to fetch (e.g., --categories cs.AI cs.LG)"
    )
    parser.add_argument(
        "--max-per-category", type=int, default=1000,
        help="Maximum papers per category (default: 1000)"
    )
    
    args = parser.parse_args()
    
    # Determine date range
    end_date = date.today()
    
    if args.end:
        end_date = parse_date(args.end)
    
    if args.start:
        start_date = parse_date(args.start)
    elif args.months:
        start_date = end_date - timedelta(days=args.months * 30)
    elif args.days:
        start_date = end_date - timedelta(days=args.days)
    else:
        # Default to last 30 days
        start_date = end_date - timedelta(days=30)
    
    logger.info("="*60)
    logger.info("ARXIV BACKFILL SCRIPT")
    logger.info("="*60)
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Categories: {args.categories or settings.arxiv_categories}")
    logger.info(f"Max per category: {args.max_per_category}")
    logger.info("")
    
    await backfill_papers(
        start_date=start_date,
        end_date=end_date,
        categories=args.categories,
        max_per_category=args.max_per_category,
    )


if __name__ == "__main__":
    asyncio.run(main())
