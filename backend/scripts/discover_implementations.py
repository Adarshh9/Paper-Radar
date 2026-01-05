"""
GitHub implementation discovery job.
Searches GitHub for repositories implementing papers.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Paper, PaperMetrics, PaperImplementation
from app.services.github_service import github_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def discover_implementations(
    days_back: int = 7,
    limit: int = 200,
) -> Dict[str, int]:
    """
    Discover GitHub implementations for recent papers.
    
    Args:
        days_back: Look for papers from last N days
        limit: Maximum papers to process
        
    Returns:
        Statistics dict
    """
    stats = {
        "processed": 0,
        "found": 0,
        "repos_added": 0,
        "errors": 0,
    }
    
    db = SessionLocal()
    
    try:
        # Get recent papers without implementations
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        
        # Papers with no implementations
        papers_without_impl = (
            db.query(Paper)
            .outerjoin(PaperImplementation)
            .filter(
                Paper.published_date >= cutoff.date(),
                PaperImplementation.id.is_(None),
            )
            .order_by(Paper.published_date.desc())
            .limit(limit)
            .all()
        )
        
        logger.info(f"Searching implementations for {len(papers_without_impl)} papers")
        
        for paper in papers_without_impl:
            stats["processed"] += 1
            
            try:
                # Search GitHub
                repos = await github_service.search_repos_by_paper(
                    arxiv_id=paper.arxiv_id,
                    paper_title=paper.title,
                )
                
                if repos:
                    stats["found"] += 1
                    
                    for repo in repos:
                        # Check if repo already exists
                        existing = db.query(PaperImplementation).filter(
                            PaperImplementation.paper_id == paper.id,
                            PaperImplementation.repo_url == repo["repo_url"],
                        ).first()
                        
                        if not existing:
                            impl = PaperImplementation(
                                paper_id=paper.id,
                                source="github",
                                repo_url=repo["repo_url"],
                                repo_name=repo["repo_name"],
                                stars=repo["stars"],
                                description=repo.get("description", ""),
                                language=repo.get("language", ""),
                                last_updated=datetime.fromisoformat(
                                    repo["last_updated"].replace("Z", "+00:00")
                                ) if repo.get("last_updated") else None,
                            )
                            db.add(impl)
                            stats["repos_added"] += 1
                    
                    # Update paper metrics
                    if paper.metrics:
                        paper.metrics.github_stars = sum(r["stars"] for r in repos)
                        paper.metrics.github_repos_count = len(repos)
                
                # Commit periodically
                if stats["processed"] % 20 == 0:
                    db.commit()
                    logger.info(f"Processed {stats['processed']} papers...")
                
            except Exception as e:
                logger.warning(f"Error finding implementations for {paper.arxiv_id}: {e}")
                stats["errors"] += 1
        
        db.commit()
        logger.info(f"Discovery complete: {stats}")
        return stats
        
    finally:
        db.close()


async def update_existing_implementations(limit: int = 100) -> Dict[str, int]:
    """Update star counts for existing implementations."""
    stats = {"updated": 0, "errors": 0}
    
    db = SessionLocal()
    
    try:
        # Get implementations to update
        implementations = (
            db.query(PaperImplementation)
            .filter(PaperImplementation.source == "github")
            .order_by(PaperImplementation.last_updated.asc())
            .limit(limit)
            .all()
        )
        
        for impl in implementations:
            try:
                # Parse owner and repo from URL
                parts = impl.repo_name.split("/")
                if len(parts) >= 2:
                    owner, repo = parts[0], parts[1]
                    details = await github_service.get_repo_details(owner, repo)
                    
                    if details:
                        impl.stars = details["stars"]
                        impl.last_updated = datetime.fromisoformat(
                            details["last_updated"].replace("Z", "+00:00")
                        ) if details.get("last_updated") else None
                        stats["updated"] += 1
                
            except Exception as e:
                stats["errors"] += 1
        
        db.commit()
        return stats
        
    finally:
        db.close()


async def main():
    """Run the discovery job."""
    logger.info("Starting GitHub implementation discovery...")
    stats = await discover_implementations(days_back=7, limit=200)
    logger.info(f"Job completed: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
