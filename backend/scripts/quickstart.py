"""
Quick start script for Paper Radar local development.
Initializes the database and runs a quick ingestion.

Usage:
    cd backend
    uv run python -m scripts.quickstart
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.core.config import get_settings
from app.core.database import init_db, SessionLocal
from app.core.logging import setup_logging
from app.models import Paper


def main():
    setup_logging()
    settings = get_settings()
    
    print("\n" + "=" * 60)
    print("🚀 PAPER RADAR - LOCAL QUICK START")
    print("=" * 60)
    print(f"📁 Data directory: {settings.data_directory.absolute()}")
    print(f"💾 Using local storage: {settings.use_local_storage}")
    print("=" * 60 + "\n")
    
    # Initialize database
    print("📊 Initializing database...")
    init_db()
    
    # Check if we have papers
    db = SessionLocal()
    paper_count = db.query(Paper).count()
    db.close()
    
    if paper_count > 0:
        print(f"✅ Database already has {paper_count} papers")
        print("\n🎉 Ready! You can now:")
        print("   1. Start the API server:")
        print("      uv run uvicorn app.main:app --reload")
        print("   2. Run the full pipeline (fetches new papers):")
        print("      uv run python -m scripts.run_pipeline --quick")
        print("   3. Start the frontend:")
        print("      cd ../frontend && npm run dev")
    else:
        print("📥 No papers found. Running quick ingestion...")
        from scripts.ingest_arxiv_daily import ingest_arxiv_papers
        asyncio.run(ingest_arxiv_papers(days_back=3, max_per_category=50))
        
        db = SessionLocal()
        paper_count = db.query(Paper).count()
        db.close()
        
        print(f"✅ Ingested {paper_count} papers!")
        print("\n🎉 Ready! Start the server:")
        print("   uv run uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
