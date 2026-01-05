"""
Test script for individual services.
Run with: uv run -m scripts.test_services
"""
import asyncio
from loguru import logger

from app.core.logging import setup_logging

setup_logging()


async def test_arxiv():
    """Test arXiv API service."""
    logger.info("Testing arXiv API...")
    
    from app.services.arxiv_service import arxiv_service
    
    try:
        papers = await arxiv_service.fetch_recent_papers(
            category="cs.AI",
            max_results=5,
            days_back=7,
        )
        
        if papers:
            logger.success(f"✓ arXiv API works! Got {len(papers)} papers")
            for p in papers[:2]:
                logger.info(f"  - {p['title'][:60]}...")
        else:
            logger.warning("arXiv API returned no papers (empty but no error)")
            
        return True
    except Exception as e:
        logger.error(f"✗ arXiv API failed: {e}")
        return False


async def test_semantic_scholar():
    """Test Semantic Scholar API service."""
    logger.info("Testing Semantic Scholar API...")
    
    from app.services.semantic_scholar_service import semantic_scholar_service
    
    try:
        # Test with a known paper
        result = await semantic_scholar_service.get_paper_details("2301.00234")
        
        if result:
            logger.success(f"✓ Semantic Scholar API works!")
            logger.info(f"  Paper: {result.get('title', 'Unknown')[:60]}")
            logger.info(f"  Citations: {result.get('citationCount', 0)}")
        else:
            logger.warning("Paper not found in Semantic Scholar (but API responded)")
            
        return True
    except Exception as e:
        logger.error(f"✗ Semantic Scholar API failed: {e}")
        return False


async def test_github():
    """Test GitHub API service."""
    logger.info("Testing GitHub API...")
    
    from app.services.github_service import github_service
    from app.core.config import get_settings
    
    settings = get_settings()
    
    if not settings.github_token:
        logger.warning("⚠ GITHUB_TOKEN not set - API will have lower rate limits")
    
    try:
        # Search for transformer repos
        repos = await github_service._search_repositories(
            query="transformer machine learning",
            min_stars=100,
            limit=3,
        )
        
        if repos:
            logger.success(f"✓ GitHub API works! Found {len(repos)} repos")
            for r in repos[:2]:
                logger.info(f"  - {r['repo_name']} ({r['stars']} ⭐)")
        else:
            logger.warning("GitHub search returned no results")
            
        return True
    except Exception as e:
        logger.error(f"✗ GitHub API failed: {e}")
        return False


async def test_groq():
    """Test Groq LLM API service."""
    logger.info("Testing Groq LLM API...")
    
    from app.services.llm_service import llm_service
    from app.core.config import get_settings
    
    settings = get_settings()
    
    if not settings.groq_api_key:
        logger.error("✗ GROQ_API_KEY not set - cannot test")
        return False
    
    try:
        result = await llm_service.generate_paper_summary(
            title="Attention Is All You Need",
            abstract="We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.",
        )
        
        if result:
            logger.success(f"✓ Groq API works!")
            logger.info(f"  Summary: {result.get('one_line_summary', 'N/A')[:80]}")
        else:
            logger.warning("Groq API returned no summary")
            
        return True
    except Exception as e:
        logger.error(f"✗ Groq API failed: {e}")
        return False


async def test_database():
    """Test database connection."""
    logger.info("Testing Database connection...")
    
    try:
        from sqlalchemy import text
        from app.core.database import SessionLocal
        
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        
        logger.success("✓ Database connection works!")
        return True
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        return False


async def test_redis():
    """Test Redis connection."""
    logger.info("Testing Redis connection...")
    
    try:
        from app.core.cache import cache
        
        # Test set and get
        cache.set("test_key", {"test": "value"}, ttl_seconds=60)
        result = cache.get("test_key")
        cache.delete("test_key")
        
        if result and result.get("test") == "value":
            logger.success("✓ Redis connection works!")
            return True
        else:
            logger.warning("Redis responded but data mismatch")
            return False
    except Exception as e:
        logger.error(f"✗ Redis connection failed: {e}")
        return False


async def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("PAPER RADAR - SERVICE TESTS")
    logger.info("=" * 60)
    
    results = {}
    
    # Infrastructure tests
    results["database"] = await test_database()
    results["redis"] = await test_redis()
    
    # External API tests
    results["arxiv"] = await test_arxiv()
    results["semantic_scholar"] = await test_semantic_scholar()
    results["github"] = await test_github()
    results["groq"] = await test_groq()
    
    # Summary
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for service, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        logger.info(f"  {service}: {status}")
    
    logger.info(f"\nTotal: {passed}/{total} passed")
    
    if passed == total:
        logger.success("All services working! 🎉")
    else:
        logger.warning("Some services need attention")


if __name__ == "__main__":
    asyncio.run(main())
