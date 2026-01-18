"""
Quick setup script for Paper Radar enhanced features.
Run this after pulling the latest code.
"""
import asyncio
import sys
from pathlib import Path

from loguru import logger

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal
from app.core.config import get_settings
from app.core.logging import setup_logging

setup_logging()
settings = get_settings()


async def setup_database():
    """Run database migrations."""
    logger.info("Step 1: Setting up database...")
    
    try:
        from scripts.migrate_add_pros_cons import add_pros_cons_columns
        await add_pros_cons_columns()
        logger.info("✓ Database migration completed")
        return True
    except Exception as e:
        logger.error(f"✗ Database migration failed: {e}")
        return False


async def test_basic_functionality():
    """Test basic functionality."""
    logger.info("\nStep 2: Testing basic functionality...")
    
    try:
        from scripts.test_all_features import quick_test
        result = await quick_test()
        
        if result == 0:
            logger.info("✓ Basic tests passed")
            return True
        else:
            logger.warning("⚠ Some basic tests failed, but continuing...")
            return False
    except Exception as e:
        logger.error(f"✗ Tests failed: {e}")
        return False


async def generate_sample_summaries():
    """Generate summaries for a few papers to test."""
    logger.info("\nStep 3: Generating sample summaries...")
    
    if not settings.groq_api_key:
        logger.warning("⚠ GROQ_API_KEY not set. Skipping summary generation.")
        logger.info("  To generate summaries, add GROQ_API_KEY to your .env file")
        return False
    
    try:
        db = SessionLocal()
        from app.models import Paper, PaperSummary
        
        # Find papers without summaries
        papers_without_summaries = (
            db.query(Paper)
            .outerjoin(PaperSummary)
            .filter(PaperSummary.id.is_(None))
            .limit(3)
            .all()
        )
        
        db.close()
        
        if not papers_without_summaries:
            logger.info("✓ All papers already have summaries")
            return True
        
        logger.info(f"  Found {len(papers_without_summaries)} papers without summaries")
        logger.info("  Generating summaries for first 3 papers...")
        
        from scripts.generate_enhanced_summaries import generate_enhanced_summaries
        stats = await generate_enhanced_summaries(
            limit=3,
            batch_size=3,
            batch_delay_seconds=10
        )
        
        if stats['generated'] > 0:
            logger.info(f"✓ Generated {stats['generated']} summaries")
            return True
        else:
            logger.warning("⚠ No summaries generated")
            return False
            
    except Exception as e:
        logger.error(f"✗ Summary generation failed: {e}")
        return False


async def verify_api_integration():
    """Verify API returns enhanced data."""
    logger.info("\nStep 4: Verifying API integration...")
    
    try:
        import httpx
        
        # Check if API is running
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get("http://localhost:8000/health", timeout=5.0)
                if response.status_code == 200:
                    logger.info("✓ API is running")
                    
                    # Try to get a paper
                    db = SessionLocal()
                    from app.models import Paper
                    paper = db.query(Paper).first()
                    db.close()
                    
                    if paper:
                        paper_response = await client.get(
                            f"http://localhost:8000/api/papers/{paper.id}"
                        )
                        
                        if paper_response.status_code == 200:
                            data = paper_response.json()
                            has_summary = data.get('summary') is not None
                            has_pros = data.get('summary', {}).get('pros') is not None if has_summary else False
                            
                            if has_summary:
                                logger.info(f"✓ API returns summaries (pros: {has_pros})")
                            else:
                                logger.info("✓ API accessible (no summaries yet)")
                            
                            return True
                else:
                    logger.warning("⚠ API returned non-200 status")
                    return False
                    
            except httpx.ConnectError:
                logger.warning("⚠ API not running. Start with: uv run uvicorn app.main:app --reload")
                logger.info("  (This is optional for setup)")
                return False
                
    except Exception as e:
        logger.warning(f"⚠ API verification skipped: {e}")
        return False


async def main():
    """Run complete setup."""
    logger.info("\n" + "="*80)
    logger.info("PAPER RADAR - ENHANCED FEATURES SETUP")
    logger.info("="*80 + "\n")
    
    logger.info("This script will:")
    logger.info("  1. Run database migrations")
    logger.info("  2. Test basic functionality")
    logger.info("  3. Generate sample summaries")
    logger.info("  4. Verify API integration")
    logger.info("\n")
    
    # Run setup steps
    db_ok = await setup_database()
    test_ok = await test_basic_functionality()
    summary_ok = await generate_sample_summaries()
    api_ok = await verify_api_integration()
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.info("SETUP SUMMARY")
    logger.info("="*80)
    logger.info(f"Database Migration: {'✓' if db_ok else '✗'}")
    logger.info(f"Basic Tests:        {'✓' if test_ok else '✗'}")
    logger.info(f"Sample Summaries:   {'✓' if summary_ok else '⚠'}")
    logger.info(f"API Integration:    {'✓' if api_ok else '⚠'}")
    logger.info("="*80 + "\n")
    
    if db_ok and test_ok:
        logger.info("🎉 Setup completed successfully!")
        logger.info("\nNext steps:")
        logger.info("  1. Start the API:")
        logger.info("     cd backend && uv run uvicorn app.main:app --reload")
        logger.info("\n  2. Generate summaries for all papers:")
        logger.info("     uv run python -m scripts.generate_enhanced_summaries")
        logger.info("\n  3. Test specific features:")
        logger.info("     uv run python -m scripts.test_all_features")
        return 0
    else:
        logger.error("⚠️  Setup incomplete. Please fix the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
