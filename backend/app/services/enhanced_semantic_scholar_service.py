"""
Enhanced Semantic Scholar API service with robust rate limiting.
Includes proper header-based rate limit handling and exponential backoff.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

import httpx
from loguru import logger

from app.core.config import get_settings
from app.core.intelligent_cache import intelligent_cache, DataType
from app.core.rate_limiting import (
    AdaptiveRateLimiter,
    RateLimitConfig,
    RequestPriority,
    ExponentialBackoff,
    RateLimitError,
)

settings = get_settings()


class EnhancedSemanticScholarService:
    """
    Enhanced service for Semantic Scholar API with robust rate handling.
    
    Improvements over basic service:
    - Reads X-RateLimit-Remaining headers for adaptive limiting
    - Exponential backoff for repeated failures
    - Per-endpoint rate limiters
    - Request prioritization
    - Automatic recovery from rate limit errors
    """
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    # Fields to request from API
    PAPER_FIELDS = [
        "paperId", "title", "abstract", "authors", "year",
        "citationCount", "referenceCount", "influentialCitationCount",
        "venue", "publicationDate", "externalIds"
    ]
    
    CITATION_FIELDS = [
        "paperId", "title", "year", "citationCount", "authors"
    ]
    
    def __init__(self):
        # Configure rate limiters for different endpoints
        self._paper_limiter = AdaptiveRateLimiter(RateLimitConfig(
            requests_per_window=settings.semantic_scholar_requests_per_5min,
            window_seconds=300,
            max_retries=3,
            base_backoff_seconds=60,
            max_backoff_seconds=300,
        ))
        
        self._search_limiter = AdaptiveRateLimiter(RateLimitConfig(
            requests_per_window=settings.semantic_scholar_requests_per_5min // 2,
            window_seconds=300,
            max_retries=2,
            base_backoff_seconds=30,
        ))
        
        self._backoff = ExponentialBackoff(
            base_seconds=60,
            max_seconds=300,
            jitter=True,
        )
        
        # Track API-reported rate limits
        self._rate_limit_remaining: Optional[int] = None
        self._rate_limit_reset: Optional[datetime] = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers, including API key if available."""
        headers = {
            "User-Agent": "PaperRadar/2.0 (Academic Research Tool; Enhanced Rate Limiting)"
        }
        if settings.semantic_scholar_api_key:
            headers["x-api-key"] = settings.semantic_scholar_api_key
        return headers
    
    def _update_rate_limits_from_response(self, response: httpx.Response):
        """Update rate limit tracking from response headers."""
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        
        if remaining is not None:
            try:
                self._rate_limit_remaining = int(remaining)
                
                # Update the adaptive limiter with API-reported limits
                self._paper_limiter.update_from_headers(dict(response.headers))
                
                if self._rate_limit_remaining < 10:
                    logger.warning(
                        f"S2 rate limit low: {self._rate_limit_remaining} remaining"
                    )
            except ValueError:
                pass
        
        if reset is not None:
            try:
                reset_timestamp = int(reset)
                self._rate_limit_reset = datetime.fromtimestamp(reset_timestamp)
            except ValueError:
                pass
    
    async def _check_preemptive_rate_limit(self) -> bool:
        """
        Check if we should preemptively wait based on API headers.
        
        Returns True if request should proceed.
        """
        if self._rate_limit_remaining is not None and self._rate_limit_remaining <= 0:
            if self._rate_limit_reset and datetime.now() < self._rate_limit_reset:
                wait_time = (self._rate_limit_reset - datetime.now()).total_seconds()
                if wait_time > 0 and wait_time < 300:
                    logger.info(f"S2: Preemptive wait for {wait_time:.1f}s until rate limit reset")
                    await asyncio.sleep(wait_time)
                    self._rate_limit_remaining = None
                    return True
                elif wait_time >= 300:
                    logger.warning("S2: Rate limit reset too far in future, skipping request")
                    return False
        return True
    
    async def get_paper_details(
        self,
        arxiv_id: str,
        priority: RequestPriority = RequestPriority.NORMAL,
    ) -> Optional[Dict[str, Any]]:
        """
        Get paper details from Semantic Scholar using arXiv ID.
        
        Args:
            arxiv_id: The arXiv ID of the paper
            priority: Request priority for queue management
        
        Returns:
            Paper details dict, None if not found, or raises RateLimitError
        """
        # Check cache first
        cache_key = f"ss:paper:{arxiv_id}"
        cached = intelligent_cache.get(cache_key, DataType.CITATIONS.value)
        if cached:
            return cached
        
        # Check preemptive rate limit
        if not await self._check_preemptive_rate_limit():
            raise RateLimitError("Semantic Scholar rate limit exceeded")
        
        # Acquire rate limit permit
        if not await self._paper_limiter.acquire(priority):
            raise RateLimitError("Rate limit reached, try again later")
        
        fields = ",".join(self.PAPER_FIELDS)
        url = f"{self.BASE_URL}/paper/arXiv:{arxiv_id}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(3):
                try:
                    response = await client.get(
                        url,
                        params={"fields": fields},
                        headers=self._get_headers(),
                    )
                    
                    # Update rate limit tracking from headers
                    self._update_rate_limits_from_response(response)
                    
                    if response.status_code == 404:
                        logger.debug("Paper not found in S2", arxiv_id=arxiv_id)
                        return None
                    
                    if response.status_code == 429:
                        self._paper_limiter.record_failure(is_rate_limit=True)
                        
                        # Get retry-after if provided
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            wait_time = int(retry_after)
                        else:
                            wait_time = self._backoff.calculate(attempt)
                        
                        logger.warning(
                            f"S2 rate limit hit, backing off {wait_time}s",
                            attempt=attempt + 1,
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    # Success - record it
                    self._paper_limiter.record_success()
                    
                    # Cache with dynamic TTL based on paper activity
                    citation_count = data.get("citationCount", 0)
                    if citation_count > 100:
                        # High-citation papers - shorter TTL for fresher data
                        ttl = 3600  # 1 hour
                    else:
                        ttl = 21600  # 6 hours
                    
                    intelligent_cache.set(
                        cache_key, data,
                        data_type=DataType.CITATIONS.value,
                        ttl_seconds=ttl,
                    )
                    
                    return data
                    
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        self._paper_limiter.record_failure(is_rate_limit=True)
                        if not await self._paper_limiter.wait_and_retry(attempt):
                            raise RateLimitError(f"Max retries exceeded for {arxiv_id}")
                    else:
                        logger.error("S2 API error", error=str(e), arxiv_id=arxiv_id)
                        return None
                        
                except httpx.HTTPError as e:
                    logger.error("S2 request error", error=str(e), arxiv_id=arxiv_id)
                    self._paper_limiter.record_failure(is_rate_limit=False)
                    return None
        
        return None
    
    async def get_citations(
        self,
        paper_id: str,
        limit: int = 100,
        priority: RequestPriority = RequestPriority.NORMAL,
    ) -> List[Dict[str, Any]]:
        """
        Get papers that cite the given paper.
        
        Args:
            paper_id: Semantic Scholar paper ID
            limit: Maximum citations to fetch
            priority: Request priority
        
        Returns:
            List of citing papers
        """
        cache_key = f"ss:citations:{paper_id}:{limit}"
        cached = intelligent_cache.get(cache_key, DataType.CITATIONS.value)
        if cached:
            return cached
        
        if not await self._check_preemptive_rate_limit():
            return []
        
        if not await self._paper_limiter.acquire(priority):
            logger.warning("Rate limit reached for citations request")
            return []
        
        url = f"{self.BASE_URL}/paper/{paper_id}/citations"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    url,
                    params={
                        "fields": ",".join(self.CITATION_FIELDS),
                        "limit": limit,
                    },
                    headers=self._get_headers(),
                )
                
                self._update_rate_limits_from_response(response)
                
                if response.status_code == 429:
                    self._paper_limiter.record_failure(is_rate_limit=True)
                    logger.warning("Rate limit on citations endpoint")
                    return []
                
                response.raise_for_status()
                data = response.json()
                
                self._paper_limiter.record_success()
                
                result = [
                    item.get("citingPaper", {})
                    for item in data.get("data", [])
                    if item.get("citingPaper")
                ]
                
                # Cache for 2 hours
                intelligent_cache.set(
                    cache_key, result,
                    data_type=DataType.CITATIONS.value,
                    ttl_seconds=7200,
                )
                
                return result
                
            except httpx.HTTPError as e:
                logger.error("S2 citations error", error=str(e), paper_id=paper_id)
                self._paper_limiter.record_failure(is_rate_limit=False)
                return []
    
    async def get_citation_velocity(
        self,
        paper_id: str,
        days: int = 7,
    ) -> int:
        """
        Calculate citation velocity (new citations in last N days).
        
        Uses publication year as approximation since S2 doesn't provide
        exact citation dates.
        """
        citations = await self.get_citations(paper_id, limit=500)
        
        if not citations:
            return 0
        
        current_year = datetime.now().year
        
        # Count citations from papers published this year
        recent_count = sum(
            1 for c in citations
            if c.get("year") == current_year
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
        """Get papers related to the given paper (references)."""
        if not await self._paper_limiter.acquire(RequestPriority.LOW):
            return []
        
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
                
                self._update_rate_limits_from_response(response)
                response.raise_for_status()
                self._paper_limiter.record_success()
                
                data = response.json()
                return [
                    item.get("citedPaper", {})
                    for item in data.get("data", [])
                    if item.get("citedPaper")
                ]
                
            except httpx.HTTPError as e:
                logger.error("S2 related papers error", error=str(e), paper_id=paper_id)
                self._paper_limiter.record_failure(is_rate_limit=False)
                return []
    
    async def search_papers(
        self,
        query: str,
        limit: int = 20,
        year_range: Optional[tuple] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search papers by query text.
        
        Args:
            query: Search query
            limit: Maximum results
            year_range: Optional (start_year, end_year) filter
        """
        if not await self._search_limiter.acquire(RequestPriority.NORMAL):
            logger.warning("Rate limit reached for search request")
            return []
        
        url = f"{self.BASE_URL}/paper/search"
        params = {
            "query": query,
            "fields": ",".join(self.PAPER_FIELDS),
            "limit": limit,
        }
        
        if year_range:
            params["year"] = f"{year_range[0]}-{year_range[1]}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(),
                )
                
                self._update_rate_limits_from_response(response)
                response.raise_for_status()
                self._search_limiter.record_success()
                
                data = response.json()
                return data.get("data", [])
                
            except httpx.HTTPError as e:
                logger.error("S2 search error", error=str(e), query=query)
                self._search_limiter.record_failure(is_rate_limit=False)
                return []
    
    async def batch_get_papers(
        self,
        arxiv_ids: List[str],
        batch_size: int = 50,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Batch fetch multiple papers efficiently.
        
        Args:
            arxiv_ids: List of arXiv IDs
            batch_size: Papers per batch request
        
        Returns:
            Dict mapping arxiv_id to paper data
        """
        results = {}
        
        # Check cache first
        uncached_ids = []
        for arxiv_id in arxiv_ids:
            cache_key = f"ss:paper:{arxiv_id}"
            cached = intelligent_cache.get(cache_key, DataType.CITATIONS.value)
            if cached:
                results[arxiv_id] = cached
            else:
                uncached_ids.append(arxiv_id)
        
        # Batch fetch uncached papers
        for i in range(0, len(uncached_ids), batch_size):
            batch = uncached_ids[i:i + batch_size]
            
            if not await self._paper_limiter.acquire(RequestPriority.NORMAL):
                logger.warning("Rate limit reached during batch fetch")
                break
            
            # S2 batch endpoint
            url = f"{self.BASE_URL}/paper/batch"
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                try:
                    response = await client.post(
                        url,
                        params={"fields": ",".join(self.PAPER_FIELDS)},
                        json={"ids": [f"arXiv:{aid}" for aid in batch]},
                        headers=self._get_headers(),
                    )
                    
                    self._update_rate_limits_from_response(response)
                    
                    if response.status_code == 429:
                        self._paper_limiter.record_failure(is_rate_limit=True)
                        backoff = self._backoff.calculate(0)
                        await asyncio.sleep(backoff)
                        continue
                    
                    response.raise_for_status()
                    self._paper_limiter.record_success()
                    
                    for paper in response.json():
                        if paper:
                            external_ids = paper.get("externalIds", {})
                            arxiv_id = external_ids.get("ArXiv")
                            if arxiv_id:
                                results[arxiv_id] = paper
                                # Cache individual papers
                                cache_key = f"ss:paper:{arxiv_id}"
                                intelligent_cache.set(
                                    cache_key, paper,
                                    data_type=DataType.CITATIONS.value,
                                    ttl_seconds=21600,
                                )
                    
                except httpx.HTTPError as e:
                    logger.error(f"Batch fetch error: {e}")
                    self._paper_limiter.record_failure(is_rate_limit=False)
            
            # Small delay between batches
            await asyncio.sleep(0.5)
        
        return results
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status for monitoring."""
        return {
            "api_remaining": self._rate_limit_remaining,
            "api_reset": self._rate_limit_reset.isoformat() if self._rate_limit_reset else None,
            "paper_limiter": {
                "requests_this_window": self._paper_limiter.state.requests_this_window,
                "consecutive_failures": self._paper_limiter.state.consecutive_failures,
            },
            "search_limiter": {
                "requests_this_window": self._search_limiter.state.requests_this_window,
                "consecutive_failures": self._search_limiter.state.consecutive_failures,
            },
        }


# Singleton service instance
enhanced_semantic_scholar_service = EnhancedSemanticScholarService()
