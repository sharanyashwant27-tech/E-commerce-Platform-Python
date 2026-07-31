"""Redis caching with graceful fallback when Redis is unavailable."""

import json
import logging
from typing import Any, Optional

from config.settings import settings

logger = logging.getLogger(__name__)
_client = None
_unavailable = False


def get_redis():
    global _client, _unavailable
    if _unavailable:
        return None
    if _client is not None:
        return _client
    try:
        import redis

        _client = redis.from_url(settings.redis_url, decode_responses=True)
        _client.ping()
        return _client
    except Exception:
        logger.warning("Redis unavailable — caching disabled")
        _unavailable = True
        return None


def cache_get(key: str) -> Optional[Any]:
    client = get_redis()
    if not client:
        return None
    try:
        raw = client.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def cache_set(key: str, value: Any, ttl: Optional[int] = None) -> None:
    client = get_redis()
    if not client:
        return
    try:
        client.setex(key, ttl or settings.cache_ttl_seconds, json.dumps(value, default=str))
    except Exception:
        logger.debug("cache_set failed for %s", key)


def cache_delete(key: str) -> None:
    client = get_redis()
    if not client:
        return
    try:
        client.delete(key)
    except Exception:
        pass
