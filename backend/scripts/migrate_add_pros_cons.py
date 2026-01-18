"""
Database migration script to add pros/cons fields to paper_summaries.
Run this after updating the model.
"""
import asyncio
from sqlalchemy import text

from app.core.database import SessionLocal
from app.core.logging import setup_logging
from loguru import logger

setup_logging()


async def add_pros_cons_columns():
    """Add pros and cons columns to paper_summaries table."""
    db = SessionLocal()
    
    try:
        logger.info("Adding pros and cons columns to paper_summaries...")
        
        # Check if columns already exist
        result = db.execute(text("PRAGMA table_info(paper_summaries)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'pros' not in columns:
            db.execute(text("ALTER TABLE paper_summaries ADD COLUMN pros TEXT"))
            logger.info("✓ Added 'pros' column")
        else:
            logger.info("'pros' column already exists")
        
        if 'cons' not in columns:
            db.execute(text("ALTER TABLE paper_summaries ADD COLUMN cons TEXT"))
            logger.info("✓ Added 'cons' column")
        else:
            logger.info("'cons' column already exists")
        
        db.commit()
        logger.info("Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(add_pros_cons_columns())
