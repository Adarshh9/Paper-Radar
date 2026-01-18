"""
Enhanced LLM service with better prompt engineering for all summary fields.
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from groq import Groq, RateLimitError
from loguru import logger

from app.core.config import get_settings
from app.core.intelligent_cache import intelligent_cache, DataType

settings = get_settings()


class EnhancedLLMService:
    """Enhanced service for generating comprehensive AI summaries using Groq API."""
    
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
        """
        Generate comprehensive structured summary for a paper.
        
        Returns dict with ALL fields populated:
        - one_line_summary
        - eli5
        - key_innovation
        - problem_statement
        - methodology
        - real_world_use_cases
        - limitations
        - results_summary
        """
        if not self.client:
            logger.warning("Groq API key not configured")
            return None
        
        # Check cache
        cache_key = f"summary_enhanced:{hash(title + abstract)}"
        cached = intelligent_cache.get(cache_key, DataType.SUMMARIES.value)
        if cached:
            return cached
        
        await self._rate_limit()
        
        system_prompt = """You are an expert research paper analyzer. Your task is to extract structured insights from academic papers and present them clearly for researchers.

CRITICAL: You must respond with ONLY valid JSON. No markdown, no code blocks, no preamble. Just pure JSON."""
        
        user_prompt = f"""Analyze this research paper and extract the following information:

Title: {title}

Abstract: {abstract}

Generate a JSON object with EXACTLY these fields (all fields are required):

1. "one_line": A concise one-sentence summary (max 25 words) capturing the core contribution
2. "eli5": Explain this paper like I'm 5 years old - use simple analogies and everyday language that a child could understand (50-80 words)
3. "innovation": What makes this work unique or novel? What's the key breakthrough? (30-50 words)
4. "problem": What specific problem does this paper solve? Why is it important? (25-40 words)
5. "methodology": What technical approach or method did they use? Mention key algorithms, architectures, or techniques (40-60 words)
6. "use_cases": List 3-5 real-world applications where this could be used. Format as bullet points in a single string (e.g., "• Application 1\\n• Application 2\\n• Application 3")
7. "limitations": What are the acknowledged limitations or future work mentioned? What can't this approach do well? (30-50 words)
8. "results": What were the key quantitative or qualitative results? Include numbers/metrics if mentioned (30-50 words)
9. "pros": List 3-5 advantages or strengths of this approach (format as bullet points: "• Pro 1\\n• Pro 2\\n• Pro 3")
10. "cons": List 3-5 disadvantages or weaknesses (format as bullet points: "• Con 1\\n• Con 2\\n• Con 3")

IMPORTANT RULES:
- Respond with ONLY the JSON object
- No markdown code blocks (no ```json```)
- All 10 fields must be present
- Keep within word limits
- Be specific and technical where appropriate
- Use bullet points (•) for lists

Example response format:
{{"one_line": "...", "eli5": "...", "innovation": "...", "problem": "...", "methodology": "...", "use_cases": "• ...", "limitations": "...", "results": "...", "pros": "• ...", "cons": "• ..."}}

Now generate the JSON for the paper above:"""

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
                    if summary and self._validate_summary(summary):
                        intelligent_cache.set(
                            cache_key, 
                            summary, 
                            data_type=DataType.SUMMARIES.value
                        )
                        return summary
                    else:
                        logger.warning(f"Invalid summary structure on attempt {attempt + 1}")
                
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
                max_tokens=1200,  # Increased for comprehensive response
            )
            return completion.choices[0].message.content
        except Exception as e:
            logger.error("Groq call failed", error=str(e))
            return None
    
    def _parse_summary_response(self, response: str) -> Optional[Dict[str, str]]:
        """Parse and validate summary JSON response."""
        try:
            # Clean response
            cleaned = response.strip()
            
            # Remove markdown code blocks if present
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1])  # Remove first and last lines
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
            
            # Parse JSON
            data = json.loads(cleaned)
            
            # Map to database fields
            return {
                "one_line_summary": data.get("one_line", ""),
                "eli5": data.get("eli5"),
                "key_innovation": data.get("innovation"),
                "problem_statement": data.get("problem"),
                "methodology": data.get("methodology"),
                "real_world_use_cases": data.get("use_cases"),
                "limitations": data.get("limitations"),
                "results_summary": data.get("results"),
                "pros": data.get("pros"),  # New field
                "cons": data.get("cons"),  # New field
            }
            
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse summary JSON", error=str(e), response=response[:200])
            return None
        except Exception as e:
            logger.error("Unexpected error parsing summary", error=str(e))
            return None
    
    def _validate_summary(self, summary: Dict[str, str]) -> bool:
        """Validate that summary has required fields."""
        required_fields = [
            "one_line_summary",
            "eli5",
            "key_innovation",
            "problem_statement",
            "methodology",
        ]
        
        for field in required_fields:
            if not summary.get(field):
                logger.warning(f"Missing required field: {field}")
                return False
        
        return True
    
    async def generate_eli5_summary(
        self,
        title: str,
        abstract: str,
    ) -> Optional[str]:
        """Generate standalone ELI5 summary (fallback method)."""
        if not self.client:
            return None
        
        await self._rate_limit()
        
        system_prompt = """You are an expert at explaining complex research in simple terms that anyone can understand."""
        
        user_prompt = f"""Explain this research paper like I'm 5 years old. Use simple analogies and everyday examples.

