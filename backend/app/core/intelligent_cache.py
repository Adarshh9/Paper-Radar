"""
Intelligent Cache with Dynamic TTL.
Smart caching strategy that adapts TTL based on data volatility and paper activity.
"""
import json
import hashlib
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Dict, Callable, TypeVar, Generic
from dataclasses import dataclass
from enum import Enum
from functools import wraps

from loguru import logger

from app.core.config import get_settings

settings = get_settings()

T = TypeVar('T')


class DataType(Enum):
    """Types of cached data with their base TTL."""
    PAPER_METADATA = "paper_metadata"
    CITATIONS = "citations"
    IMPLEMENTATIONS = "implementations"
    SOCIAL_SIGNALS = "social_signals"
    TRENDING_PAPERS = "trending_papers"
    SEARCH_RESULTS = "search_results"
    USER_RECOMMENDATIONS = "user_recommendations"
    FIELD_STATISTICS = "field_statistics"
    EMBEDDINGS = "embeddings"
    SUMMARIES = "summaries"
    VISUALIZATIONS = "visualizations"  # For 3D graph data


@dataclass
class CacheEntry:
    """A cache entry with metadata."""
    key: str
    value: Any
    data_type: str
    created_at: float
    expires_at: float
    hits: int = 0
    paper_velocity: Optional[int] = None  # For dynamic TTL calculation


