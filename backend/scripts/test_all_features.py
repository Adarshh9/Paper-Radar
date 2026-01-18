"""
Comprehensive test script to verify all enhanced features are working.
"""
import asyncio
import sys
from typing import Dict, List

from loguru import logger

from app.core.database import SessionLocal
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.models import Paper, PaperSummary, PaperMetrics
from app.services.llm_service_enhanced import enhanced_llm_service

setup_logging()
settings = get_settings()


class TestResults:
    """Track test results."""
    
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures: List[str] = []
    
    def record_pass(self, test_name: str):
        self.tests_run += 1
        self.tests_passed += 1
        logger.info(f"✅ PASS: {test_name}")
    
    def record_fail(self, test_name: str, reason: str):
        self.tests_run += 1
        self.tests_failed += 1
        self.failures.append(f"{test_name}: {reason}")
        logger.error(f"❌ FAIL: {test_name} - {reason}")
    
    def print_summary(self):
        logger.info("\n" + "="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        logger.info(f"Tests Run: {self.tests_run}")
        logger.info(f"Passed: {self.tests_passed}")
        logger.info(f"Failed: {self.tests_failed}")
        
        if self.failures:
            logger.info("\nFailures:")
            for failure in self.failures:
                logger.info(f"  - {failure}")
        
        logger.info("="*80 + "\n")
        
        return self.tests_failed == 0


async def test_database_connection(results: TestResults):
    """Test database connection."""
    try:
        db = SessionLocal()
        paper_count = db.query(Paper).count()
        db.close()
        
        if paper_count > 0:
            results.record_pass(f"Database connection ({paper_count} papers found)")
        else:
            results.record_fail("Database connection", "No papers in database")
    except Exception as e:
        results.record_fail("Database connection", str(e))


async def test_pros_cons_columns(results: TestResults):
    """Test that pros/cons columns exist."""
    try:
        db = SessionLocal()
        
        # Try to query a summary with pros/cons
        summary = db.query(PaperSummary).first()
        
        if summary:
            # Check if attributes exist (will raise AttributeError if not)
            _ = summary.pros
            _ = summary.cons
            results.record_pass("Pros/cons columns exist")
        else:
            results.record_fail("Pros/cons columns", "No summaries in database to test")
        
        db.close()
    except AttributeError as e:
        results.record_fail("Pros/cons columns", f"Columns don't exist: {e}")
    except Exception as e:
        results.record_fail("Pros/cons columns", str(e))


async def test_groq_api_key(results: TestResults):
    """Test Groq API key is configured."""
    if settings.groq_api_key:
        results.record_pass(f"Groq API key configured ({len(settings.groq_api_key)} chars)")
    else:
        results.record_fail("Groq API key", "GROQ_API_KEY not set in .env")


async def test_enhanced_summary_generation(results: TestResults):
    """Test enhanced summary generation with all fields."""
    if not settings.groq_api_key:
        results.record_fail("Enhanced summary generation", "Groq API key not configured")
        return
    
    try:
        db = SessionLocal()
        paper = db.query(Paper).first()
        db.close()
        
        if not paper:
            results.record_fail("Enhanced summary generation", "No papers to test with")
            return
        
        logger.info(f"\nTesting summary generation for: {paper.title[:60]}...")
        
        summary = await enhanced_llm_service.generate_paper_summary(
            title=paper.title,
            abstract=paper.abstract
        )
        
        if not summary:
            results.record_fail("Enhanced summary generation", "Failed to generate summary")
            return
        
        # Check all required fields
        required_fields = [
            "one_line_summary",
            "eli5",
            "key_innovation",
            "problem_statement",
            "methodology",
        ]
        
        missing_fields = []
        for field in required_fields:
            if not summary.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            results.record_fail(
                "Enhanced summary generation",
                f"Missing fields: {', '.join(missing_fields)}"
            )
        else:
            # Check new fields
            has_pros = bool(summary.get("pros"))
            has_cons = bool(summary.get("cons"))
            
            logger.info(f"\nGenerated Summary Sample:")
            logger.info(f"  One-line: {summary['one_line_summary'][:80]}...")
            logger.info(f"  ELI5: {summary.get('eli5', 'N/A')[:80]}...")
            logger.info(f"  Has Pros: {has_pros}")
            logger.info(f"  Has Cons: {has_cons}")
            
            if has_pros and has_cons:
                results.record_pass("Enhanced summary generation (all fields including pros/cons)")
            else:
                results.record_fail(
                    "Enhanced summary generation",
                    f"Missing pros ({has_pros}) or cons ({has_cons})"
                )
        
    except Exception as e:
        results.record_fail("Enhanced summary generation", str(e))


async def test_existing_summaries(results: TestResults):
    """Test existing summaries have all fields."""
    try:
        db = SessionLocal()
        summaries = db.query(PaperSummary).limit(10).all()
        db.close()
        
        if not summaries:
            results.record_fail("Existing summaries", "No summaries found in database")
            return
        
        # Check how many have all fields populated
        complete_summaries = 0
        for summary in summaries:
            if all([
                summary.one_line_summary,
                summary.eli5,
                summary.key_innovation,
                summary.methodology,
            ]):
                complete_summaries += 1
        
        percentage = (complete_summaries / len(summaries)) * 100
        
        if percentage >= 80:
            results.record_pass(
                f"Existing summaries ({percentage:.0f}% complete with all fields)"
            )
        else:
            results.record_fail(
                "Existing summaries",
                f"Only {percentage:.0f}% have all fields. Run generate_enhanced_summaries.py"
            )
        
    except Exception as e:
        results.record_fail("Existing summaries", str(e))


async def test_ranking_scores(results: TestResults):
    """Test that papers have ranking scores."""
    try:
        db = SessionLocal()
        
        metrics_count = db.query(PaperMetrics).filter(
            PaperMetrics.overall_rank_score > 0
        ).count()
        
        total_papers = db.query(Paper).count()
        db.close()
        
        if metrics_count == 0:
            results.record_fail("Ranking scores", "No papers have ranking scores")
        else:
            percentage = (metrics_count / total_papers) * 100
            results.record_pass(f"Ranking scores ({percentage:.0f}% of papers ranked)")
        
    except Exception as e:
        results.record_fail("Ranking scores", str(e))


async def test_imports(results: TestResults):
    """Test that all enhanced services can be imported."""
    try:
        from app.services.ranking_engine import AdvancedRankingEngine
        from app.core.rate_limiting import rate_limiter
        from app.core.intelligent_cache import intelligent_cache
        from app.services.embedding_service import paper_embedding_service
        from app.services.summary_generator import adaptive_summary_generator
        from app.services.llm_service_enhanced import enhanced_llm_service
        from app.core.optimized_queries import OptimizedPaperRepository
        
        results.record_pass("All enhanced services import successfully")
    except ImportError as e:
        results.record_fail("Service imports", str(e))


async def test_cache_functionality(results: TestResults):
    """Test intelligent cache."""
    try:
        from app.core.intelligent_cache import intelligent_cache, DataType
        
        # Test set/get
        test_key = "test:key:12345"
        test_value = {"test": "data"}
        
        intelligent_cache.set(test_key, test_value, data_type=DataType.SUMMARIES.value)
        retrieved = intelligent_cache.get(test_key, DataType.SUMMARIES.value)
        
        if retrieved == test_value:
            results.record_pass("Intelligent cache set/get")
        else:
            results.record_fail("Intelligent cache", f"Retrieved {retrieved}, expected {test_value}")
        
        # Cleanup
        intelligent_cache.delete(test_key)
        
    except Exception as e:
        results.record_fail("Intelligent cache", str(e))


async def run_all_tests():
    """Run all tests."""
    logger.info("\n" + "="*80)
    logger.info("PAPER RADAR - COMPREHENSIVE FEATURE TEST")
    logger.info("="*80 + "\n")
    
    results = TestResults()
    
    # Run tests
    logger.info("Running tests...\n")
    
    await test_imports(results)
    await test_database_connection(results)
    await test_pros_cons_columns(results)
    await test_groq_api_key(results)
    await test_existing_summaries(results)
    await test_ranking_scores(results)
    await test_cache_functionality(results)
    
    # This test takes longer, so run it last
    await test_enhanced_summary_generation(results)
    
    # Print summary
    success = results.print_summary()
    
    if success:
        logger.info("🎉 All tests passed! System is working correctly.")
        return 0
    else:
        logger.error("⚠️  Some tests failed. Please fix the issues above.")
        return 1


async def quick_test():
    """Quick test of just critical features."""
    logger.info("\n🚀 Running quick test...\n")
    
    results = TestResults()
    
    await test_imports(results)
    await test_database_connection(results)
    await test_groq_api_key(results)
    
    success = results.print_summary()
    return 0 if success else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        exit_code = asyncio.run(quick_test())
    else:
        exit_code = asyncio.run(run_all_tests())
    
    sys.exit(exit_code)
