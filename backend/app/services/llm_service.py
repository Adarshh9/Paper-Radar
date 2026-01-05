"""
LLM service for generating paper summaries using Groq API.
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from groq import Groq, RateLimitError
from loguru import logger

from app.core.config import get_settings
from app.core.cache import cache

settings = get_settings()


class LLMService:
    """Service for generating AI summaries using Groq API."""
    
    # Model options
    FAST_MODEL = "llama-3.1-8b-instant"
    QUALITY_MODEL = "llama-3.3-70b-versatile"
    
    def __init__(self):
        self.client = Groq(api_key=settings.groq_api_key) if settings.groq_api_key else None
        self.requests_this_minute = 0
        self.minute_start = datetime.now()
        self.max_rpm = settings.groq_requests_per_minute
    
    async def _rate_limit(self):
        """Ensure we don't exceed Groq rate limits."""
        now = datetime.now()
        
        # Reset counter if new minute
        if now - self.minute_start > timedelta(minutes=1):
            self.requests_this_minute = 0
            self.minute_start = now
        
        # Wait if at limit
        if self.requests_this_minute >= self.max_rpm:
            wait_time = 60 - (now - self.minute_start).total_seconds()
            if wait_time > 0:
                logger.info("Groq rate limit, waiting", wait_seconds=round(wait_time, 1))
                await asyncio.sleep(wait_time)
                self.requests_this_minute = 0
                self.minute_start = datetime.now()
        
        self.requests_this_minute += 1
    
    async def generate_paper_summary(
        self,
        title: str,
        abstract: str,
        max_retries: int = 3,
    ) -> Optional[Dict[str, str]]:
        """Generate structured summary for a paper."""
        if not self.client:
            logger.warning("Groq API key not configured")
            return None
        
        # Check cache
        cache_key = f"summary_v2:{hash(title + abstract)}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        await self._rate_limit()
        
        system_prompt = """You are an expert research paper summarizer. Generate comprehensive, structured insights. Always respond with valid JSON."""
        
        user_prompt = f"""Analyze this research paper and generate structured insights.
        
Paper Title: {title}

Abstract: {abstract}

Generate a JSON response with exactly these keys:
- "one_line": A single sentence summary (max 25 words)
- "eli5": "Explain Like I'm 5" - simple explanation for non-experts (max 50 words)
- "innovation": What is unique/novel about this work (max 40 words)
- "problem": The core problem being addressed (max 30 words)
- "methodology": Technical approach/architecture used (max 50 words)
- "use_cases": Bullet points of real-world applications (concise string)
- "limitations": What the paper admits it can't do or future work (max 40 words)
- "results": Key quantitative or qualitative results (max 40 words)

Respond ONLY with the JSON object."""

        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    self._call_groq,
                    system_prompt,
                    user_prompt,
                    self.FAST_MODEL,
                )
                
                if response:
                    summary = self._parse_summary_response(response)
                    if summary:
                        cache.set(cache_key, summary, ttl_seconds=604800)
                        return summary
                
            except RateLimitError:
                logger.warning("Groq rate limit hit", attempt=attempt + 1)
                await asyncio.sleep(60)
            except Exception as e:
                logger.error("Groq API error", error=str(e), attempt=attempt + 1)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        
        return None
    
    def _call_groq(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
    ) -> Optional[str]:
        """Synchronous Groq API call."""
        try:
            completion = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=600,
            )
            return completion.choices[0].message.content
        except Exception as e:
            logger.error("Groq call failed", error=str(e))
            return None
    
    def _parse_summary_response(self, response: str) -> Optional[Dict[str, str]]:
        """Parse and validate summary JSON response."""
        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            cleaned = cleaned.strip()
            
            data = json.loads(cleaned)
            
            # Allow partial matches but prioritize critical fields
            return {
                "one_line_summary": data.get("one_line", ""),
                "eli5": data.get("eli5", None),
                "key_innovation": data.get("innovation", None),
                "problem_statement": data.get("problem", None),
                "methodology": data.get("methodology", None),
                "real_world_use_cases": data.get("use_cases", None),
                "limitations": data.get("limitations", None),
                "results_summary": data.get("results", None),
            }
            
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse summary JSON", error=str(e))
            return None
    
    async def generate_eli5_summary(
        self,
        title: str,
        abstract: str,
    ) -> Optional[str]:
        """Generate an ELI5 (Explain Like I'm 5) summary."""
        if not self.client:
            return None
        
        await self._rate_limit()
        
        system_prompt = """You are an expert at explaining complex research in simple terms."""
        
        user_prompt = f"""Explain this research paper in simple terms that a non-expert can understand. Use 3-4 sentences.

Title: {title}

Abstract: {abstract}

Simple explanation:"""

        try:
            response = await asyncio.to_thread(
                self._call_groq,
                system_prompt,
                user_prompt,
                self.QUALITY_MODEL,
            )
            return response
        except Exception as e:
            logger.error("ELI5 generation error", error=str(e))
            return None


# Singleton instance
llm_service = LLMService()