class IntelligentCache:
    """
    Cache with TTL based on data volatility.
    
    Features:
    - Data-type specific base TTLs
    - Dynamic TTL adjustment based on paper activity
    - Automatic cache warming for popular items
    - LRU eviction for memory management
    - Cache statistics and monitoring
    """
    
    # Base TTL strategies in seconds
    TTL_STRATEGY = {
        DataType.PAPER_METADATA.value: 86400 * 7,    # 7 days (rarely changes)
        DataType.CITATIONS.value: 3600,               # 1 hour (changes often)
        DataType.IMPLEMENTATIONS.value: 3600 * 6,     # 6 hours (moderate)
        DataType.SOCIAL_SIGNALS.value: 900,           # 15 mins (very volatile)
        DataType.TRENDING_PAPERS.value: 600,          # 10 mins (real-time feel)
        DataType.SEARCH_RESULTS.value: 1800,          # 30 mins
        DataType.USER_RECOMMENDATIONS.value: 3600,    # 1 hour
        DataType.FIELD_STATISTICS.value: 21600,       # 6 hours
        DataType.EMBEDDINGS.value: 86400 * 30,        # 30 days (static)
        DataType.SUMMARIES.value: 86400 * 7,          # 7 days (regenerate weekly)
    }
    
    # Velocity thresholds for TTL adjustment
    HIGH_VELOCITY_THRESHOLD = 15  # citations/week
    STABLE_AGE_THRESHOLD = 180    # days
    
    def __init__(self, cache_dir: Optional[Path] = None, max_memory_items: int = 10000):
        self.cache_dir = cache_dir or (settings.data_directory / "cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_memory_items = max_memory_items
        
        # In-memory LRU cache for hot items
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._access_order: list = []
        
        # Statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "memory_hits": 0,
            "disk_hits": 0,
            "evictions": 0,
        }
    
    def get_ttl(
        self,
        data_type: str,
        paper_velocity: Optional[int] = None,
        paper_age_days: Optional[int] = None,
    ) -> int:
        """
        Calculate dynamic TTL based on data type and paper activity.
        
        Args:
            data_type: Type of data being cached
            paper_velocity: Citation velocity (citations per week)
            paper_age_days: Days since paper was published
        
        Returns:
            TTL in seconds
        """
        base_ttl = self.TTL_STRATEGY.get(data_type, 3600)
        
        # No adjustment without paper info
        if paper_velocity is None and paper_age_days is None:
            return base_ttl
        
        # Reduce TTL for trending papers (need fresher data)
        if paper_velocity is not None and paper_velocity > self.HIGH_VELOCITY_THRESHOLD:
            return base_ttl // 2
        
        # Increase TTL for old, stable papers (data changes slowly)
        if paper_age_days is not None and paper_age_days > self.STABLE_AGE_THRESHOLD:
            return base_ttl * 2
        
        return base_ttl
    
    def _get_cache_path(self, key: str) -> Path:
        """Get file path for a cache key."""
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.json"
    
    def _evict_if_needed(self):
        """Evict oldest entries if memory cache is full."""
        while len(self._memory_cache) >= self.max_memory_items:
            if self._access_order:
                oldest_key = self._access_order.pop(0)
                if oldest_key in self._memory_cache:
                    del self._memory_cache[oldest_key]
                    self._stats["evictions"] += 1
    
    def _update_access_order(self, key: str):
        """Update LRU access order."""
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
    
    def get(
        self,
        key: str,
        data_type: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Get value from cache.
        
        Checks memory cache first, then disk cache.
        """
        # Check memory cache first
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            
            # Check expiration
            if entry.expires_at < time.time():
                del self._memory_cache[key]
                self._stats["misses"] += 1
                return None
            
            entry.hits += 1
            self._update_access_order(key)
            self._stats["hits"] += 1
            self._stats["memory_hits"] += 1
            return entry.value
        
        # Check disk cache
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            self._stats["misses"] += 1
            return None
        
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Check if expired
            if data.get("expires_at") and data["expires_at"] < time.time():
                cache_path.unlink(missing_ok=True)
                self._stats["misses"] += 1
                return None
            
            # Promote to memory cache
            self._evict_if_needed()
            entry = CacheEntry(
                key=key,
                value=data.get("value"),
                data_type=data.get("data_type", "unknown"),
                created_at=data.get("created_at", time.time()),
                expires_at=data.get("expires_at", time.time() + 3600),
                hits=data.get("hits", 0) + 1,
                paper_velocity=data.get("paper_velocity"),
            )
            self._memory_cache[key] = entry
            self._update_access_order(key)
            
            self._stats["hits"] += 1
            self._stats["disk_hits"] += 1
            return entry.value
            
        except (json.JSONDecodeError, IOError):
            self._stats["misses"] += 1
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        data_type: str = "unknown",
        ttl_seconds: Optional[int] = None,
        paper_velocity: Optional[int] = None,
        paper_age_days: Optional[int] = None,
    ) -> bool:
        """
        Set value in cache with intelligent TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            data_type: Type of data (for TTL calculation)
            ttl_seconds: Override TTL (optional)
            paper_velocity: Citation velocity for dynamic TTL
            paper_age_days: Paper age for dynamic TTL
        """
        # Calculate TTL if not provided
        if ttl_seconds is None:
            ttl_seconds = self.get_ttl(data_type, paper_velocity, paper_age_days)
        
        now = time.time()
        expires_at = now + ttl_seconds
        
        # Store in memory cache
        self._evict_if_needed()
        entry = CacheEntry(
            key=key,
            value=value,
            data_type=data_type,
            created_at=now,
            expires_at=expires_at,
            paper_velocity=paper_velocity,
        )
        self._memory_cache[key] = entry
        self._update_access_order(key)
        
        # Persist to disk
        cache_path = self._get_cache_path(key)
        
        try:
            data = {
                "key": key,
                "value": value,
                "data_type": data_type,
                "created_at": now,
                "expires_at": expires_at,
                "paper_velocity": paper_velocity,
            }
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return True
        except (IOError, TypeError) as e:
            logger.warning(f"Failed to persist cache entry: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        deleted = False
        
        if key in self._memory_cache:
            del self._memory_cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            deleted = True
        
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            cache_path.unlink()
            deleted = True
        
        return deleted
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all cache entries matching a pattern."""
        count = 0
        
        # Memory cache
        keys_to_delete = [k for k in self._memory_cache if pattern in k]
        for key in keys_to_delete:
            del self._memory_cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            count += 1
        
        # Disk cache (slower, but complete)
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if pattern in data.get("key", ""):
                    cache_file.unlink()
                    count += 1
            except (json.JSONDecodeError, IOError):
                continue
        
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        hit_rate = (
            self._stats["hits"] / (self._stats["hits"] + self._stats["misses"])
            if (self._stats["hits"] + self._stats["misses"]) > 0
            else 0
        )
        
        return {
            **self._stats,
            "hit_rate": round(hit_rate, 4),
            "memory_items": len(self._memory_cache),
            "disk_items": len(list(self.cache_dir.glob("*.json"))),
        }
    
    def clear_expired(self) -> int:
        """Clear all expired cache entries."""
        deleted = 0
        now = time.time()
        
        # Memory cache
        expired_keys = [
            k for k, v in self._memory_cache.items()
            if v.expires_at < now
        ]
        for key in expired_keys:
            del self._memory_cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            deleted += 1
        
        # Disk cache
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("expires_at", 0) < now:
                    cache_file.unlink()
                    deleted += 1
            except (json.JSONDecodeError, IOError):
                cache_file.unlink(missing_ok=True)
                deleted += 1
        
        return deleted
    
    def warm_cache(self, keys_with_loaders: Dict[str, Callable]) -> int:
        """
        Pre-warm cache with commonly accessed items.
        
        Args:
            keys_with_loaders: Dict mapping cache keys to loader functions
        
        Returns:
            Number of items warmed
        """
        warmed = 0
        for key, loader in keys_with_loaders.items():
            if self.get(key) is None:
                try:
                    value = loader()
                    if value is not None:
                        self.set(key, value)
                        warmed += 1
                except Exception as e:
                    logger.warning(f"Cache warming failed for {key}: {e}")
        
        return warmed


def cached(
    data_type: str,
    key_builder: Optional[Callable[..., str]] = None,
    ttl_seconds: Optional[int] = None,
):
    """
    Decorator for caching function results.
    
    Usage:
        @cached(data_type=DataType.CITATIONS.value)
        async def get_citations(paper_id: str):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default key from function name and args
                arg_str = "_".join(str(a) for a in args)
                kwarg_str = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = f"{func.__name__}:{arg_str}:{kwarg_str}"
            
            # Check cache
            cached_value = intelligent_cache.get(cache_key, data_type)
            if cached_value is not None:
                return cached_value
            
            # Call function
            result = await func(*args, **kwargs)
            
            # Cache result
            if result is not None:
                intelligent_cache.set(
                    cache_key,
                    result,
                    data_type=data_type,
                    ttl_seconds=ttl_seconds,
                )
            
            return result
        
        return wrapper
    return decorator


# Singleton intelligent cache instance
intelligent_cache = IntelligentCache()


# Also update the simple cache interface for backward compatibility
class SimpleCacheInterface:
    """
    Simple cache interface wrapping IntelligentCache.
    Maintains backward compatibility with existing code.
    """
    
    def __init__(self, intelligent_cache: IntelligentCache):
        self._cache = intelligent_cache
    
    def get(self, key: str) -> Optional[Any]:
        return self._cache.get(key)
    
    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        return self._cache.set(key, value, ttl_seconds=ttl_seconds)
    
    def delete(self, key: str) -> bool:
        return self._cache.delete(key)
    
    def increment(self, key: str, ttl_seconds: int = 60) -> int:
        """Increment counter (for rate limiting)."""
        current = self.get(key)
        if current is None:
            current = 0
        new_value = int(current) + 1
        self.set(key, new_value, ttl_seconds)
        return new_value
    
    def get_counter(self, key: str) -> int:
        """Get current counter value."""
        value = self.get(key)
        return int(value) if value else 0


# Export compatible interface
smart_cache = SimpleCacheInterface(intelligent_cache)
