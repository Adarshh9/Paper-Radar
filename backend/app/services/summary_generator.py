"""
Adaptive Multi-Level Summary Generator.
Generates summaries at different complexity levels for diverse audiences.
"""
import asyncio
from typing import Dict, Optional, AsyncGenerator, List, Tuple
from dataclasses import dataclass
from enum import Enum

from loguru import logger

from app.core.config import get_settings
from app.core.intelligent_cache import intelligent_cache, DataType

settings = get_settings()


class SummaryLevel(Enum):
    """Summary complexity levels."""
    ELI5 = "eli5"           # 5th grade level
    UNDERGRAD = "undergrad"  # Undergraduate level
    GRADUATE = "graduate"    # Graduate student level
    EXPERT = "expert"        # Expert/researcher level


@dataclass
class MultiLevelSummary:
    """Collection of summaries at different levels."""
    paper_id: str
    eli5: Optional[str] = None
    undergrad: Optional[str] = None
    graduate: Optional[str] = None
    expert: Optional[str] = None
    comparison_table: Optional[str] = None
    prerequisites: Optional[List[str]] = None
    audio_summary_url: Optional[str] = None


@dataclass
class PaperComparison:
    """Comparison between related papers."""
    papers: List[str]  # Paper IDs
    comparison_table: str
    summary: str
    key_differences: List[str]
    common_themes: List[str]


