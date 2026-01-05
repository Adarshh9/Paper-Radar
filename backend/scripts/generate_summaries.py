"""
AI summary generation job.
Generates summaries for papers using Groq LLM.
"""
import asyncio
from datetime import datetime
from typing import Dict

from loguru import logger

from app.core.database import SessionLocal
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.models import Paper, PaperSummary
from app.services.llm_service import llm_service

# Initialize logging
setup_logging()

settings = get_settings()


async def generate_summaries(
    limit: int = 500,
    batch_size: int = 25,
    batch_delay_seconds: int = 65,
) -> Dict[str, int]:
    """
    Generate AI summaries for papers without summaries.

    Args:
        limit: Maximum papers to process
        batch_size: Papers per batch (respecting rate limits)
        batch_delay_seconds: Delay between batches

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
        logger.error("Groq API key not configured")
        return stats

    db = SessionLocal()

    try:
        # Get papers without summaries
        papers = (
            db.query(Paper)
            .outerjoin(PaperSummary)
            .filter(PaperSummary.id.is_(None))
            .order_by(Paper.published_date.desc())
            .limit(limit)
            .all()
        )

        logger.info("Generating summaries", paper_count=len(papers))

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
                    # Generate summary
                    summary_data = await llm_service.generate_paper_summary(
                        title=paper.title,
                        abstract=paper.abstract,
                    )

                    if summary_data:
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
                            generated_by=f"groq-{llm_service.FAST_MODEL}",
                            generated_at=datetime.utcnow(),
                        )
                        db.add(summary)
                        stats["generated"] += 1
                    else:
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


async def main():
    """Run the summary generation job."""
    logger.info("Starting summary generation job")
    stats = await generate_summaries(limit=500, batch_size=25)
    logger.info("Job completed", **stats)


if __name__ == "__main__":
    asyncio.run(main())
