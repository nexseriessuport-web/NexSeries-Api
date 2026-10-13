"""
Jikan provider — unofficial MAL REST API proxy.
Endpoint: https://api.jikan.moe/v4
Docs: https://docs.api.jikan.moe/
Rate limit: ≤3 req/s, ≤60 req/min (enforced by http_client backoff)

Status: VERIFIED (public API, no auth required)
Capabilities: search, details, episodes, schedule, recent, popular, genres
NOT available: streaming URLs
"""
from __future__ import annotations

import time
from typing import Any, Optional

from app.core import http_client
from app.core.cache import cache_get, cache_set, make_cache_key
from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.base import BaseProvider
from app.schemas.anime import (
    AnimeBase,
    AnimeDetail,
    CoverImage,
    Episode,
    PaginatedResult,
    ProviderHealth,
    ProviderStatus,
    ScheduleEntry,
    SearchFilters,
    Season,
    Title,
)

logger = get_logger(__name__)
_settings = get_settings()
_BASE = "https://api.jikan.moe/v4"


def _season_to_jikan(s: Optional[Season]) -> Optional[str]:
    if not s:
        return None
    return s.value.lower()


def _map_anime(raw: dict[str, Any]) -> AnimeBase:
    titles = raw.get("titles") or []
    english = next((t["title"] for t in titles if t.get("type") == "English"), None)
    romaji = next((t["title"] for t in titles if t.get("type") == "Default"), None)
    synonyms = [t["title"] for t in titles if t.get("type") == "Synonym"]
    native = next((t["title"] for t in titles if t.get("type") == "Japanese"), None)

    images = (raw.get("images") or {}).get("jpg") or {}
    genres = [g["name"] for g in (raw.get("genres") or [])]
    studios = [s["name"] for s in (raw.get("studios") or [])]

    season_raw = (raw.get("season") or "").upper()
    try:
        season = Season(season_raw) if season_raw else None
    except ValueError:
        season = None

    score_raw = raw.get("score")
    return AnimeBase(
        provider_id=str(raw["mal_id"]),
        canonical_id=None,           # Jikan is MAL — no AniList canonical
        mal_id=raw.get("mal_id"),
        title=Title(
            romaji=romaji or raw.get("title"),
            english=english,
            native=native,
            synonyms=synonyms,
        ),
        cover_image=CoverImage(
            large=images.get("large_image_url"),
            medium=images.get("image_url"),
        ),
        banner_image=None,
        description=raw.get("synopsis"),
        genres=genres,
        tags=[t["name"] for t in (raw.get("themes") or [])],
        season=season,
        season_year=raw.get("year"),
        episode_count=raw.get("episodes"),
        duration_minutes=None,
        status=raw.get("status"),
        format=raw.get("type"),
        score=float(score_raw) if score_raw else None,
        popularity=raw.get("popularity"),
        studios=studios,
        languages_available=[],
        subtitles_available=False,
        source_provider="jikan",
    )