class AdaptiveSummaryGenerator:
    """
    Generate summaries at different complexity levels.
    
    Features:
    - Slider to adjust summary complexity
    - Prerequisites checker: "You should read these papers first"
    - Comparison tables for related papers
    - Audio summary generation (TTS integration)
    """
    
    # Level descriptions for prompts
    LEVEL_INSTRUCTIONS = {
        SummaryLevel.ELI5: "5th grade level - Use metaphors, simple examples, and everyday language. Avoid all jargon.",
        SummaryLevel.UNDERGRAD: "Undergraduate level - Use basic technical terms with brief explanations. Assume familiarity with general concepts.",
        SummaryLevel.GRADUATE: "Graduate level - Use domain-specific jargon. Assume solid foundation in the field.",
        SummaryLevel.EXPERT: "Expert level - Assume deep domain knowledge. Focus on novel contributions and technical details.",
    }
    
    # Target word counts per level
    WORD_COUNTS = {
        SummaryLevel.ELI5: 100,
        SummaryLevel.UNDERGRAD: 150,
        SummaryLevel.GRADUATE: 200,
        SummaryLevel.EXPERT: 250,
    }
    
    def __init__(self):
        self._llm_client = None
        self._tts_client = None
    
    def _get_llm_client(self):
        """Lazy load LLM client."""
        if self._llm_client is None:
            try:
                from groq import Groq
                self._llm_client = Groq(api_key=settings.groq_api_key) if settings.groq_api_key else None
            except ImportError:
                logger.warning("Groq not installed")
        return self._llm_client
    
    async def generate_summary_at_level(
        self,
        title: str,
        abstract: str,
        level: SummaryLevel,
        use_cache: bool = True,
    ) -> Optional[str]:
        """
        Generate a summary at a specific complexity level.
        
        Args:
            title: Paper title
            abstract: Paper abstract
            level: Complexity level
            use_cache: Whether to use cached summaries
        
        Returns:
            Summary text or None if generation failed
        """
        import hashlib
        cache_key = f"summary:{level.value}:{hashlib.md5((title + abstract).encode()).hexdigest()}"
        
        if use_cache:
            cached = intelligent_cache.get(cache_key, DataType.SUMMARIES.value)
            if cached:
                return cached
        
        client = self._get_llm_client()
        if client is None:
            return None
        
        instruction = self.LEVEL_INSTRUCTIONS[level]
        word_count = self.WORD_COUNTS[level]
        
        system_prompt = """You are an expert at explaining complex research papers to different audiences. 
Adapt your language and depth based on the audience level specified."""
        
        user_prompt = f"""Summarize this paper at {instruction}

Title: {title}

Abstract: {abstract}

Requirements:
1. Focus on: problem being solved, approach taken, key results, and significance
2. Length: approximately {word_count} words
3. Audience level: {level.value}

Summary:"""

        try:
            response = await asyncio.to_thread(
                self._call_llm,
                client,
                system_prompt,
                user_prompt,
            )
            
            if response:
                intelligent_cache.set(
                    cache_key,
                    response,
                    data_type=DataType.SUMMARIES.value,
                )
                return response
                
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
        
        return None
    
    async def generate_multi_level_summary(
        self,
        paper_id: str,
        title: str,
        abstract: str,
    ) -> AsyncGenerator[Tuple[SummaryLevel, str], None]:
        """
        Generate summaries at all complexity levels.
        
        Yields (level, summary) tuples as they are generated.
        """
        for level in SummaryLevel:
            summary = await self.generate_summary_at_level(title, abstract, level)
            if summary:
                yield level, summary
    
    async def generate_all_summaries(
        self,
        paper_id: str,
        title: str,
        abstract: str,
    ) -> MultiLevelSummary:
        """
        Generate all summary levels and return as a structured object.
        """
        result = MultiLevelSummary(paper_id=paper_id)
        
        # Generate in parallel for efficiency
        tasks = {
            level: asyncio.create_task(
                self.generate_summary_at_level(title, abstract, level)
            )
            for level in SummaryLevel
        }
        
        for level, task in tasks.items():
            summary = await task
            setattr(result, level.value, summary)
        
        # Generate prerequisites
        result.prerequisites = await self.identify_prerequisites(title, abstract)
        
        return result
    
    async def identify_prerequisites(
        self,
        title: str,
        abstract: str,
    ) -> List[str]:
        """
        Identify prerequisite concepts/papers that would help understand this paper.
        
        Returns list of concepts or paper references.
        """
        client = self._get_llm_client()
        if client is None:
            return []
        
        system_prompt = """You are an expert at identifying prerequisite knowledge for understanding research papers."""
        
        user_prompt = f"""What concepts or prior papers should someone understand before reading this paper?

Title: {title}
Abstract: {abstract}

List 3-5 prerequisite concepts or foundational papers (just names/titles, not full explanations):"""

        try:
            response = await asyncio.to_thread(
                self._call_llm,
                client,
                system_prompt,
                user_prompt,
            )
            
            if response:
                # Parse response into list
                lines = response.strip().split('\n')
                prerequisites = [
                    line.strip().lstrip('-•*0123456789.)')
                    for line in lines
                    if line.strip()
                ]
                return prerequisites[:5]
                
        except Exception as e:
            logger.error(f"Prerequisites generation failed: {e}")
        
        return []
    
    async def generate_comparison_table(
        self,
        papers: List[Tuple[str, str, str]],  # (paper_id, title, abstract)
    ) -> Optional[PaperComparison]:
        """
        Generate a comparison table for multiple related papers.
        
        Args:
            papers: List of (paper_id, title, abstract) tuples
        
        Returns:
            PaperComparison object with table and analysis
        """
        if len(papers) < 2:
            return None
        
        client = self._get_llm_client()
        if client is None:
            return None
        
        system_prompt = """You are an expert at comparing and contrasting research papers. 
Create clear, structured comparisons highlighting key differences and similarities."""
        
        papers_text = "\n\n".join([
            f"Paper {i+1}: {title}\nAbstract: {abstract}"
            for i, (_, title, abstract) in enumerate(papers)
        ])
        
        user_prompt = f"""Compare these {len(papers)} papers:

{papers_text}

Provide:
1. A comparison table (Markdown format) with columns for: Approach, Key Innovation, Evaluation Method, Main Results
2. Key differences (bullet points)
3. Common themes (bullet points)
4. Brief summary of how they relate to each other

Format your response with clear sections."""

        try:
            response = await asyncio.to_thread(
                self._call_llm,
                client,
                system_prompt,
                user_prompt,
            )
            
            if response:
                # Parse response into structured format
                return PaperComparison(
                    papers=[pid for pid, _, _ in papers],
                    comparison_table=self._extract_table(response),
                    summary=self._extract_summary(response),
                    key_differences=self._extract_list(response, "differences"),
                    common_themes=self._extract_list(response, "themes"),
                )
                
        except Exception as e:
            logger.error(f"Comparison generation failed: {e}")
        
        return None
    
    async def generate_audio_summary(
        self,
        summary: str,
        paper_id: str,
    ) -> Optional[str]:
        """
        Generate audio version of summary using TTS.
        
        Returns URL/path to audio file.
        """
        # Placeholder for TTS integration
        # In production, would use OpenAI TTS, ElevenLabs, or similar
        logger.info(f"Audio summary generation not implemented yet for {paper_id}")
        return None
    
    def _call_llm(
        self,
        client,
        system_prompt: str,
        user_prompt: str,
        model: str = "llama-3.1-8b-instant",
    ) -> Optional[str]:
        """Synchronous LLM call."""
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=800,
            )
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None
    
    def _extract_table(self, response: str) -> str:
        """Extract Markdown table from response."""
        lines = response.split('\n')
        table_lines = []
        in_table = False
        
        for line in lines:
            if '|' in line:
                in_table = True
                table_lines.append(line)
            elif in_table and line.strip():
                if '|' not in line:
                    break
        
        return '\n'.join(table_lines) if table_lines else response
    
    def _extract_summary(self, response: str) -> str:
        """Extract summary section from response."""
        # Look for summary-related keywords
        for marker in ['summary', 'relation', 'conclusion']:
            lower = response.lower()
            idx = lower.find(marker)
            if idx != -1:
                # Get text after the marker
                remaining = response[idx:]
                lines = remaining.split('\n')
                # Get first paragraph after marker
                for i, line in enumerate(lines[1:], 1):
                    if line.strip() and not line.startswith(('-', '*', '|')):
                        return line.strip()
        
        return "See comparison table above."
    
    def _extract_list(self, response: str, list_type: str) -> List[str]:
        """Extract bullet point list from response."""
        lower = response.lower()
        idx = lower.find(list_type)
        
        if idx == -1:
            return []
        
        remaining = response[idx:]
        lines = remaining.split('\n')
        items = []
        
        for line in lines[1:]:  # Skip header line
            stripped = line.strip()
            if stripped.startswith(('-', '*', '•')):
                item = stripped.lstrip('-*• ')
                if item:
                    items.append(item)
            elif items and not stripped:
                break  # End of list
        
        return items[:5]  # Limit to 5 items


# Singleton instance
adaptive_summary_generator = AdaptiveSummaryGenerator()
