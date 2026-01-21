# python_service/cache_manager.py
import asyncio
import hashlib
import json
from datetime import datetime
from datetime import timedelta
from functools import wraps
from typing import Any
from typing import Callable
from typing import Optional

import structlog

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

log = structlog.get_logger(__name__)


class CacheManager:
    def __init__(self):
        self.redis_client = None
        self.memory_cache = {}
        self.is_configured = False
        log.info("CacheManager initialized (not connected).")

    async def connect(self, redis_url: str):
        if self.is_configured or not REDIS_AVAILABLE or not redis_url:
            return

        try:
            log.info("Attempting to connect to Redis...", url=redis_url)
            # Use the async version of the client
            self.redis_client = redis.asyncio.from_url(redis_url, decode_responses=True)
            await self.redis_client.ping()  # Verify connection asynchronously
            self.is_configured = True
            log.info("Redis cache connected successfully.")
        except (redis.exceptions.ConnectionError, asyncio.TimeoutError) as e:
            log.warning(
                "Failed to connect to Redis. Falling back to in-memory cache.",
                error=str(e),
            )
            self.redis_client = None
            self.is_configured = False

    async def disconnect(self):
        if self.redis_client:
            await self.redis_client.close()
            log.info("Redis connection closed.")

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()

    async def get(self, key: str) -> Any | None:
        if self.redis_client:
            try:
                value = await self.redis_client.get(key)
                return json.loads(value) if value else None
            except redis.exceptions.RedisError as e:
                log.warning("Redis GET failed, falling back to memory cache.", error=e)

        entry = self.memory_cache.get(key)
        if entry and entry.get("expires_at", datetime.min) > datetime.now():
            return entry.get("value")
        return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 300):
        try:
            serialized = json.dumps(value, default=str)
        except (TypeError, ValueError) as e:
            log.error("Failed to serialize value for caching.", value=value, error=str(e))
            return

        if self.redis_client:
            try:
                await self.redis_client.setex(key, ttl_seconds, serialized)
                return
            except redis.exceptions.RedisError as e:
                log.warning("Redis SET failed, falling back to memory cache.", error=e)

        self.memory_cache[key] = {
            "value": value,
            "expires_at": datetime.now() + timedelta(seconds=ttl_seconds),
        }


# --- Singleton Instance & Decorator ---
cache_manager = CacheManager()


def cache_async_result(ttl_seconds: int = 300, key_prefix: str = "cache"):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            instance_args = args[1:] if args and hasattr(args[0], func.__name__) else args
            cache_key = cache_manager._generate_key(f"{key_prefix}:{func.__name__}", *instance_args, **kwargs)

            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                log.debug("Cache hit", function=func.__name__)
                return cached_result

            log.debug("Cache miss", function=func.__name__)
            result = await func(*args, **kwargs)

            try:
                await cache_manager.set(cache_key, result, ttl_seconds)
            except Exception as e:
                log.error("Failed to store result in cache.", error=str(e), key=cache_key)

            return result

        return wrapper

    return decorator


class StaleDataCache:
    """In-memory cache for storing the last known good data for a given date."""

    def __init__(self, max_age_hours: int = 24):
        self._cache: dict[str, dict] = {}
        self.max_age = timedelta(hours=max_age_hours)
        self.logger = structlog.get_logger(cache_type="StaleDataCache")

    async def get(self, date_key: str) -> Optional[dict]:
        """
        Retrieves stale data if it exists and is within the max_age.
        Returns a dictionary with the data and its age, or None.
        """
        entry = self._cache.get(date_key)
        if not entry:
            self.logger.debug("Cache miss", key=date_key)
            return None

        now = datetime.utcnow()
        timestamp = entry["timestamp"]
        age = now - timestamp

        if age > self.max_age:
            self.logger.warning("Cache entry expired", key=date_key, age_hours=age.total_seconds() / 3600)
            del self._cache[date_key]
            return None

        age_hours = age.total_seconds() / 3600
        self.logger.info("Cache hit", key=date_key, age_hours=round(age_hours, 2))
        return {"data": entry["data"], "age_hours": age_hours}

    async def set(self, date_key: str, data: Any):
        """
        Stores the latest successful data fetch for a given date.
        """
        self.logger.info("Updating stale cache", key=date_key)
        self._cache[date_key] = {
            "timestamp": datetime.utcnow(),
            "data": data,
        }
