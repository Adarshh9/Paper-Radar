"""
HuggingFace API service for discovering model implementations.
"""
import asyncio
from typing import Dict, Any, Optional, List

import httpx
from loguru import logger

from app.core.config import get_settings
from app.core.cache import cache

settings = get_settings()


class HuggingFaceService:
    """Service for interacting with HuggingFace API."""
    
    BASE_URL = "https://huggingface.co/api"
    
    def __init__(self):
        self._rate_limit_delay = 1.0
        self._last_request_time = 0.0
    
    async def _rate_limit(self):
        """Ensure reasonable request rate."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()
    
    async def search_models_by_paper(
        self,
        arxiv_id: str,
        paper_title: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search HuggingFace for models implementing a paper."""
        cache_key = f"hf:models:{arxiv_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        models = []
        
        arxiv_models = await self._search_models(arxiv_id)
        models.extend(arxiv_models)
        
        if not models and paper_title:
            title_query = " ".join(paper_title.split()[:5])
            title_models = await self._search_models(title_query)
            
            for model in title_models:
                if await self._verify_paper_reference(model, arxiv_id):
                    models.append(model)
        
        seen = set()
        unique_models = []
        for model in models:
            if model["model_id"] not in seen:
                seen.add(model["model_id"])
                unique_models.append(model)
        
        cache.set(cache_key, unique_models, ttl_seconds=43200)
        
        logger.debug("Found HuggingFace models", arxiv_id=arxiv_id, count=len(unique_models))
        
        return unique_models[:10]
    
    async def _search_models(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search HuggingFace models."""
        await self._rate_limit()
        
        url = f"{self.BASE_URL}/models"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    url,
                    params={
                        "search": query,
                        "limit": limit,
                        "sort": "downloads",
                        "direction": -1,
                    },
                )
                response.raise_for_status()
                data = response.json()
                
                models = []
                for item in data:
                    models.append({
                        "model_id": item["id"],
                        "model_url": f"https://huggingface.co/{item['id']}",
                        "downloads": item.get("downloads", 0),
                        "likes": item.get("likes", 0),
                        "tags": item.get("tags", []),
                        "pipeline_tag": item.get("pipeline_tag", ""),
                    })
                
                return models
                
            except httpx.HTTPError as e:
                logger.error("HuggingFace search error", error=str(e))
                return []
    
    async def _verify_paper_reference(
        self,
        model: Dict[str, Any],
        arxiv_id: str,
    ) -> bool:
        """Check if model card references the paper."""
        model_card = await self.get_model_card(model["model_id"])
        if model_card and arxiv_id in model_card:
            return True
        return False
    
    async def get_model_card(
        self,
        model_id: str,
    ) -> Optional[str]:
        """Get model card (README) content."""
        await self._rate_limit()
        
        url = f"https://huggingface.co/{model_id}/raw/main/README.md"
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(url)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.text
            except httpx.HTTPError:
                return None
    
    async def get_model_details(
        self,
        model_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get detailed model information."""
        await self._rate_limit()
        
        url = f"{self.BASE_URL}/models/{model_id}"
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                
                return {
                    "model_id": data["id"],
                    "model_url": f"https://huggingface.co/{data['id']}",
                    "downloads": data.get("downloads", 0),
                    "likes": data.get("likes", 0),
                    "tags": data.get("tags", []),
                    "pipeline_tag": data.get("pipeline_tag", ""),
                    "library_name": data.get("library_name", ""),
                }
            except httpx.HTTPError as e:
                logger.error("HuggingFace model details error", error=str(e))
                return None


# Singleton instance
huggingface_service = HuggingFaceService()
