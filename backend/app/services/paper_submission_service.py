"""
Service for handling user-submitted paper links.
Allows community contribution to add papers from arXiv.
"""
import asyncio
import re
from typing import Dict, Any, Optional
from datetime import datetime, timezone

import httpx
from loguru import logger

from app.core.database import SessionLocal
from app.models import Paper, PaperMetrics, PaperSummary
from app.services.arxiv_service import arxiv_service
from app.services.github_service import github_service
from app.services.llm_service_enhanced import enhanced_llm_service


class PaperSubmissionService:
    """Service for processing user-submitted paper links."""
    
    # Regex patterns for arXiv URLs
    ARXIV_PATTERNS = [
        r"arxiv\.org/abs/(\d+\.\d+)",  # https://arxiv.org/abs/2512.24880
        r"arxiv\.org/pdf/(\d+\.\d+)",  # https://arxiv.org/pdf/2512.24880
        r"arxiv\.org/abs/([a-z-]+/\d+)",  # Old format: arxiv.org/abs/cs/0123456
        r"arxiv\.org/pdf/([a-z-]+/\d+)",  # Old format PDF
    ]
    
    async def extract_arxiv_id(self, url: str) -> Optional[str]:
        """Extract arXiv ID from various URL formats."""
        url = url.strip().lower()
        
        # Remove .pdf extension if present
        url = re.sub(r'\.pdf$', '', url)
        
        for pattern in self.ARXIV_PATTERNS:
            match = re.search(pattern, url)
            if match:
                arxiv_id = match.group(1)
                # Remove version number if present (e.g., 2512.24880v1 -> 2512.24880)
                arxiv_id = re.sub(r'v\d+$', '', arxiv_id)
                return arxiv_id
        
        return None
    
    async def fetch_paper_from_arxiv(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """Fetch paper metadata from arXiv API."""
        url = "http://export.arxiv.org/api/query"
        params = {
            "id_list": arxiv_id,
            "max_results": 1,
        }
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                # Parse using arxiv_service's parser
                papers = arxiv_service._parse_feed(response.text)
                
                if papers:
                    return papers[0]
                
                logger.warning(f"Paper not found on arXiv: {arxiv_id}")
                return None
                
            except Exception as e:
                logger.error(f"Error fetching paper from arXiv: {e}")
                return None
    
    async def fetch_paper_pdf_text(self, arxiv_id: str) -> Optional[str]:
        """
        Fetch and extract text from paper PDF.
        Uses arXiv's HTML rendering when available, or falls back to abstract.
        """
        # Try to get HTML version first (ar5iv)
        html_url = f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}"
        
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            try:
                response = await client.get(html_url)
                if response.status_code == 200:
                    # Extract text from HTML (simplified - just get main content)
                    from html.parser import HTMLParser
                    
                    class TextExtractor(HTMLParser):
                        def __init__(self):
                            super().__init__()
                            self.text_parts = []
                            self.in_main = False
                            self.skip_tags = {'script', 'style', 'nav', 'header', 'footer'}
                            self.current_tag = None
                        
                        def handle_starttag(self, tag, attrs):
                            self.current_tag = tag
                            if tag == 'main' or tag == 'article':
                                self.in_main = True
                        
                        def handle_endtag(self, tag):
                            if tag == 'main' or tag == 'article':
                                self.in_main = False
                            self.current_tag = None
                        
                        def handle_data(self, data):
                            if self.current_tag not in self.skip_tags:
                                text = data.strip()
                                if text and len(text) > 20:
                                    self.text_parts.append(text)
                    
                    parser = TextExtractor()
                    parser.feed(response.text)
                    
                    full_text = '\n'.join(parser.text_parts)
                    
                    # Limit to ~15000 chars for LLM context
                    if len(full_text) > 15000:
                        full_text = full_text[:15000] + "..."
                    
                    if len(full_text) > 1000:
                        logger.info(f"Extracted {len(full_text)} chars from HTML for {arxiv_id}")
                        return full_text
                        
            except Exception as e:
                logger.debug(f"Could not fetch HTML version: {e}")
        
        # Fallback: return None (will use abstract only)
        return None
    
    async def extract_github_links_from_paper(self, arxiv_id: str, abstract: str) -> list[str]:
        """Extract GitHub repository links mentioned in the paper or abstract."""
        github_links = []
        
        # Common patterns for GitHub URLs
        github_pattern = r'github\.com/([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)'
        
        # Check abstract
        matches = re.findall(github_pattern, abstract, re.IGNORECASE)
        github_links.extend(matches)
        
        # Try to get full paper text for more links
        full_text = await self.fetch_paper_pdf_text(arxiv_id)
        if full_text:
            matches = re.findall(github_pattern, full_text, re.IGNORECASE)
            github_links.extend(matches)
        
        # Deduplicate
        return list(set(github_links))
    
    async def submit_paper(
        self, 
        url: str,
        submitted_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit a paper URL for processing.
        
        Returns:
            Dict with status and paper info
        """
        # Extract arXiv ID
        arxiv_id = await self.extract_arxiv_id(url)
        
        if not arxiv_id:
            return {
                "success": False,
                "error": "Invalid URL. Please provide a valid arXiv link (e.g., https://arxiv.org/abs/2512.24880)",
            }
        
        db = SessionLocal()
        
        try:
            # Check if paper already exists
            existing = db.query(Paper).filter(Paper.arxiv_id == arxiv_id).first()
            
            if existing:
                return {
                    "success": True,
                    "message": "Paper already exists in database",
                    "paper_id": str(existing.id),
                    "arxiv_id": arxiv_id,
                    "title": existing.title,
                    "already_exists": True,
                }
            
            # Fetch paper from arXiv
            paper_data = await self.fetch_paper_from_arxiv(arxiv_id)
            
            if not paper_data:
                return {
                    "success": False,
                    "error": f"Could not find paper with arXiv ID: {arxiv_id}",
                }
            
            # Create paper record
            paper = Paper(
                arxiv_id=arxiv_id,
                title=paper_data["title"],
                abstract=paper_data["abstract"],
                authors=paper_data["authors"],
                published_date=paper_data["published_date"],
                updated_date=paper_data.get("updated_date"),
                primary_category=paper_data["primary_category"],
                categories=paper_data["categories"],
                pdf_url=paper_data["pdf_url"],
                arxiv_url=paper_data["arxiv_url"],
                doi=paper_data.get("doi"),
                journal_ref=paper_data.get("journal_ref"),
                comments=paper_data.get("comments"),
            )
            db.add(paper)
            db.flush()
            
            # Create metrics record
            metrics = PaperMetrics(paper_id=paper.id)
            db.add(metrics)
            
            db.commit()
            
            logger.info(f"Added paper from submission: {arxiv_id} - {paper_data['title'][:50]}")
            
            # Queue background tasks (non-blocking)
            asyncio.create_task(self._enrich_paper_async(str(paper.id), arxiv_id))
            
            return {
                "success": True,
                "message": "Paper added successfully! Summary and implementations will be generated shortly.",
                "paper_id": str(paper.id),
                "arxiv_id": arxiv_id,
                "title": paper_data["title"],
                "already_exists": False,
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error submitting paper: {e}")
            return {
                "success": False,
                "error": f"Error processing paper: {str(e)}",
            }
        finally:
            db.close()
    
    async def _enrich_paper_async(self, paper_id: str, arxiv_id: str):
        """Background task to enrich paper with summary and implementations."""
        try:
            db = SessionLocal()
            paper = db.query(Paper).filter(Paper.arxiv_id == arxiv_id).first()
            
            if not paper:
                return
            
            # Generate summary using full paper context when possible
            full_text = await self.fetch_paper_pdf_text(arxiv_id)
            
            if full_text and len(full_text) > 500:
                # Use full paper text for better summary
                summary_data = await enhanced_llm_service.generate_paper_summary_with_context(
                    title=paper.title,
                    abstract=paper.abstract,
                    full_text=full_text,
                )
            else:
                # Fallback to abstract-only
                summary_data = await enhanced_llm_service.generate_paper_summary(
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
                    pros=summary_data.get("pros"),
                    cons=summary_data.get("cons"),
                    generated_by=f"groq-{enhanced_llm_service.FAST_MODEL}",
                    generated_at=datetime.now(timezone.utc),
                )
                db.add(summary)
                logger.info(f"Generated summary for submitted paper: {arxiv_id}")
            
            # Search for implementations
            # First, extract GitHub links from paper itself
            github_repos = await self.extract_github_links_from_paper(arxiv_id, paper.abstract)
            
            # Then search GitHub API
            api_repos = await github_service.search_repos_by_paper(
                arxiv_id=arxiv_id,
                paper_title=paper.title,
                min_stars=5,  # Lower threshold for submitted papers
            )
            
            # Process found repos
            from app.models import PaperImplementation
            
            processed_urls = set()
            
            # Add repos found from paper text first
            for repo_path in github_repos:
                repo_url = f"https://github.com/{repo_path}"
                if repo_url not in processed_urls:
                    repo_details = await github_service.get_repo_details(
                        repo_path.split('/')[0],
                        repo_path.split('/')[1] if '/' in repo_path else repo_path,
                    )
                    if repo_details:
                        impl = PaperImplementation(
                            paper_id=paper.id,
                            source="github",
                            repo_url=repo_details["repo_url"],
                            repo_name=repo_details["repo_name"],
                            stars=repo_details["stars"],
                            description=repo_details.get("description", ""),
                            language=repo_details.get("language", ""),
                            last_updated=repo_details.get("last_updated"),
                        )
                        db.add(impl)
                        processed_urls.add(repo_url)
                        logger.info(f"Found implementation from paper: {repo_url}")
            
            # Add repos from API search
            for repo in api_repos:
                if repo["repo_url"] not in processed_urls:
                    impl = PaperImplementation(
                        paper_id=paper.id,
                        source="github",
                        repo_url=repo["repo_url"],
                        repo_name=repo["repo_name"],
                        stars=repo["stars"],
                        description=repo.get("description", ""),
                        language=repo.get("language", ""),
                        last_updated=repo.get("last_updated"),
                    )
                    db.add(impl)
                    processed_urls.add(repo["repo_url"])
            
            # Update metrics
            if paper.metrics:
                paper.metrics.github_repos_count = len(processed_urls)
                total_stars = sum(
                    impl.stars for impl in db.query(PaperImplementation)
                    .filter(PaperImplementation.paper_id == paper.id).all()
                )
                paper.metrics.github_stars = total_stars
            
            db.commit()
            logger.info(f"Enrichment complete for submitted paper: {arxiv_id}")
            
        except Exception as e:
            logger.error(f"Error enriching submitted paper: {e}")
        finally:
            db.close()


# Singleton instance
paper_submission_service = PaperSubmissionService()
