"""
Enhanced AI summary generation job using the new improved LLM service.
Generates comprehensive summaries with all fields including ELI5, pros, cons.
"""
import asyncio
from datetime import datetime
from typing import Dict

from loguru import logger

from app.core.database import SessionLocal
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.models import Paper, PaperSummary
from app.services.llm_service_enhanced import enhanced_llm_service

# Initialize logging
setup_logging()

settings = get_settings()


async def generate_enhanced_summaries(
    limit: int = 100,
    batch_size: int = 20,
    batch_delay_seconds: int = 65,
    regenerate: bool = False,
) -> Dict[str, int]:
    """
    Generate comprehensive AI summaries for papers.

    Args:
        limit: Maximum papers to process
        batch_size: Papers per batch (respecting rate limits)
        batch_delay_seconds: Delay between batches
        regenerate: If True, regenerate summaries even for papers that have them

    Returns:
        Statistics dict
    """
    stats = {
        "processed": 0,
        "generated": 0,
        "failed": 0,
        "skipped": 0,
    }

    if not settings.groq_api_key:
        logger.error("Groq API key not configured. Please set GROQ_API_KEY in .env file")
        return stats

    db = SessionLocal()

    try:
        # Get papers to process
        if regenerate:
            papers = (
                db.query(Paper)
                .order_by(Paper.published_date.desc())
                .limit(limit)
                .all()
            )
            logger.info("Regenerating summaries for papers", paper_count=len(papers))
        else:
            papers = (
                db.query(Paper)
                .outerjoin(PaperSummary)
                .filter(PaperSummary.id.is_(None))
                .order_by(Paper.published_date.desc())
                .limit(limit)
                .all()
            )
            logger.info("Generating summaries for papers without summaries", paper_count=len(papers))

        if not papers:
            logger.info("No papers to process")
            return stats

        batches = [papers[i : i + batch_size] for i in range(0, len(papers), batch_size)]

        for batch_idx, batch in enumerate(batches):
            logger.info(
                "Processing batch",
                batch_num=batch_idx + 1,
                total_batches=len(batches),
            )

            for paper in batch:
                stats["processed"] += 1

                try:
                    # Generate comprehensive summary
                    summary_data = await enhanced_llm_service.generate_paper_summary(
                        title=paper.title,
                        abstract=paper.abstract,
                    )

                    if summary_data:
                        # Check if summary exists
                        existing_summary = db.query(PaperSummary).filter(
                            PaperSummary.paper_id == paper.id
                        ).first()

                        if existing_summary and regenerate:
                            # Update existing
                            existing_summary.one_line_summary = summary_data["one_line_summary"]
                            existing_summary.eli5 = summary_data.get("eli5")
                            existing_summary.key_innovation = summary_data.get("key_innovation")
                            existing_summary.problem_statement = summary_data.get("problem_statement")
                            existing_summary.methodology = summary_data.get("methodology")
                            existing_summary.real_world_use_cases = summary_data.get("real_world_use_cases")
                            existing_summary.limitations = summary_data.get("limitations")
                            existing_summary.results_summary = summary_data.get("results_summary")
                            existing_summary.pros = summary_data.get("pros")
                            existing_summary.cons = summary_data.get("cons")
                            existing_summary.generated_by = f"groq-{enhanced_llm_service.FAST_MODEL}"
                            existing_summary.generated_at = datetime.utcnow()
                            
                            logger.info(f"✓ Updated summary for {paper.arxiv_id}")
                        else:
                            # Create new
                            summary = PaperSummary(
                                paper_id=paper.id,
                                one_line_summary=summary_data["one_line_summary"],
                                eli5=summary_data.get("eli5"),
                                key_innovation=summary_data.get("key_innovation"),
                                problem_statement=summary_data.get("problem_statement"),
                                methodology=summary_data.get("methodology"),
                                real_world_use_cases=summary_data.get("real_world_use_cases"),
                                limitations=summary_data.get("limitations"),
                                results_summary=summary_data.get("results_summary"),
                                pros=summary_data.get("pros"),
                                cons=summary_data.get("cons"),
                                generated_by=f"groq-{enhanced_llm_service.FAST_MODEL}",
                                generated_at=datetime.utcnow(),
                            )
                            db.add(summary)
                            logger.info(f"✓ Generated summary for {paper.arxiv_id}")
                        
                        stats["generated"] += 1
                        
                        # Show sample output for first paper
                        if stats["generated"] == 1:
                            logger.info("Sample summary generated:")
                            logger.info(f"  Title: {paper.title[:80]}...")
                            logger.info(f"  One-line: {summary_data['one_line_summary']}")
                            logger.info(f"  ELI5: {summary_data.get('eli5', 'N/A')[:100]}...")
                            logger.info(f"  Pros: {summary_data.get('pros', 'N/A')[:100]}...")
                    else:
                        logger.warning(f"Failed to generate summary for {paper.arxiv_id}")
                        stats["failed"] += 1

                except Exception as e:
                    logger.warning(
                        "Error generating summary",
                        arxiv_id=paper.arxiv_id,
                        error=str(e),
                    )
                    stats["failed"] += 1

            # Commit after each batch
            db.commit()
            logger.info("Batch complete", batch_num=batch_idx + 1, **stats)

            # Wait between batches to respect rate limits
            if batch_idx < len(batches) - 1:
                logger.info("Waiting for rate limit", wait_seconds=batch_delay_seconds)
                await asyncio.sleep(batch_delay_seconds)

        logger.info("Summary generation complete", **stats)
        return stats

    finally:
        db.close()


async def test_single_paper():
    """Test summary generation for a single paper."""
    db = SessionLocal()
    
    try:
        # Get first paper without summary
        paper = (
            db.query(Paper)
            .outerjoin(PaperSummary)
            .filter(PaperSummary.id.is_(None))
            .first()
        )
        
        if not paper:
            logger.info("No papers without summaries found. Testing with existing paper...")
            paper = db.query(Paper).first()
        
        if not paper:
            logger.error("No papers found in database")
            return
        
        logger.info(f"\nTesting summary generation for paper: {paper.title}\n")
        
        summary_data = await enhanced_llm_service.generate_paper_summary(
            title=paper.title,
            abstract=paper.abstract,
        )
        
        if summary_data:
            logger.info("\n" + "="*80)
            logger.info("GENERATED SUMMARY")
            logger.info("="*80 + "\n")
            
            for key, value in summary_data.items():
                logger.info(f"{key.upper()}:")
                logger.info(f"  {value}\n")
            
            logger.info("="*80 + "\n")
        else:
            logger.error("Failed to generate summary")
            
    finally:
        db.close()


async def main():
    """Run the enhanced summary generation job."""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        logger.info("Running test mode - single paper")
        await test_single_paper()
    else:
        logger.info("Starting enhanced summary generation job")
        stats = await generate_enhanced_summaries(
            limit=100, 
            batch_size=20,
            regenerate=False
        )
        logger.info("Job completed", **stats)


if __name__ == "__main__":
    asyncio.run(main())