Title: {title}

Abstract: {abstract}

Requirements:
- Use language a child would understand
- Avoid all technical jargon
- Use metaphors and comparisons to familiar things
- 3-5 sentences maximum

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

    async def generate_paper_summary_with_context(
        self,
        title: str,
        abstract: str,
        full_text: str,
        max_retries: int = 3,
    ) -> Optional[Dict[str, str]]:
        """
        Generate comprehensive summary using FULL PAPER CONTEXT.
        This provides more accurate and detailed insights than abstract-only.
        """
        if not self.client:
            logger.warning("Groq API key not configured")
            return None
        
        # Check cache
        cache_key = f"summary_full:{hash(title + abstract + full_text[:500])}"
        cached = intelligent_cache.get(cache_key, DataType.SUMMARIES.value)
        if cached:
            return cached
        
        await self._rate_limit()
        
        # Truncate full text if too long (keep intro, methods, results sections)
        if len(full_text) > 12000:
            # Try to keep important sections
            full_text = full_text[:12000] + "\n...[truncated]..."
        
        system_prompt = """You are an expert research paper analyzer with deep technical knowledge. 
You are given the FULL TEXT of a research paper, not just the abstract. 
Use the complete context to provide thorough and accurate analysis.

CRITICAL: You must respond with ONLY valid JSON. No markdown, no code blocks, no preamble."""
        
        user_prompt = f"""Analyze this research paper IN FULL and extract comprehensive insights:

Title: {title}

Abstract: {abstract}

FULL PAPER CONTENT:
{full_text}

Generate a JSON object with EXACTLY these fields (all required). Use the full paper context for more accurate answers:

1. "one_line": A concise one-sentence summary (max 25 words) capturing the core contribution
2. "eli5": Explain this paper like I'm 5 years old - use simple analogies and everyday language (50-80 words)
3. "innovation": What makes this work unique or novel? What's the key breakthrough? Be specific based on the paper content (40-60 words)
4. "problem": What specific problem does this paper solve? Why is it important? (30-50 words)
5. "methodology": What technical approach did they use? Include specific algorithms, architectures, datasets, training details from the paper (60-100 words)
6. "use_cases": List 4-6 real-world applications. Format as bullet points: "• App 1\\n• App 2\\n• App 3"
7. "limitations": What are the acknowledged limitations? Include specific weaknesses mentioned in the paper (40-60 words)
8. "results": Key quantitative results - include specific numbers, metrics, benchmarks from the paper (40-70 words)
9. "pros": List 4-5 advantages/strengths with specifics from the paper (format: "• Pro 1\\n• Pro 2\\n• Pro 3")
10. "cons": List 4-5 disadvantages/weaknesses with specifics (format: "• Con 1\\n• Con 2\\n• Con 3")

Respond with ONLY the JSON object:"""

        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    self._call_groq,
                    system_prompt,
                    user_prompt,
                    self.QUALITY_MODEL,  # Use quality model for full paper analysis
                )
                
                if response:
                    summary = self._parse_summary_response(response)
                    if summary and self._validate_summary(summary):
                        intelligent_cache.set(
                            cache_key, 
                            summary, 
                            data_type=DataType.SUMMARIES.value
                        )
                        return summary
                    else:
                        logger.warning(f"Invalid full-context summary on attempt {attempt + 1}")
                
            except RateLimitError:
                logger.warning("Groq rate limit hit", attempt=attempt + 1)
                await asyncio.sleep(60)
            except Exception as e:
                logger.error("Groq API error (full context)", error=str(e), attempt=attempt + 1)
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        
        # Fallback to abstract-only if full context fails
        logger.info("Falling back to abstract-only summary")
        return await self.generate_paper_summary(title, abstract, max_retries)


# Singleton instance
enhanced_llm_service = EnhancedLLMService()
