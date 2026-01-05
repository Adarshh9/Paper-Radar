"""
Redis cache connection and utilities.
"""
import json
from typing import Any, Optional

import redis

from app.core.config import get_settings

settings = get_settings()

# Create Redis client
redis_client = redis.from_url(
    settings.redis_url,
    decode_responses=True,
)


class CacheManager:
    """Redis cache manager for application caching."""
    
    def __init__(self, client: redis.Redis = redis_client):
        self.client = client
    
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


# Singleton cache manager
cache = CacheManager()
