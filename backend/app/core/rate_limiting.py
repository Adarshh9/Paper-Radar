"""
Advanced Rate Limiting with Exponential Backoff.
Provides per-endpoint rate limiting, adaptive backoff, and request prioritization.
"""
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps

from loguru import logger


class RequestPriority(Enum):
    """Request priority levels for queue management."""
    CRITICAL = 1    # User-facing requests
    HIGH = 2        # Important updates (trending papers)
    NORMAL = 3      # Routine updates
    LOW = 4         # Background tasks


@dataclass
class RateLimitConfig:
    """Configuration for a rate limiter."""
    requests_per_window: int
    window_seconds: int
    max_retries: int = 3
    base_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 300.0
    jitter: bool = True


@dataclass
class RateLimitState:
    """Current state of a rate limiter."""
    requests_this_window: int = 0
    window_start: datetime = field(default_factory=datetime.now)
    consecutive_failures: int = 0
    last_failure_time: Optional[datetime] = None
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[datetime] = None


class ExponentialBackoff:
    """
    Exponential backoff calculator with jitter.
    
    Implements the "full jitter" algorithm for optimal backoff behavior.
    """
    
    def __init__(
        self,
        base_seconds: float = 1.0,
        max_seconds: float = 300.0,
        jitter: bool = True,
    ):
        self.base = base_seconds
        self.max = max_seconds
        self.jitter = jitter
    
    def calculate(self, attempt: int) -> float:
        """
        Calculate backoff time for given attempt number.
        
        Uses exponential backoff with optional jitter.
        """
        # Exponential: base * 2^attempt
        exp_backoff = self.base * (2 ** attempt)
        
        # Cap at maximum
        capped = min(exp_backoff, self.max)
        
        if self.jitter:
            # Full jitter: random between 0 and capped
            import random
            return random.uniform(0, capped)
        
        return capped
    
    def calculate_from_failures(self, consecutive_failures: int) -> float:
        """Calculate backoff based on consecutive failure count."""
        return self.calculate(consecutive_failures)


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that responds to API feedback.
    
    Features:
    - Per-endpoint rate limiting
    - Reads X-RateLimit-Remaining headers
    - Exponential backoff on failures
    - Request prioritization
    - Automatic recovery
    """
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.state = RateLimitState()
        self.backoff = ExponentialBackoff(
            base_seconds=config.base_backoff_seconds,
            max_seconds=config.max_backoff_seconds,
            jitter=config.jitter,
        )
        self._lock = asyncio.Lock()
    
    async def acquire(self, priority: RequestPriority = RequestPriority.NORMAL) -> bool:
        """
        Acquire permission to make a request.
        
        Returns True if request can proceed, False if should be dropped.
        """
        async with self._lock:
            now = datetime.now()
            
            # Check if in backoff period
            if self.state.last_failure_time and self.state.consecutive_failures > 0:
                backoff_time = self.backoff.calculate_from_failures(
                    self.state.consecutive_failures
                )
                backoff_until = self.state.last_failure_time + timedelta(seconds=backoff_time)
                
                if now < backoff_until:
                    # Still in backoff - only allow critical requests
                    if priority != RequestPriority.CRITICAL:
                        wait_remaining = (backoff_until - now).total_seconds()
                        logger.debug(
                            f"Rate limiter in backoff, {wait_remaining:.1f}s remaining",
                            priority=priority.name,
                        )
                        return False
            
            # Reset window if needed
            window_elapsed = (now - self.state.window_start).total_seconds()
            if window_elapsed >= self.config.window_seconds:
                self.state.requests_this_window = 0
                self.state.window_start = now
            
            # Check API-reported rate limit
            if self.state.rate_limit_remaining is not None:
                if self.state.rate_limit_remaining <= 0:
                    if self.state.rate_limit_reset and now < self.state.rate_limit_reset:
                        wait_time = (self.state.rate_limit_reset - now).total_seconds()
                        logger.info(f"API rate limit exhausted, reset in {wait_time:.1f}s")
                        
                        # Wait for reset (only for high priority)
                        if priority in (RequestPriority.CRITICAL, RequestPriority.HIGH):
                            await asyncio.sleep(min(wait_time, 60))
                        else:
                            return False
            
            # Check local rate limit
            if self.state.requests_this_window >= self.config.requests_per_window:
                wait_time = self.config.window_seconds - window_elapsed
                
                if wait_time > 0:
                    if priority == RequestPriority.CRITICAL:
                        logger.info(f"Critical request waiting {wait_time:.1f}s for rate limit")
                        await asyncio.sleep(wait_time)
                        self.state.requests_this_window = 0
                        self.state.window_start = datetime.now()
                    else:
                        logger.debug(f"Rate limit reached, {wait_time:.1f}s until reset")
                        return False
            
            self.state.requests_this_window += 1
            return True
    
    def record_success(self):
        """Record a successful request."""
        self.state.consecutive_failures = 0
        self.state.last_failure_time = None
    
    def record_failure(self, is_rate_limit: bool = False):
        """Record a failed request."""
        self.state.consecutive_failures += 1
        self.state.last_failure_time = datetime.now()
        
        if is_rate_limit:
            logger.warning(
                f"Rate limit failure #{self.state.consecutive_failures}",
                backoff=self.backoff.calculate_from_failures(self.state.consecutive_failures),
            )
    
    def update_from_headers(self, headers: Dict[str, str]):
        """Update rate limit state from API response headers."""
        remaining = headers.get("X-RateLimit-Remaining") or headers.get("x-ratelimit-remaining")
        reset = headers.get("X-RateLimit-Reset") or headers.get("x-ratelimit-reset")
        
        if remaining is not None:
            try:
                self.state.rate_limit_remaining = int(remaining)
            except ValueError:
                pass
        
        if reset is not None:
            try:
                # Reset time can be Unix timestamp or seconds until reset
                reset_int = int(reset)
                if reset_int > 1e9:  # Unix timestamp
                    self.state.rate_limit_reset = datetime.fromtimestamp(reset_int)
                else:  # Seconds until reset
                    self.state.rate_limit_reset = datetime.now() + timedelta(seconds=reset_int)
            except ValueError:
                pass
    
    async def wait_and_retry(self, attempt: int) -> bool:
        """
        Wait with exponential backoff and return whether to retry.
        
        Returns False if max retries exceeded.
        """
        if attempt >= self.config.max_retries:
            return False
        
        backoff_time = self.backoff.calculate(attempt)
        logger.info(f"Backing off for {backoff_time:.1f}s (attempt {attempt + 1})")
        await asyncio.sleep(backoff_time)
        return True


class MultiEndpointRateLimiter:
    """
    Rate limiter manager for multiple API endpoints.
    
    Each endpoint can have its own rate limit configuration.
    """
    
    # Default configurations for common APIs
    DEFAULT_CONFIGS = {
        "semantic_scholar": RateLimitConfig(
            requests_per_window=100,
            window_seconds=300,  # 5 minutes
            max_retries=3,
            base_backoff_seconds=60,
        ),
        "semantic_scholar_partner": RateLimitConfig(
            requests_per_window=1000,
            window_seconds=300,
            max_retries=3,
            base_backoff_seconds=30,
        ),
        "github": RateLimitConfig(
            requests_per_window=5000,
            window_seconds=3600,  # 1 hour
            max_retries=2,
            base_backoff_seconds=30,
        ),
        "github_unauthenticated": RateLimitConfig(
            requests_per_window=60,
            window_seconds=3600,
            max_retries=2,
            base_backoff_seconds=60,
        ),
        "arxiv": RateLimitConfig(
            requests_per_window=120,
            window_seconds=60,  # 1 minute
            max_retries=3,
            base_backoff_seconds=5,
        ),
        "groq": RateLimitConfig(
            requests_per_window=30,
            window_seconds=60,
            max_retries=2,
            base_backoff_seconds=30,
            max_backoff_seconds=120,
        ),
        "huggingface": RateLimitConfig(
            requests_per_window=100,
            window_seconds=60,
            max_retries=2,
            base_backoff_seconds=10,
        ),
    }
    
    def __init__(self):
        self._limiters: Dict[str, AdaptiveRateLimiter] = {}
    
    def get_limiter(self, endpoint: str) -> AdaptiveRateLimiter:
        """Get or create a rate limiter for an endpoint."""
        if endpoint not in self._limiters:
            config = self.DEFAULT_CONFIGS.get(
                endpoint,
                RateLimitConfig(
                    requests_per_window=60,
                    window_seconds=60,
                    max_retries=3,
                )
            )
            self._limiters[endpoint] = AdaptiveRateLimiter(config)
        
        return self._limiters[endpoint]
    
    def register_endpoint(self, endpoint: str, config: RateLimitConfig):
        """Register a custom endpoint configuration."""
        self._limiters[endpoint] = AdaptiveRateLimiter(config)


# Global rate limiter instance
rate_limiter = MultiEndpointRateLimiter()


def with_rate_limit(
    endpoint: str,
    priority: RequestPriority = RequestPriority.NORMAL,
):
    """
    Decorator for applying rate limiting to async functions.
    
    Usage:
        @with_rate_limit("semantic_scholar")
        async def fetch_paper(arxiv_id: str):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            limiter = rate_limiter.get_limiter(endpoint)
            
            for attempt in range(limiter.config.max_retries + 1):
                if not await limiter.acquire(priority):
                    if attempt < limiter.config.max_retries:
                        await limiter.wait_and_retry(attempt)
                        continue
                    raise RateLimitExceeded(f"Rate limit exceeded for {endpoint}")
                
                try:
                    result = await func(*args, **kwargs)
                    limiter.record_success()
                    return result
                except RateLimitError as e:
                    limiter.record_failure(is_rate_limit=True)
                    if not await limiter.wait_and_retry(attempt):
                        raise
                except Exception as e:
                    limiter.record_failure(is_rate_limit=False)
                    raise
            
            raise RateLimitExceeded(f"Max retries exceeded for {endpoint}")
        
        return wrapper
    return decorator


class RateLimitError(Exception):
    """Raised when an API returns a rate limit error."""
    pass


class RateLimitExceeded(Exception):
    """Raised when local rate limit is exceeded."""
    pass


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = 3,
        retry_on: tuple = (RateLimitError, ConnectionError, TimeoutError),
        backoff: Optional[ExponentialBackoff] = None,
    ):
        self.max_retries = max_retries
        self.retry_on = retry_on
        self.backoff = backoff or ExponentialBackoff()


async def with_retry(
    func: Callable,
    config: RetryConfig,
    *args,
    **kwargs,
) -> Any:
    """
    Execute a function with retry logic and exponential backoff.
    
    Args:
        func: Async function to execute
        config: Retry configuration
        *args, **kwargs: Arguments to pass to the function
    
    Returns:
        Result of the function
    
    Raises:
        The last exception if all retries fail
    """
    last_exception = None
    
    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except config.retry_on as e:
            last_exception = e
            
            if attempt < config.max_retries:
                backoff_time = config.backoff.calculate(attempt)
                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {backoff_time:.1f}s"
                )
                await asyncio.sleep(backoff_time)
            else:
                logger.error(f"All {config.max_retries + 1} attempts failed: {e}")
    
    raise last_exception
