"""
Two-backend cache:
  memory — cachetools TTLCache, suitable for single-process dev/Railway deploys
  redis  — redis-py async, suitable for multi-worker production

Usage:
    from app.core.cache import cache_get, cache_set

All values are JSON-serialised strings.
"""
from __future__ import annotations

import json
from typing import Any

from cachetools import TTLCache

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
_settings = get_settings()

# ── In-memory backend ─────────────────────────────────────────────────────
_MEM_CACHE: TTLCache = TTLCache(maxsize=4096, ttl=_settings.cache_ttl_details)

# ── Redis backend ─────────────────────────────────────────────────────────
_redis_client: Any = None


async def _get_redis() -> Any:
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis  # type: ignore

            _redis_client = await aioredis.from_url(
                _settings.redis_url, encoding="utf-8", decode_responses=True
            )
        except Exception as exc:
            logger.warning("redis_connect_failed", error=str(exc))
            _redis_client = None
    return _redis_client


# ── Public interface ──────────────────────────────────────────────────────

async def cache_get(key: str) -> Any | None:
    if _settings.cache_backend == "redis":
        r = await _get_redis()
        if r:
            try:
                raw = await r.get(key)
                return json.loads(raw) if raw else None
            except Exception as exc:
                logger.warning("cache_get_redis_error", key=key, error=str(exc))
    # fall through to memory
    raw = _MEM_CACHE.get(key)
    return json.loads(raw) if raw else None


async def cache_set(key: str, value: Any, ttl: int) -> None:
    serialised = json.dumps(value, default=str)

    if _settings.cache_backend == "redis":
        r = await _get_redis()
        if r:
            try:
                await r.setex(key, ttl, serialised)
                return
            except Exception as exc:
                logger.warning("cache_set_redis_error", key=key, error=str(exc))
    # fall through to memory (re-insert with adjusted TTLCache ttl ignored,
    # we store with the global TTLCache default — acceptable for dev)
    _MEM_CACHE[key] = serialised


async def cache_delete(key: str) -> None:
    _MEM_CACHE.pop(key, None)
    if _settings.cache_backend == "redis":
        r = await _get_redis()
        if r:
            try:
                await r.delete(key)
            except Exception:
                pass


def make_cache_key(*parts: str) -> str:
    return ":".join(parts)
