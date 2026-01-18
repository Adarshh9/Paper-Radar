"""
Cache connection and utilities.
Supports Redis (production) and file-based caching (local development).
"""
import json
import hashlib
import time
from pathlib import Path
from typing import Any, Optional

from app.core.config import get_settings

settings = get_settings()


class FileCacheManager:
    """File-based cache manager for local development (no Redis required)."""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or (settings.data_directory / "cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, key: str) -> Path:
        """Get file path for a cache key."""
        # Use hash to avoid filesystem issues with special characters
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.json"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Check if expired
            if data.get("expires_at") and data["expires_at"] < time.time():
                cache_path.unlink(missing_ok=True)
                return None
            
            return data.get("value")
        except (json.JSONDecodeError, IOError):
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = 3600,
    ) -> bool:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl_seconds: Time to live in seconds (default 1 hour)
        """
        cache_path = self._get_cache_path(key)
        
        try:
            data = {
                "key": key,
                "value": value,
                "expires_at": time.time() + ttl_seconds,
                "created_at": time.time(),
            }
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return True
        except (IOError, TypeError):
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            cache_path.unlink()
            return True
        return False
    
    def increment(self, key: str, ttl_seconds: int = 60) -> int:
        """
        Increment counter (for rate limiting).
        Creates key with TTL if doesn't exist.
        """
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
    
    def clear_expired(self) -> int:
        """Clear all expired cache entries. Returns count of deleted entries."""
        deleted = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("expires_at") and data["expires_at"] < time.time():
                    cache_file.unlink()
                    deleted += 1
            except (json.JSONDecodeError, IOError):
                cache_file.unlink(missing_ok=True)
                deleted += 1
        return deleted


class RedisCacheManager:
    """Redis cache manager for production."""
    
    def __init__(self):
        import redis
        self.client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        value = self.client.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = 3600,
    ) -> bool:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl_seconds: Time to live in seconds (default 1 hour)
        """
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        return self.client.setex(key, ttl_seconds, value)
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        return self.client.delete(key) > 0
    
    def increment(self, key: str, ttl_seconds: int = 60) -> int:
        """
        Increment counter (for rate limiting).
        Creates key with TTL if doesn't exist.
        """
        pipe = self.client.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl_seconds)
        results = pipe.execute()
        return results[0]
    
    def get_counter(self, key: str) -> int:
        """Get current counter value."""
        value = self.client.get(key)
        return int(value) if value else 0


def get_cache_manager():
    """Get the appropriate cache manager based on settings."""
    if settings.use_local_storage:
        return FileCacheManager()
    return RedisCacheManager()


# Singleton cache manager
cache = get_cache_manager()
