import asyncio
import logging
from sqlalchemy import text
from app.core.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_summaries_table():
    """Drop paper_summaries table."""
    logger.info("Dropping paper_summaries table...")
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS paper_summaries CASCADE"))
    logger.info("Table dropped. Restart the backend to recreate it.")

if __name__ == "__main__":
    reset_summaries_table()
