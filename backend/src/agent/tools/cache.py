"""Redis-backed caching utility for external API calls.

Provides a simple key-value cache with TTL using the app's existing
Redis connection. Keys are built from function name + args to ensure
uniqueness. Cached results are JSON-serialized.
"""

import json
import hashlib
from typing import Optional
from src.database import get_redis_client

# Default cache TTLs (in seconds)
FLIGHT_CACHE_TTL = 900     # 15 minutes — prices change frequently
HOTEL_CACHE_TTL = 1800     # 30 minutes — availability changes less often


def _build_cache_key(prefix: str, **kwargs) -> str:
    """Build a deterministic cache key from prefix + sorted kwargs."""
    # Sort kwargs for consistency, exclude None values
    filtered = {k: v for k, v in sorted(kwargs.items()) if v is not None}
    raw = json.dumps(filtered, sort_keys=True, default=str)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"cache:{prefix}:{key_hash}"


def get_cached(prefix: str, **kwargs) -> Optional[dict]:
    """
    Get a cached result. Returns None on miss or if Redis is unavailable.
    
    This is a SYNC function because the tool functions that call it
    (search_flights, search_hotels) are sync.
    """
    try:
        redis = get_redis_client()
        if not redis:
            return None
        
        key = _build_cache_key(prefix, **kwargs)
        
        # Use the sync Redis interface via asyncio
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context — can't block, skip cache
            return None
        except RuntimeError:
            pass
        
        # No running loop — safe to create one
        result = asyncio.run(_async_get(redis, key))
        return result
    except Exception:
        return None


def set_cached(prefix: str, data: dict, ttl: int, **kwargs) -> None:
    """
    Set a cache entry with TTL. Fails silently if Redis is unavailable.
    """
    try:
        redis = get_redis_client()
        if not redis:
            return
        
        key = _build_cache_key(prefix, **kwargs)
        
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # In async context — schedule as task
            loop.create_task(_async_set(redis, key, data, ttl))
            return
        except RuntimeError:
            pass
        
        asyncio.run(_async_set(redis, key, data, ttl))
    except Exception:
        pass


async def _async_get(redis, key: str) -> Optional[dict]:
    """Async Redis GET + JSON decode."""
    raw = await redis.get(key)
    if raw:
        return json.loads(raw)
    return None


async def _async_set(redis, key: str, data: dict, ttl: int) -> None:
    """Async Redis SET with TTL."""
    await redis.set(key, json.dumps(data, default=str), ex=ttl)


# ── Async-native functions (for use in async contexts) ──

async def aget_cached(prefix: str, **kwargs) -> Optional[dict]:
    """Async version of get_cached."""
    try:
        redis = get_redis_client()
        if not redis:
            return None
        key = _build_cache_key(prefix, **kwargs)
        return await _async_get(redis, key)
    except Exception:
        return None


async def aset_cached(prefix: str, data: dict, ttl: int, **kwargs) -> None:
    """Async version of set_cached."""
    try:
        redis = get_redis_client()
        if not redis:
            return
        key = _build_cache_key(prefix, **kwargs)
        await _async_set(redis, key, data, ttl)
    except Exception:
        pass
