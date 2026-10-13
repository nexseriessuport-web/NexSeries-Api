"""
Shared async HTTP client with:
  - configurable timeouts
  - tenacity retry with exponential backoff
  - semaphore-based concurrency cap
  - structured error responses (never raises raw exceptions to callers)
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
_settings = get_settings()

_semaphore = asyncio.Semaphore(_settings.http_concurrency_limit)

# Single shared client — created on first use, closed on shutdown
_client: httpx.AsyncClient | None = None


def _build_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(_settings.http_timeout),
        follow_redirects=True,
        headers={"User-Agent": "AnimeAggregator/1.0 (+https://github.com/nexseries)"},
        http2=True,
    )


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = _build_client()
    return _client


async def close_client() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


# ---------------------------------------------------------------------------
# Retry decorator — only retries transient network / 5xx errors
# ---------------------------------------------------------------------------
_RETRYABLE = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.RemoteProtocolError,
)


def _is_retryable_status(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return False


@retry(
    retry=retry_if_exception_type(_RETRYABLE) | retry_if_exception_type(httpx.HTTPStatusError),
    stop=stop_after_attempt(_settings.http_max_retries),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
    reraise=True,
)
async def _fetch_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    resp = await client.request(method, url, **kwargs)
    if resp.status_code >= 500 or resp.status_code == 429:
        logger.warning("retryable_status", url=url, status=resp.status_code)
        resp.raise_for_status()
    return resp


async def request(
    method: str,
    url: str,
    *,
    provider: str = "unknown",
    **kwargs: Any,
) -> httpx.Response | None:
    """
    Make an HTTP request inside the concurrency semaphore.
    Returns None on terminal failure so callers can handle gracefully.
    """
    client = await get_client()
    async with _semaphore:
        try:
            resp = await _fetch_with_retry(client, method, url, **kwargs)
            logger.debug("http_ok", provider=provider, url=url, status=resp.status_code)
            return resp
        except httpx.HTTPStatusError as exc:
            logger.error(
                "http_error",
                provider=provider,
                url=url,
                status=exc.response.status_code,
            )
            return None
        except Exception as exc:
            logger.error("http_exception", provider=provider, url=url, error=str(exc))
            return None


async def get(url: str, *, provider: str = "unknown", **kwargs: Any) -> httpx.Response | None:
    return await request("GET", url, provider=provider, **kwargs)


async def post(url: str, *, provider: str = "unknown", **kwargs: Any) -> httpx.Response | None:
    return await request("POST", url, provider=provider, **kwargs)
