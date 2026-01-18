"""
Quick fix script - Run this to fix all remaining issues.
"""
import asyncio
import sys

from loguru import logger

from app.core.logging import setup_logging

setup_logging()


async def main():
    logger.info("\n" + "="*80)
    logger.info("PAPER RADAR - QUICK FIX SCRIPT")
    logger.info("="*80 + "\n")
    
    logger.info("This will:")
    logger.info("  1. Calculate ranking scores for all papers")
    logger.info("  2. Verify everything is working")
    logger.info("  3. Show you what to do next\n")
    
    # Step 1: Calculate rankings
    logger.info("Step 1/2: Calculating ranking scores...")
    logger.info("(This may take 2-5 minutes depending on paper count)\n")
    
    try:
        from scripts.recalculate_rankings import calculate_field_normalized_scores
        from app.core.database import SessionLocal
        
        stats = await calculate_field_normalized_scores(SessionLocal(), days_back=90)
        
        logger.info(f"✅ Rankings calculated!")
        logger.info(f"   - Processed: {stats['processed']} papers")
        logger.info(f"   - Updated: {stats['updated']} scores")
        logger.info(f"   - Errors: {stats['errors']}\n")
        
    except Exception as e:
        logger.error(f"❌ Error calculating rankings: {e}")
        logger.info("Try running manually: uv run python -m scripts.recalculate_rankings")
        return 1
    
    # Step 2: Quick verification
    logger.info("Step 2/2: Verifying system...\n")
    
    try:
        from app.core.database import SessionLocal
        from app.models import Paper, PaperMetrics, PaperSummary
        
        db = SessionLocal()
        
        paper_count = db.query(Paper).count()
        ranked_count = db.query(PaperMetrics).filter(
            PaperMetrics.overall_rank_score > 0
        ).count()
        summary_count = db.query(PaperSummary).count()
        
        db.close()
        
        logger.info(f"📊 System Status:")
        logger.info(f"   Papers: {paper_count}")
        logger.info(f"   With rankings: {ranked_count} ({ranked_count/paper_count*100:.0f}%)")
        logger.info(f"   With summaries: {summary_count} ({summary_count/paper_count*100:.0f}%)")
        logger.info("")
        
        if ranked_count == 0:
            logger.warning("⚠️  Rankings still 0. Check logs above for errors.")
            return 1
        
    except Exception as e:
        logger.error(f"Error checking status: {e}")
        return 1
    
    # Success!
    logger.info("="*80)
    logger.info("✅ ALL FIXES APPLIED!")
    logger.info("="*80 + "\n")
    
    logger.info("Next steps:")
    logger.info("  1. Start the API:")
    logger.info("     uv run uvicorn app.main:app --reload")
    logger.info("")
    logger.info("  2. Open your browser:")
    logger.info("     http://localhost:3000/papers")
    logger.info("")
    logger.info("  3. Click any paper - you should now see:")
    logger.info("     ✓ Metrics with radar scores")
    logger.info("     ✓ ELI5 explanation")
    logger.info("     ✓ Pros & Cons")
    logger.info("     ✓ Methodology & Innovation")
    logger.info("     ✓ All other summary fields")
    logger.info("")
    logger.info("  4. (Optional) Start background scheduler:")
    logger.info("     uv run python -m app.services.background_scheduler")
    logger.info("")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
