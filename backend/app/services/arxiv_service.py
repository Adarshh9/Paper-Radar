"""
arXiv API service for fetching research papers.
"""
import asyncio
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional

import httpx
import feedparser
from loguru import logger

from app.core.config import get_settings

settings = get_settings()


class ArxivService:
    """Service for interacting with arXiv API."""
    
    BASE_URL = "http://export.arxiv.org/api/query"
    
    def __init__(self):
        self.rate_limit_delay = 1.0 / settings.arxiv_requests_per_second
        self._last_request_time = 0.0
    
    async def _rate_limit(self):
        """Ensure we don't exceed rate limits."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()
    
    async def fetch_recent_papers(
        self,
        category: str,
        max_results: int = 100,
        days_back: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent papers from arXiv for a given category.
        
        Args:
            category: arXiv category (e.g., "cs.AI", "cs.LG")
            max_results: Maximum number of papers to fetch
            days_back: Number of days to look back
            
        Returns:
            List of paper dictionaries
        """
        await self._rate_limit()
        
        # arXiv uses submittedDate for filtering
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        # Build query
        query = f"cat:{category}"
        
        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            try:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                
                papers = self._parse_feed(response.text, start_date)
                logger.debug(
                    "Fetched papers from arXiv",
                    category=category,
                    count=len(papers),
                )
                return papers
                
            except httpx.HTTPError as e:
                logger.error(
                    "arXiv API error",
                    error=str(e),
                    category=category,
                    status_code=getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None,
                    response_text=getattr(e.response, 'text', '')[:500] if hasattr(e, 'response') else None,
                )
                return []
            except Exception as e:
                logger.error("arXiv unexpected error", error=str(e), error_type=type(e).__name__)
                return []
    
    async def fetch_papers_by_date_range(
        self,
        start_date: date,
        end_date: date,
        category: str,
        max_results: int = 500,
    ) -> List[Dict[str, Any]]:
        """
        Fetch papers from a specific date range.
        Handles pagination for large result sets.
        """
        all_papers = []
        start = 0
        batch_size = min(max_results, 500)
        
        while len(all_papers) < max_results:
            await self._rate_limit()
            
            query = f"cat:{category}"
            params = {
                "search_query": query,
                "start": start,
                "max_results": batch_size,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
            
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                try:
                    response = await client.get(self.BASE_URL, params=params)
                    response.raise_for_status()
                    
                    papers = self._parse_feed(response.text, start_date, end_date)
                    
                    if not papers:
                        break
                    
                    all_papers.extend(papers)
                    start += batch_size
                    
                    logger.debug(
                        "Fetched paper batch",
                        category=category,
                        batch_start=start,
                        batch_count=len(papers),
                    )
                    
                    # Check if we got fewer papers than requested (end of results)
                    if len(papers) < batch_size:
                        break
                        
                except httpx.HTTPError as e:
                    logger.error("arXiv API error on batch", error=str(e), batch_start=start)
                    break
        
        return all_papers[:max_results]
    
    async def search_papers_by_keyword(
        self,
        keyword: str,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search papers by keyword."""
        await self._rate_limit()
        
        params = {
            "search_query": f"all:{keyword}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
        }
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            try:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                
                return self._parse_feed(response.text)
                
            except httpx.HTTPError as e:
                logger.error("arXiv search error", error=str(e), keyword=keyword)
                return []
    
    def _parse_feed(
        self,
        xml_content: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Parse arXiv Atom feed response."""
        feed = feedparser.parse(xml_content)
        papers = []
        
        for entry in feed.entries:
            try:
                # Extract arXiv ID from the id URL
                arxiv_id = entry.id.split("/abs/")[-1]
                if "v" in arxiv_id:
                    arxiv_id = arxiv_id.split("v")[0]
                
                # Parse dates
                published = datetime.strptime(
                    entry.published[:10], "%Y-%m-%d"
                ).date()
                
                updated = None
                if hasattr(entry, "updated"):
                    updated = datetime.strptime(
                        entry.updated[:10], "%Y-%m-%d"
                    ).date()
                
                # Filter by date range if specified
                if start_date and published < start_date:
                    continue
                if end_date and published > end_date:
                    continue
                
                # Extract authors
                authors = []
                for author in entry.authors:
                    author_data = {"name": author.name, "affiliations": []}
                    if hasattr(author, "arxiv_affiliation"):
                        author_data["affiliations"] = [author.arxiv_affiliation]
                    authors.append(author_data)
                
                # Extract categories
                categories = []
                primary_category = None
                if hasattr(entry, "arxiv_primary_category"):
                    primary_category = entry.arxiv_primary_category.get("term", "")
                if hasattr(entry, "tags"):
                    categories = [tag.term for tag in entry.tags]
                
                if not primary_category and categories:
                    primary_category = categories[0]
                
                # Build paper dict
                paper = {
                    "arxiv_id": arxiv_id,
                    "title": entry.title.replace("\n", " ").strip(),
                    "abstract": entry.summary.replace("\n", " ").strip(),
                    "authors": authors,
                    "published_date": published,
                    "updated_date": updated,
                    "primary_category": primary_category,
                    "categories": categories,
                    "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                    "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
                    "doi": getattr(entry, "arxiv_doi", None),
                    "journal_ref": getattr(entry, "arxiv_journal_ref", None),
                    "comments": getattr(entry, "arxiv_comment", None),
                }
                
                papers.append(paper)
                
            except Exception as e:
                logger.warning("Error parsing arXiv entry", error=str(e))
                continue
        
        return papers


# Singleton instance
arxiv_service = ArxivService()
