# python_service/cache_manager.py
import hashlib
import json
import os
from datetime import datetime
from datetime import timedelta
from functools import wraps
from typing import Any
from typing import Callable

import structlog

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

log = structlog.get_logger(__name__)


class CacheManager:
    def __init__(self, redis_url: str = None):
        self.redis_client = None
        self.memory_cache = {}
        self.is_configured = False
        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()  # Verify connection
                self.is_configured = True
                log.info("Redis cache connected successfully.")
            except redis.exceptions.ConnectionError as e:
                log.warning(f"Failed to connect to Redis: {e}. Falling back to in-memory cache.")
                self.redis_client = None  # Ensure client is None on failure

        if not self.is_configured:
            log.info("CacheManager initialized with in-memory cache.")

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, key: str) -> Any | None:
        if self.redis_client:
            try:
                value = self.redis_client.get(key)
                return json.loads(value) if value else None
            except redis.exceptions.RedisError as e:
                log.warning(f"Redis GET failed, falling back to memory cache: {e}")

        entry = self.memory_cache.get(key)
        if entry and entry.get("expires_at", datetime.min) > datetime.now():
            return entry.get("value")
        return None

    def set(self, key: str, value: Any, ttl_seconds: int = 300):
        try:
            serialized = json.dumps(value, default=str)
        except (TypeError, ValueError) as e:
            log.error("Failed to serialize value for caching.", value=value, error=str(e))
            return

        if self.redis_client:
            try:
                self.redis_client.setex(key, ttl_seconds, serialized)
                return
            except redis.exceptions.RedisError as e:
                log.warning(f"Redis SET failed, falling back to memory cache: {e}")

        self.memory_cache[key] = {
            "value": value,
            "expires_at": datetime.now() + timedelta(seconds=ttl_seconds),
        }


# --- Singleton Instance & Decorator ---
cache_manager = CacheManager(redis_url=os.getenv("REDIS_URL"))


def cache_async_result(ttl_seconds: int = 300, key_prefix: str = "cache"):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            instance_args = args[1:] if args and hasattr(args[0], func.__name__) else args
            cache_key = cache_manager._generate_key(f"{key_prefix}:{func.__name__}", *instance_args, **kwargs)

            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                log.debug("Cache hit", function=func.__name__)
                return cached_result

            log.debug("Cache miss", function=func.__name__)
            result = await func(*args, **kwargs)

            try:
                cache_manager.set(cache_key, result, ttl_seconds)
            except Exception as e:
                log.error("Failed to store result in cache.", error=str(e), key=cache_key)

            return result

        return wrapper

    return decorator
