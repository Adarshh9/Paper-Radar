"""
Semantic Scholar API service for citation data and paper enrichment.
Includes robust rate limiting and exponential backoff.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

import httpx
from loguru import logger

from app.core.config import get_settings
from app.core.cache import cache

settings = get_settings()


class SemanticScholarService:
    """Service for interacting with Semantic Scholar API."""
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    # Fields to request from API
    PAPER_FIELDS = [
        "paperId", "title", "abstract", "authors", "year",
        "citationCount", "referenceCount", "influentialCitationCount",
        "venue", "publicationDate", "externalIds"
    ]
    
    def __init__(self):
        self.requests_this_window = 0
        self.window_start = datetime.now()
        self.window_duration = timedelta(minutes=5)
        self.max_requests_per_window = settings.semantic_scholar_requests_per_5min
        self._consecutive_rate_limits = 0
        self._max_consecutive_rate_limits = 3
        self._base_backoff_seconds = 60
    
    async def _rate_limit(self):
        """Ensure we don't exceed rate limits with adaptive backoff."""
        now = datetime.now()
        
        # Reset window if needed
        if now - self.window_start > self.window_duration:
            self.requests_this_window = 0
            self.window_start = now
            self._consecutive_rate_limits = 0
        
        # Wait if at limit
        if self.requests_this_window >= self.max_requests_per_window:
            wait_time = (self.window_start + self.window_duration - now).total_seconds()
            if wait_time > 0:
                logger.info("S2 rate limit reached, waiting", wait_seconds=round(wait_time, 1))
                await asyncio.sleep(wait_time)
                self.requests_this_window = 0
                self.window_start = datetime.now()
        
        self.requests_this_window += 1
        
        # Add small delay between requests to be gentle on the API
        await asyncio.sleep(0.5)
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers, including API key if available."""
        headers = {
            "User-Agent": "PaperRadar/1.0 (Academic Research Tool)"
        }
        if settings.semantic_scholar_api_key:
            headers["x-api-key"] = settings.semantic_scholar_api_key
        return headers
    
    async def get_paper_details(
        self,
        arxiv_id: str,
        retry_count: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """
        Get paper details from Semantic Scholar using arXiv ID.
        Returns None if paper not found, "RATE_LIMITED" if rate limit exceeded.
        """
        # Check cache first
        cache_key = f"ss:paper:{arxiv_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        # Check if we've hit too many consecutive rate limits
        if self._consecutive_rate_limits >= self._max_consecutive_rate_limits:
            logger.warning("Too many consecutive rate limits, backing off")
            return "RATE_LIMITED"
        
        await self._rate_limit()
        
        fields = ",".join(self.PAPER_FIELDS)
        url = f"{self.BASE_URL}/paper/arXiv:{arxiv_id}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    url,
                    params={"fields": fields},
                    headers=self._get_headers(),
                )
                
                if response.status_code == 404:
                    logger.debug("Paper not found in S2", arxiv_id=arxiv_id)
                    return None
                
                if response.status_code == 429:
                    self._consecutive_rate_limits += 1
                    backoff_time = self._base_backoff_seconds * (2 ** retry_count)
                    backoff_time = min(backoff_time, 300)  # Cap at 5 minutes
                    
                    if retry_count < 2:
                        logger.warning(
                            "Semantic Scholar rate limit hit, backing off",
                            backoff_seconds=backoff_time,
                            retry=retry_count + 1,
                        )
                        await asyncio.sleep(backoff_time)
                        return await self.get_paper_details(arxiv_id, retry_count + 1)
                    else:
                        logger.warning("Max retries reached for rate limit")
                        return "RATE_LIMITED"
                
                response.raise_for_status()
                data = response.json()
                
                # Success - reset consecutive rate limit counter
                self._consecutive_rate_limits = 0
                
                # Cache for 6 hours
                cache.set(cache_key, data, ttl_seconds=21600)
                
                return data
                
            except httpx.HTTPStatusError as e:
                logger.error("S2 API error", error=str(e), arxiv_id=arxiv_id)
                return None
            except httpx.HTTPError as e:
                logger.error("S2 request error", error=str(e), arxiv_id=arxiv_id)
                return None
    
    async def get_citations(
        self,
        paper_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get papers that cite the given paper."""
        # Check cache first
        cache_key = f"ss:citations:{paper_id}:{limit}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        await self._rate_limit()
        
        url = f"{self.BASE_URL}/paper/{paper_id}/citations"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    url,
                    params={
                        "fields": "paperId,title,year,citationCount",
                        "limit": limit,
                    },
                    headers=self._get_headers(),
                )
                
                if response.status_code == 429:
                    logger.warning("Rate limit on citations endpoint")
                    return []
                
                response.raise_for_status()
                data = response.json()
                
                result = data.get("data", [])
                
                # Cache for 2 hours
                cache.set(cache_key, result, ttl_seconds=7200)
                
                return result
                
            except httpx.HTTPError as e:
                logger.error("S2 citations error", error=str(e), paper_id=paper_id)
                return []
    
    async def get_citation_velocity(
        self,
        paper_id: str,
        days: int = 7,
    ) -> int:
        """Calculate citation velocity (new citations in last N days)."""
        citations = await self.get_citations(paper_id, limit=500)
        
        if not citations:
            return 0
        
        current_year = datetime.now().year
        
        # Count citations from papers published this year
        recent_count = sum(
            1 for c in citations
            if c.get("citingPaper", {}).get("year") == current_year
        )
        
        # Scale to approximately N days of the year
        days_in_year = 365
        estimated_velocity = int(recent_count * days / days_in_year)
        
        return estimated_velocity
    
    async def get_related_papers(
        self,
        paper_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get papers related to the given paper."""
        await self._rate_limit()
        
        url = f"{self.BASE_URL}/paper/{paper_id}/references"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    url,
                    params={
                        "fields": "paperId,title,abstract,authors,year,citationCount,externalIds",
                        "limit": limit,
                    },
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                data = response.json()
                
                return data.get("data", [])
                
            except httpx.HTTPError as e:
                logger.error("S2 related papers error", error=str(e), paper_id=paper_id)
                return []
    
    async def search_papers(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search papers by query text."""
        await self._rate_limit()
        
        url = f"{self.BASE_URL}/paper/search"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    url,
                    params={
                        "query": query,
                        "fields": ",".join(self.PAPER_FIELDS),
                        "limit": limit,
                    },
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                data = response.json()
                
                return data.get("data", [])
                
            except httpx.HTTPError as e:
                logger.error("S2 search error", error=str(e), query=query)
                return []


# Singleton service instance
semantic_scholar_service = SemanticScholarService()
