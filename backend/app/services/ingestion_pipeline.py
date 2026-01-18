"""
Async Ingestion Pipeline with Backpressure Handling.
Efficiently processes paper streams with rate limiting and priority queues.
"""
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import time

from loguru import logger
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.rate_limiting import rate_limiter, RequestPriority
from app.models import Paper, PaperMetrics


class PipelineStage(Enum):
    """Pipeline processing stages."""
    FETCH = "fetch"
    ENRICH = "enrich"
    SUMMARIZE = "summarize"
    INDEX = "index"
    RANK = "rank"


class TaskPriority(Enum):
    """Task priority levels."""
    CRITICAL = 1  # User-requested
    HIGH = 2      # Trending papers
    NORMAL = 3    # Regular updates
    LOW = 4       # Background tasks


@dataclass
class PipelineTask:
    """A task in the ingestion pipeline."""
    paper_id: str
    arxiv_id: str
    priority: TaskPriority
    stage: PipelineStage
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    attempts: int = 0
    max_attempts: int = 3
    last_error: Optional[str] = None


@dataclass
class PipelineStats:
    """Statistics for pipeline monitoring."""
    tasks_queued: int = 0
    tasks_processing: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    avg_processing_time_ms: float = 0
    backpressure_events: int = 0


class BackpressureController:
    """
    Controls backpressure in the pipeline.
    
    Monitors queue depths and processing rates to prevent overload.
    """
    
    def __init__(
        self,
        max_queue_depth: int = 1000,
        high_water_mark: float = 0.8,
        low_water_mark: float = 0.5,
    ):
        self.max_queue_depth = max_queue_depth
        self.high_water_mark = high_water_mark
        self.low_water_mark = low_water_mark
        self._paused = False
        self._current_depth = 0
    
    def update_depth(self, depth: int):
        """Update current queue depth."""
        self._current_depth = depth
        
        if not self._paused and depth > self.max_queue_depth * self.high_water_mark:
            self._paused = True
            logger.warning(f"Backpressure: pausing intake at depth {depth}")
        elif self._paused and depth < self.max_queue_depth * self.low_water_mark:
            self._paused = False
            logger.info(f"Backpressure: resuming intake at depth {depth}")
    
    @property
    def should_accept(self) -> bool:
        """Whether the pipeline should accept new tasks."""
        return not self._paused
    
    @property
    def utilization(self) -> float:
        """Current queue utilization (0.0 - 1.0)."""
        return self._current_depth / self.max_queue_depth


class PriorityTaskQueue:
    """
    Priority queue for pipeline tasks.
    
    Higher priority tasks are processed first.
    """
    
    def __init__(self):
        self._queues: Dict[TaskPriority, deque] = {
            priority: deque() for priority in TaskPriority
        }
        self._size = 0
    
    def put(self, task: PipelineTask):
        """Add a task to the queue."""
        self._queues[task.priority].append(task)
        self._size += 1
    
    def get(self) -> Optional[PipelineTask]:
        """Get the highest priority task."""
        for priority in TaskPriority:
            if self._queues[priority]:
                self._size -= 1
                return self._queues[priority].popleft()
        return None
    
    def size(self) -> int:
        """Get total queue size."""
        return self._size
    
    def size_by_priority(self) -> Dict[TaskPriority, int]:
        """Get queue size by priority level."""
        return {p: len(q) for p, q in self._queues.items()}


