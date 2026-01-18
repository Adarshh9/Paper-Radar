"""
Script to calculate ranking scores for all papers.
Run this after ingesting papers to populate ranking scores.
"""
import asyncio
from datetime import datetime

from loguru import logger

from app.core.database import SessionLocal
from app.core.logging import setup_logging
from app.services.ranking_engine import calculate_field_normalized_scores

setup_logging()


async def main():
    """Calculate ranking scores for all papers."""
    logger.info("="*80)
    logger.info("CALCULATING RANKING SCORES")
    logger.info("="*80 + "\n")
    
    logger.info("This will calculate ranking scores for all papers from the last 90 days...")
    logger.info("This may take a few minutes depending on paper count.\n")
    
    try:
        stats = await calculate_field_normalized_scores(
            SessionLocal(),
            days_back=90
        )
        
        logger.info("\n" + "="*80)
        logger.info("RANKING CALCULATION COMPLETE")
        logger.info("="*80)
        logger.info(f"Papers processed: {stats['processed']}")
        logger.info(f"Scores updated: {stats['updated']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info("="*80 + "\n")
        
        logger.info("✅ Ranking scores have been calculated!")
        logger.info("   Papers now have rank scores and will appear in trending/sorted lists")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Error calculating rankings: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
