"""
GitHub API service for discovering paper implementations.
"""
import asyncio
import re
from typing import Dict, Any, Optional, List

import httpx
from loguru import logger

from app.core.config import get_settings
from app.core.cache import cache

settings = get_settings()


class GitHubService:
    """Service for interacting with GitHub API."""
    
    BASE_URL = "https://api.github.com"
    
    # Regex patterns for finding GitHub links in text
    GITHUB_PATTERNS = [
        r'github\.com/([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)',
        r'github\.io/([a-zA-Z0-9_-]+)',
    ]
    
    def __init__(self):
        self.token = settings.github_token
        self._rate_limit_remaining = 5000
        self._rate_limit_reset = 0
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with optional authentication."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "PaperRadar/1.0",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers
    
    async def _check_rate_limit(self, response: httpx.Response):
        """Update rate limit tracking from response headers."""
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        
        if remaining:
            self._rate_limit_remaining = int(remaining)
        if reset:
            self._rate_limit_reset = int(reset)
        
        if self._rate_limit_remaining < 10:
            import time
            wait_time = max(0, self._rate_limit_reset - time.time())
            if wait_time > 0:
                logger.warning("GitHub rate limit low, waiting", wait_seconds=round(wait_time))
                await asyncio.sleep(min(wait_time, 60))
    
    def extract_github_links_from_text(self, text: str) -> List[str]:
        """Extract GitHub repository links from any text (abstract, paper content, etc.)."""
        repos = set()
        
        for pattern in self.GITHUB_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # Clean up the repo path
                repo_path = match.strip('/')
                # Filter out common false positives
                if '.' not in repo_path.split('/')[-1]:  # Likely a repo, not a file
                    repos.add(repo_path)
        
        return list(repos)
    
    async def search_repos_by_paper(
        self,
        arxiv_id: str,
        paper_title: Optional[str] = None,
        abstract: Optional[str] = None,
        min_stars: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search GitHub for repositories implementing a paper.
        Enhanced to also search in abstract for explicit GitHub links.
        """
        # Check cache
        cache_key = f"gh:repos:{arxiv_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        repos = []
        seen_urls = set()
        
        # 1. First, extract any GitHub links mentioned in abstract
        if abstract:
            explicit_repos = self.extract_github_links_from_text(abstract)
            for repo_path in explicit_repos:
                if '/' in repo_path:
                    repo_details = await self.get_repo_details(
                        repo_path.split('/')[0],
                        '/'.join(repo_path.split('/')[1:]),
                    )
                    if repo_details and repo_details["repo_url"] not in seen_urls:
                        repos.append(repo_details)
                        seen_urls.add(repo_details["repo_url"])
                        logger.info(f"Found explicit GitHub link in abstract: {repo_path}")
        
        # 2. Search by arXiv ID (most precise)
        arxiv_repos = await self._search_repositories(
            f"arxiv {arxiv_id}",
            min_stars=min_stars,
        )
        for repo in arxiv_repos:
            if repo["repo_url"] not in seen_urls:
                repos.append(repo)
                seen_urls.add(repo["repo_url"])
        
        # 3. Search by paper title variations
        if paper_title and len(repos) < 5:
            # Try different title variations
            clean_title = re.sub(r'[^\w\s]', '', paper_title)[:50]
            
            # Search with "paper implementation"
            title_repos = await self._search_repositories(
                f"{clean_title} implementation",
                min_stars=min_stars,
            )
            for repo in title_repos:
                if repo["repo_url"] not in seen_urls:
                    if await self._verify_paper_reference(repo, arxiv_id, paper_title):
                        repos.append(repo)
                        seen_urls.add(repo["repo_url"])
            
            # Search with "paper" suffix
            if len(repos) < 5:
                title_repos2 = await self._search_repositories(
                    f"{clean_title} paper",
                    min_stars=max(min_stars - 3, 1),  # Lower threshold
                )
                for repo in title_repos2:
                    if repo["repo_url"] not in seen_urls:
                        if await self._verify_paper_reference(repo, arxiv_id, paper_title):
                            repos.append(repo)
                            seen_urls.add(repo["repo_url"])
        
        # 4. Search Papers With Code (if available)
        pwc_repos = await self._search_papers_with_code(arxiv_id)
        for repo in pwc_repos:
            if repo["repo_url"] not in seen_urls:
                repos.append(repo)
                seen_urls.add(repo["repo_url"])
        
        # Cache for 24 hours
        cache.set(cache_key, repos, ttl_seconds=86400)
        
        logger.debug("Found GitHub repos", arxiv_id=arxiv_id, count=len(repos))
        
        return repos[:15]  # Return up to 15 repos
    
    async def _search_papers_with_code(self, arxiv_id: str) -> List[Dict[str, Any]]:
        """Search Papers With Code for implementations."""
        url = f"https://paperswithcode.com/api/v1/papers/?arxiv_id={arxiv_id}"
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(url)
                if response.status_code != 200:
                    return []
                
                data = response.json()
                repos = []
                
                if data.get("results"):
                    paper = data["results"][0]
                    paper_id = paper.get("id")
                    
                    if paper_id:
                        # Get implementations for this paper
                        impl_url = f"https://paperswithcode.com/api/v1/papers/{paper_id}/repositories/"
                        impl_response = await client.get(impl_url)
                        
                        if impl_response.status_code == 200:
                            impl_data = impl_response.json()
                            
                            for impl in impl_data.get("results", []):
                                if impl.get("url") and "github.com" in impl["url"]:
                                    repos.append({
                                        "repo_url": impl["url"],
                                        "repo_name": impl["url"].replace("https://github.com/", ""),
                                        "description": impl.get("description", ""),
                                        "stars": impl.get("stars", 0),
                                        "language": "",
                                        "last_updated": None,
                                        "source": "paperswithcode",
                                    })
                
                return repos
                
            except Exception as e:
                logger.debug(f"Papers With Code search failed: {e}")
                return []
    
    async def _search_repositories(
        self,
        query: str,
        min_stars: int = 10,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search GitHub repositories."""
        url = f"{self.BASE_URL}/search/repositories"
        full_query = f"{query} stars:>={min_stars} language:python"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    url,
                    params={
                        "q": full_query,
                        "sort": "stars",
                        "order": "desc",
                        "per_page": limit,
                    },
                    headers=self._get_headers(),
                )
                
                await self._check_rate_limit(response)
                
                if response.status_code == 403:
                    logger.warning("GitHub rate limit exceeded")
                    return []
                
                response.raise_for_status()
                data = response.json()
                
                repos = []
                for item in data.get("items", []):
                    repos.append({
                        "repo_url": item["html_url"],
                        "repo_name": item["full_name"],
                        "description": item.get("description", ""),
                        "stars": item["stargazers_count"],
                        "language": item.get("language", ""),
                        "last_updated": item.get("updated_at"),
                    })
                
                return repos
                
            except httpx.HTTPError as e:
                logger.error("GitHub search error", error=str(e))
                return []
    
    async def _verify_paper_reference(
        self,
        repo: Dict[str, Any],
        arxiv_id: str,
        paper_title: str,
    ) -> bool:
        """Verify that a repository actually references the paper."""
        repo_name = repo["repo_name"]
        
        readme = await self.get_readme(repo_name)
        if readme:
            if arxiv_id in readme or paper_title.lower() in readme.lower():
                return True
        
        return False
    
    async def get_readme(self, repo_name: str) -> Optional[str]:
        """Get repository README content."""
        url = f"{self.BASE_URL}/repos/{repo_name}/readme"
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(
                    url,
                    headers={
                        **self._get_headers(),
                        "Accept": "application/vnd.github.v3.raw",
                    },
                )
                
                await self._check_rate_limit(response)
                
                if response.status_code == 404:
                    return None
                
                response.raise_for_status()
                return response.text
                
            except httpx.HTTPError:
                return None
    
    async def get_repo_details(
        self,
        owner: str,
        repo_name: str,
    ) -> Optional[Dict[str, Any]]:
        """Get detailed repository information."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo_name}"
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                )
                
                await self._check_rate_limit(response)
                response.raise_for_status()
                
                data = response.json()
                
                return {
                    "repo_url": data["html_url"],
                    "repo_name": data["full_name"],
                    "description": data.get("description", ""),
                    "stars": data["stargazers_count"],
                    "forks": data["forks_count"],
                    "watchers": data["watchers_count"],
                    "open_issues": data["open_issues_count"],
                    "language": data.get("language", ""),
                    "last_updated": data.get("updated_at"),
                }
                
            except httpx.HTTPError as e:
                logger.error("GitHub repo details error", error=str(e))
                return None


# Singleton instance
github_service = GitHubService()
