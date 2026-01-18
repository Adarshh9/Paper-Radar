"""
Background scheduler for automated paper ingestion and processing.
Runs periodic jobs to keep the database up-to-date.
"""
import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from app.core.config import get_settings
from app.core.logging import setup_logging
from scripts.ingest_arxiv_daily import ingest_arxiv_papers
from scripts.enrich_semantic_scholar import enrich_papers_with_semantic_scholar
from scripts.generate_enhanced_summaries import generate_enhanced_summaries
from scripts.recalculate_rankings import calculate_field_normalized_scores
from app.core.database import SessionLocal

setup_logging()
settings = get_settings()


class PaperRadarScheduler:
    """Automated scheduler for paper ingestion and processing."""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()
    
    def _setup_jobs(self):
        """Configure all scheduled jobs."""
        
        # Job 1: Ingest new papers every 30 minutes (check for new papers frequently)
        self.scheduler.add_job(
            self.job_ingest_papers,
            trigger=CronTrigger(minute="*/30"),  # Every 30 minutes
            id="ingest_papers",
            name="Paper Ingestion (30min)",
            replace_existing=True,
        )
        
        # Job 2: Enrich papers with citations every 6 hours
        self.scheduler.add_job(
            self.job_enrich_citations,
            trigger=CronTrigger(hour="*/6"),
            id="enrich_citations",
            name="Citation Enrichment",
            replace_existing=True,
        )
        
        # Job 3: Generate summaries for new papers every hour
        self.scheduler.add_job(
            self.job_generate_summaries,
            trigger=CronTrigger(minute=0),  # Every hour at :00
            id="generate_summaries",
            name="Generate AI Summaries",
            replace_existing=True,
        )
        
        # Job 4: Recalculate rankings every 15 minutes
        self.scheduler.add_job(
            self.job_recalculate_rankings,
            trigger=CronTrigger(minute="*/15"),  # More frequent ranking updates
            id="recalculate_rankings",
            name="Recalculate Rankings",
            replace_existing=True,
        )
        
        logger.info("Scheduled jobs configured:")
        logger.info("  - Paper Ingestion: Every 30 minutes")
        logger.info("  - Citation Enrichment: Every 6 hours")
        logger.info("  - Summary Generation: Every hour")
        logger.info("  - Ranking Calculation: Every 15 minutes")
    
    async def job_ingest_papers(self):
        """Ingest new papers from arXiv."""
        try:
            logger.info("="*80)
            logger.info(f"SCHEDULED JOB: Paper Ingestion - {datetime.now()}")
            logger.info("="*80)
            
            stats = await ingest_arxiv_papers(days_back=1, max_per_category=100)
            
            logger.info("Ingestion complete", **stats)
            
            if stats["new_papers"] > 0:
                logger.info(f"✨ {stats['new_papers']} new papers added!")
            else:
                logger.info("No new papers found")
            
        except Exception as e:
            logger.error(f"Error in ingestion job: {e}")
    
    async def job_enrich_citations(self):
        """Enrich papers with citation data."""
        try:
            logger.info("="*80)
            logger.info(f"SCHEDULED JOB: Citation Enrichment - {datetime.now()}")
            logger.info("="*80)
            
            # Only enrich papers from last 7 days
            stats = await enrich_papers_with_semantic_scholar(limit=100, update_existing=True)
            
            logger.info("Citation enrichment complete", **stats)
            
        except Exception as e:
            logger.error(f"Error in enrichment job: {e}")
    
    async def job_generate_summaries(self):
        """Generate AI summaries for papers without them."""
        try:
            logger.info("="*80)
            logger.info(f"SCHEDULED JOB: Summary Generation - {datetime.now()}")
            logger.info("="*80)
            
            # Generate summaries in small batches
            stats = await generate_enhanced_summaries(
                limit=50,  # Process 50 papers per hour
                batch_size=10,
                batch_delay_seconds=70,
            )
            
            logger.info("Summary generation complete", **stats)
            
            if stats["generated"] > 0:
                logger.info(f"✨ Generated {stats['generated']} new summaries!")
            
        except Exception as e:
            logger.error(f"Error in summary generation job: {e}")
    
    async def job_recalculate_rankings(self):
        """Recalculate paper rankings."""
        try:
            logger.info("="*80)
            logger.info(f"SCHEDULED JOB: Ranking Calculation - {datetime.now()}")
            logger.info("="*80)
            
            stats = await calculate_field_normalized_scores(
                SessionLocal(),
                days_back=30  # Recalculate for last 30 days
            )
            
            logger.info("Ranking calculation complete", **stats)
            
        except Exception as e:
            logger.error(f"Error in ranking job: {e}")
    
    def start(self):
        """Start the scheduler."""
        self.scheduler.start()
        logger.info("🚀 Background scheduler started")
    
    def shutdown(self):
        """Shutdown the scheduler."""
        self.scheduler.shutdown()
        logger.info("⏹️  Background scheduler stopped")


# Singleton instance
scheduler = PaperRadarScheduler()


async def run_scheduler():
    """Run the scheduler indefinitely."""
    scheduler.start()
    
    logger.info("\n" + "="*80)
    logger.info("PAPER RADAR - BACKGROUND SCHEDULER")
    logger.info("="*80)
    logger.info("\nScheduler is running. Press Ctrl+C to stop.\n")
    
    try:
        # Keep running
        while True:
            await asyncio.sleep(60)  # Check every minute
    except (KeyboardInterrupt, SystemExit):
        logger.info("\nShutting down scheduler...")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(run_scheduler())