class JikanProvider(BaseProvider):
    name = "jikan"
    base_url = _BASE
    status = ProviderStatus.VERIFIED
    capabilities = [
        "search", "details", "episodes", "schedule",
        "recent", "popular", "genres",
    ]

    async def _get(self, path: str, params: Optional[dict] = None) -> Optional[dict]:
        resp = await http_client.get(
            f"{_BASE}{path}",
            provider=self.name,
            params=params or {},
        )
        if resp is None:
            return None
        try:
            return resp.json()
        except Exception:
            return None

    # ── Search ────────────────────────────────────────────────────────

    async def search(self, filters: SearchFilters) -> PaginatedResult:
        cache_key = make_cache_key(
            "jikan", "search", str(filters.query), str(filters.genre),
            str(filters.year), str(filters.page),
        )
        cached = await cache_get(cache_key)
        if cached:
            return PaginatedResult(**cached)

        params: dict[str, Any] = {
            "page": filters.page,
            "limit": filters.per_page,
            "type": filters.format.lower() if filters.format else None,
            "status": _map_status_to_jikan(filters.status),
            "genres": None,
        }
        if filters.query:
            params["q"] = filters.query
        if filters.year:
            params["start_date"] = f"{filters.year}-01-01"
        # strip None
        params = {k: v for k, v in params.items() if v is not None}

        data = await self._get("/anime", params)
        if not data:
            return PaginatedResult(page=filters.page, per_page=filters.per_page)

        pagination = data.get("pagination") or {}
        results = [_map_anime(m) for m in (data.get("data") or [])]

        out = PaginatedResult(
            page=filters.page,
            per_page=filters.per_page,
            total=pagination.get("items", {}).get("total"),
            has_next_page=pagination.get("has_next_page", False),
            results=results,
        )
        await cache_set(cache_key, out.model_dump(), _settings.cache_ttl_search)
        return out

    # ── Detail ────────────────────────────────────────────────────────

    async def get_anime(self, provider_id: str) -> Optional[AnimeDetail]:
        cache_key = make_cache_key("jikan", "detail", provider_id)
        cached = await cache_get(cache_key)
        if cached:
            return AnimeDetail(**cached)

        data = await self._get(f"/anime/{provider_id}/full")
        if not data or not data.get("data"):
            return None

        raw = data["data"]
        base = _map_anime(raw)
        episodes = await self.get_episodes(provider_id)
        recs_data = await self._get(f"/anime/{provider_id}/recommendations")
        recs: list[AnimeBase] = []
        if recs_data:
            for r in (recs_data.get("data") or [])[:10]:
                entry = r.get("entry") or {}
                if entry:
                    recs.append(AnimeBase(
                        provider_id=str(entry.get("mal_id", "")),
                        mal_id=entry.get("mal_id"),
                        title=Title(romaji=entry.get("title")),
                        source_provider="jikan",
                    ))

        detail = AnimeDetail(
            **base.model_dump(),
            episodes=episodes,
            recommendations=recs,
        )
        await cache_set(cache_key, detail.model_dump(), _settings.cache_ttl_details)
        return detail

    # ── Episodes ──────────────────────────────────────────────────────

    async def get_episodes(self, provider_id: str) -> list[Episode]:
        cache_key = make_cache_key("jikan", "episodes", provider_id)
        cached = await cache_get(cache_key)
        if cached:
            return [Episode(**e) for e in cached]

        episodes: list[Episode] = []
        page = 1
        while page <= 10:  # guard: max 1000 episodes
            data = await self._get(f"/anime/{provider_id}/episodes", {"page": page})
            if not data:
                break
            for ep in (data.get("data") or []):
                episodes.append(Episode(
                    provider_id=f"{provider_id}-{ep.get('mal_id', ep.get('episode_id', ''))}",
                    mal_id=provider_id,
                    episode_number=ep.get("episode_id") or 0,
                    title=ep.get("title"),
                    air_date=ep.get("aired"),
                    filler=ep.get("filler"),
                    recap=ep.get("recap"),
                    servers=[],         # Jikan has no streaming
                ))
            pagination = data.get("pagination") or {}
            if not pagination.get("has_next_page"):
                break
            page += 1

        await cache_set(cache_key, [e.model_dump() for e in episodes], _settings.cache_ttl_episodes)
        return episodes

    # ── Popular ───────────────────────────────────────────────────────

    async def get_popular(self, page: int = 1, per_page: int = 20) -> PaginatedResult:
        cache_key = make_cache_key("jikan", "popular", str(page))
        cached = await cache_get(cache_key)
        if cached:
            return PaginatedResult(**cached)

        data = await self._get("/top/anime", {"page": page, "limit": per_page, "type": "tv"})
        if not data:
            return PaginatedResult(page=page, per_page=per_page)

        pagination = data.get("pagination") or {}
        results = [_map_anime(m) for m in (data.get("data") or [])]

        out = PaginatedResult(
            page=page, per_page=per_page,
            total=pagination.get("items", {}).get("total"),
            has_next_page=pagination.get("has_next_page", False),
            results=results,
        )
        await cache_set(cache_key, out.model_dump(), _settings.cache_ttl_trending)
        return out

    # ── Recent ────────────────────────────────────────────────────────

    async def get_recent(self, page: int = 1, per_page: int = 20) -> PaginatedResult:
        """Returns currently airing anime."""
        cache_key = make_cache_key("jikan", "recent", str(page))
        cached = await cache_get(cache_key)
        if cached:
            return PaginatedResult(**cached)

        data = await self._get("/anime", {
            "status": "airing",
            "order_by": "start_date",
            "sort": "desc",
            "page": page,
            "limit": per_page,
        })
        if not data:
            return PaginatedResult(page=page, per_page=per_page)

        pagination = data.get("pagination") or {}
        results = [_map_anime(m) for m in (data.get("data") or [])]

        out = PaginatedResult(
            page=page, per_page=per_page,
            total=pagination.get("items", {}).get("total"),
            has_next_page=pagination.get("has_next_page", False),
            results=results,
        )
        await cache_set(cache_key, out.model_dump(), _settings.cache_ttl_search)
        return out

    # ── Schedule ──────────────────────────────────────────────────────

    async def get_schedule(self) -> list[ScheduleEntry]:
        """Returns today's airing schedule from Jikan."""
        import datetime
        cache_key = make_cache_key("jikan", "schedule")
        cached = await cache_get(cache_key)
        if cached:
            return [ScheduleEntry(**e) for e in cached]

        # Jikan schedules endpoint: /schedules?day=<weekday>
        today = datetime.datetime.utcnow().strftime("%A").lower()
        data = await self._get("/schedules", {"filter": today, "limit": 25})
        entries: list[ScheduleEntry] = []
        if data:
            for item in (data.get("data") or []):
                t = item.get("title") or ""
                entries.append(ScheduleEntry(
                    canonical_id=None,
                    title=Title(romaji=t),
                    episode_number=0,          # Jikan schedule has no per-episode air time
                    air_timestamp=int(datetime.datetime.utcnow().timestamp()),
                    provider="jikan",
                ))

        await cache_set(cache_key, [e.model_dump() for e in entries], _settings.cache_ttl_schedule)
        return entries

    # ── Health ────────────────────────────────────────────────────────

    async def health_check(self) -> ProviderHealth:
        start = time.monotonic()
        data = await self._get("/anime/1")
        latency = (time.monotonic() - start) * 1000
        if data and data.get("data"):
            return ProviderHealth(
                provider=self.name,
                status=ProviderStatus.VERIFIED,
                latency_ms=round(latency, 2),
                capabilities=self.capabilities,
            )
        return ProviderHealth(
            provider=self.name,
            status=ProviderStatus.DEGRADED,
            latency_ms=round(latency, 2),
            capabilities=self.capabilities,
            notes="Health probe returned unexpected response",
        )


def _map_status_to_jikan(status: Optional[str]) -> Optional[str]:
    mapping = {
        "RELEASING": "airing",
        "FINISHED": "complete",
        "NOT_YET_RELEASED": "upcoming",
    }
    return mapping.get((status or "").upper())
