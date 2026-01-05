"""Quick test for arXiv fetch - with redirect fix."""
import asyncio
from app.services.arxiv_service import arxiv_service
from app.core.logging import setup_logging

setup_logging()

async def test():
    print("Testing arXiv with follow_redirects=True...")
    papers = await arxiv_service.fetch_recent_papers('cs.AI', max_results=10, days_back=30)
    print(f'Got {len(papers)} papers')
    if papers:
        for p in papers[:3]:
            print(f'  - {p["arxiv_id"]}: {p["title"][:60]}... ({p["published_date"]})')
    else:
        print("  No papers returned!")

if __name__ == "__main__":
    asyncio.run(test())