class AsyncIngestionPipeline:
    """
    Handle bursts of papers efficiently with backpressure.
    
    Features:
    - Multi-stage processing pipeline
    - Priority-based task scheduling
    - Backpressure handling to prevent overload
    - Concurrent processing with semaphores
    - Automatic retry with exponential backoff
    - Progress tracking and statistics
    """
    
    # Concurrency limits per stage
    STAGE_CONCURRENCY = {
        PipelineStage.FETCH: 50,      # Fast, many concurrent
        PipelineStage.ENRICH: 10,     # API rate limited
        PipelineStage.SUMMARIZE: 3,   # LLM - slow, expensive
        PipelineStage.INDEX: 20,      # CPU-bound
        PipelineStage.RANK: 30,       # Fast calculations
    }
    
    def __init__(self):
        self._task_queue = PriorityTaskQueue()
        self._backpressure = BackpressureController()
        self._stats = PipelineStats()
        self._running = False
        self._workers: List[asyncio.Task] = []
        
        # Stage semaphores
        self._stage_semaphores = {
            stage: asyncio.Semaphore(limit)
            for stage, limit in self.STAGE_CONCURRENCY.items()
        }
        
        # Processing times for monitoring
        self._processing_times: deque = deque(maxlen=1000)
    
    async def start(self, num_workers: int = 5):
        """Start the pipeline workers."""
        if self._running:
            return
        
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(i))
            for i in range(num_workers)
        ]
        logger.info(f"Pipeline started with {num_workers} workers")
    
    async def stop(self):
        """Stop the pipeline gracefully."""
        self._running = False
        
        # Wait for workers to finish current tasks
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        
        self._workers = []
        logger.info("Pipeline stopped")
    
    async def submit(self, task: PipelineTask) -> bool:
        """
        Submit a task to the pipeline.
        
        Returns False if rejected due to backpressure.
        """
        if not self._backpressure.should_accept:
            self._stats.backpressure_events += 1
            return False
        
        self._task_queue.put(task)
        self._stats.tasks_queued += 1
        self._backpressure.update_depth(self._task_queue.size())
        
        return True
    
    async def submit_batch(
        self,
        papers: List[Dict[str, Any]],
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> int:
        """
        Submit a batch of papers for processing.
        
        Returns number of tasks accepted.
        """
        accepted = 0
        for paper in papers:
            task = PipelineTask(
                paper_id=paper.get("id", ""),
                arxiv_id=paper.get("arxiv_id", ""),
                priority=priority,
                stage=PipelineStage.FETCH,
                data=paper,
            )
            if await self.submit(task):
                accepted += 1
        
        return accepted
    
    async def _worker(self, worker_id: int):
        """Worker coroutine that processes tasks."""
        logger.debug(f"Worker {worker_id} started")
        
        while self._running:
            task = self._task_queue.get()
            
            if task is None:
                await asyncio.sleep(0.1)
                continue
            
            self._stats.tasks_processing += 1
            start_time = time.time()
            
            try:
                await self._process_task(task)
                self._stats.tasks_completed += 1
            except Exception as e:
                logger.error(f"Worker {worker_id} task failed: {e}")
                await self._handle_task_failure(task, str(e))
            finally:
                self._stats.tasks_processing -= 1
                processing_time = (time.time() - start_time) * 1000
                self._processing_times.append(processing_time)
                self._update_avg_processing_time()
                self._backpressure.update_depth(self._task_queue.size())
        
        logger.debug(f"Worker {worker_id} stopped")
    
    async def _process_task(self, task: PipelineTask):
        """Process a single task through its current stage."""
        stage = task.stage
        semaphore = self._stage_semaphores[stage]
        
        async with semaphore:
            if stage == PipelineStage.FETCH:
                await self._stage_fetch(task)
            elif stage == PipelineStage.ENRICH:
                await self._stage_enrich(task)
            elif stage == PipelineStage.SUMMARIZE:
                await self._stage_summarize(task)
            elif stage == PipelineStage.INDEX:
                await self._stage_index(task)
            elif stage == PipelineStage.RANK:
                await self._stage_rank(task)
    
    async def _stage_fetch(self, task: PipelineTask):
        """Stage 1: Fetch paper data from arXiv."""
        logger.debug(f"Fetching {task.arxiv_id}")
        
        # Paper data should already be in task.data from submit
        # Move to next stage
        task.stage = PipelineStage.ENRICH
        self._task_queue.put(task)
    
    async def _stage_enrich(self, task: PipelineTask):
        """Stage 2: Enrich with citations and implementations."""
        logger.debug(f"Enriching {task.arxiv_id}")
        
        # Get rate limiter for Semantic Scholar
        limiter = rate_limiter.get_limiter("semantic_scholar")
        
        if await limiter.acquire(RequestPriority.NORMAL):
            # Would call semantic_scholar_service here
            limiter.record_success()
        
        # Only high-priority papers get summaries
        if task.priority in (TaskPriority.CRITICAL, TaskPriority.HIGH):
            task.stage = PipelineStage.SUMMARIZE
        else:
            task.stage = PipelineStage.INDEX
        
        self._task_queue.put(task)
    
    async def _stage_summarize(self, task: PipelineTask):
        """Stage 3: Generate LLM summary (expensive, limited)."""
        logger.debug(f"Summarizing {task.arxiv_id}")
        
        # LLM summary generation would happen here
        # Using semaphore limits concurrent LLM calls
        
        task.stage = PipelineStage.INDEX
        self._task_queue.put(task)
    
    async def _stage_index(self, task: PipelineTask):
        """Stage 4: Index for search."""
        logger.debug(f"Indexing {task.arxiv_id}")
        
        # Would generate embeddings and update search index here
        
        task.stage = PipelineStage.RANK
        self._task_queue.put(task)
    
    async def _stage_rank(self, task: PipelineTask):
        """Stage 5: Calculate ranking score."""
        logger.debug(f"Ranking {task.arxiv_id}")
        
        # Final stage - update database with ranking score
        # This is the end of the pipeline for this task
    
    async def _handle_task_failure(self, task: PipelineTask, error: str):
        """Handle a failed task with retry logic."""
        task.attempts += 1
        task.last_error = error
        
        if task.attempts < task.max_attempts:
            # Exponential backoff
            delay = 2 ** task.attempts
            logger.warning(
                f"Task {task.arxiv_id} failed (attempt {task.attempts}), "
                f"retrying in {delay}s"
            )
            await asyncio.sleep(delay)
            self._task_queue.put(task)
        else:
            logger.error(
                f"Task {task.arxiv_id} failed after {task.max_attempts} attempts: {error}"
            )
            self._stats.tasks_failed += 1
    
    def _update_avg_processing_time(self):
        """Update average processing time statistic."""
        if self._processing_times:
            self._stats.avg_processing_time_ms = sum(self._processing_times) / len(self._processing_times)
    
    def get_stats(self) -> PipelineStats:
        """Get current pipeline statistics."""
        return self._stats
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get detailed queue status."""
        return {
            "total_queued": self._task_queue.size(),
            "by_priority": {
                p.name: count
                for p, count in self._task_queue.size_by_priority().items()
            },
            "backpressure_active": not self._backpressure.should_accept,
            "utilization": self._backpressure.utilization,
        }


async def process_paper_batch(
    papers: List[Dict[str, Any]],
    priority: TaskPriority = TaskPriority.NORMAL,
) -> PipelineStats:
    """
    Convenience function to process a batch of papers.
    
    Creates a pipeline, processes papers, and returns stats.
    """
    pipeline = AsyncIngestionPipeline()
    await pipeline.start()
    
    try:
        accepted = await pipeline.submit_batch(papers, priority)
        logger.info(f"Submitted {accepted}/{len(papers)} papers to pipeline")
        
        # Wait for processing to complete
        while pipeline._task_queue.size() > 0 or pipeline._stats.tasks_processing > 0:
            await asyncio.sleep(0.5)
        
        return pipeline.get_stats()
    finally:
        await pipeline.stop()


# Singleton pipeline instance (created on demand)
_pipeline: Optional[AsyncIngestionPipeline] = None


def get_pipeline() -> AsyncIngestionPipeline:
    """Get or create the global pipeline instance."""
    global _pipeline
    if _pipeline is None:
        _pipeline = AsyncIngestionPipeline()
    return _pipeline
