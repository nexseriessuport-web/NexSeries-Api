"""
AniList provider — uses the official public GraphQL API.
Endpoint: https://graphql.anilist.co
Docs: https://anilist.gitbook.io/anilist-apiv2-docs/
Rate limit: ~90 requests/min unauthenticated (handled by retry/backoff in http_client).

Status: VERIFIED (public API, no auth required for read operations)
Capabilities: search, details, trending, popular, schedule, recommendations, genres
NOT available: streaming URLs (AniList is metadata-only)
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
    Language,
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

_ENDPOINT = "https://graphql.anilist.co"

# ── GraphQL fragments ─────────────────────────────────────────────────────

_MEDIA_FRAGMENT = """
fragment MediaFields on Media {
  id
  idMal
  title { romaji english native synonyms }
  coverImage { large medium color }
  bannerImage
  description(asHtml: false)
  genres
  tags { name }
  season
  seasonYear
  episodes
  duration
  status
  format
  averageScore
  popularity
  studios(isMain: true) { nodes { name } }
  nextAiringEpisode { episode timeUntilAiring }
  trailer { id site }
}
"""

_SEARCH_QUERY = """
query ($page: Int, $perPage: Int, $search: String, $genre: String,
       $season: MediaSeason, $seasonYear: Int, $format: MediaFormat, $status: MediaStatus) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { total hasNextPage }
    media(
      type: ANIME
      search: $search
      genre: $genre
      season: $season
      seasonYear: $seasonYear
      format: $format
      status: $status
      sort: SEARCH_MATCH
    ) { ...MediaFields }
  }
}
""" + _MEDIA_FRAGMENT

_DETAIL_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    ...MediaFields
    recommendations(page: 1, perPage: 10) {
      nodes { mediaRecommendation { ...MediaFields } }
    }
    relations {
      edges { relationType node { ...MediaFields } }
    }
  }
}
""" + _MEDIA_FRAGMENT

_TRENDING_QUERY = """
query ($page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { total hasNextPage }
    media(type: ANIME, sort: TRENDING_DESC) { ...MediaFields }
  }
}
""" + _MEDIA_FRAGMENT

_POPULAR_QUERY = """
query ($page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { total hasNextPage }
    media(type: ANIME, sort: POPULARITY_DESC) { ...MediaFields }
  }
}
""" + _MEDIA_FRAGMENT

_SCHEDULE_QUERY = """
query ($page: Int, $notYetAired: Boolean) {
  Page(page: $page, perPage: 50) {
    pageInfo { hasNextPage }
    airingSchedules(notYetAired: $notYetAired, sort: TIME) {
      episode
      airingAt
      media { id idMal title { romaji english native } }
    }
  }
}
"""


# ── Helper: map raw AniList media dict → AnimeBase ────────────────────────

def _map_media(raw: dict[str, Any]) -> AnimeBase:
    t = raw.get("title") or {}
    cover = raw.get("coverImage") or {}
    tags = [tag["name"] for tag in (raw.get("tags") or []) if tag.get("name")]
    studios = [s["name"] for s in ((raw.get("studios") or {}).get("nodes") or [])]

    # AniList doesn't provide streaming language info — mark unknown
    trailer_site = (raw.get("trailer") or {}).get("site")
    trailer_id = (raw.get("trailer") or {}).get("id")
    trailer_url: Optional[str] = None
    if trailer_site == "youtube" and trailer_id:
        trailer_url = f"https://www.youtube.com/watch?v={trailer_id}"

    return AnimeBase(
        provider_id=str(raw["id"]),
        canonical_id=raw.get("id"),
        mal_id=raw.get("idMal"),
        title=Title(
            romaji=t.get("romaji"),
            english=t.get("english"),
            native=t.get("native"),
            synonyms=t.get("synonyms") or [],
        ),
        cover_image=CoverImage(
            large=cover.get("large"),
            medium=cover.get("medium"),
            color=cover.get("color"),
        ) if cover else None,
        banner_image=raw.get("bannerImage"),
        description=raw.get("description"),
        genres=raw.get("genres") or [],
        tags=tags,
        season=Season(raw["season"]) if raw.get("season") and raw["season"] in Season._value2member_map_ else None,
        season_year=raw.get("seasonYear"),
        episode_count=raw.get("episodes"),
        duration_minutes=raw.get("duration"),
        status=raw.get("status"),
        format=raw.get("format"),
        score=(raw.get("averageScore") or 0) / 10 if raw.get("averageScore") else None,
        popularity=raw.get("popularity"),
        studios=studios,
        languages_available=[],        # AniList metadata only
        subtitles_available=False,
        source_provider="anilist",
    )


class AniListProvider(BaseProvider):
    name = "anilist"
    base_url = _ENDPOINT
    status = ProviderStatus.VERIFIED
    capabilities = [
        "search", "details", "trending", "popular",
        "schedule", "recommendations", "genres", "relations",
    ]

    async def _gql(self, query: str, variables: dict) -> Optional[dict]:
        resp = await http_client.post(
            _ENDPOINT,
            provider=self.name,
            json={"query": query, "variables": variables},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        if resp is None:
            return None
        try:
            data = resp.json()
        except Exception:
            logger.error("anilist_json_parse_failed")
            return None

        if "errors" in data:
            logger.error("anilist_gql_error", errors=data["errors"])
            return None

        return data.get("data")

    # ── Search ────────────────────────────────────────────────────────

    async def search(self, filters: SearchFilters) -> PaginatedResult:
        cache_key = make_cache_key(
            "anilist", "search",
            str(filters.query), str(filters.genre), str(filters.season),
            str(filters.year), str(filters.format), str(filters.status),
            str(filters.page), str(filters.per_page),
        )
        cached = await cache_get(cache_key)
        if cached:
            return PaginatedResult(**cached)

        variables: dict[str, Any] = {
            "page": filters.page,
            "perPage": filters.per_page,
        }
        if filters.query:
            variables["search"] = filters.query
        if filters.genre:
            variables["genre"] = filters.genre
        if filters.season:
            variables["season"] = filters.season.value
        if filters.year:
            variables["seasonYear"] = filters.year
        if filters.format:
            variables["format"] = filters.format.upper()
        if filters.status:
            variables["status"] = filters.status.upper()

        data = await self._gql(_SEARCH_QUERY, variables)
        if not data:
            return PaginatedResult(page=filters.page, per_page=filters.per_page)

        page_data = data.get("Page") or {}
        page_info = page_data.get("pageInfo") or {}
        results = [_map_media(m) for m in (page_data.get("media") or [])]

        out = PaginatedResult(
            page=filters.page,
            per_page=filters.per_page,
            total=page_info.get("total"),
            has_next_page=page_info.get("hasNextPage", False),
            results=results,
        )
        await cache_set(cache_key, out.model_dump(), _settings.cache_ttl_search)
        return out

    # ── Detail ────────────────────────────────────────────────────────

    async def get_anime(self, provider_id: str) -> Optional[AnimeDetail]:
        cache_key = make_cache_key("anilist", "detail", provider_id)
        cached = await cache_get(cache_key)
        if cached:
            return AnimeDetail(**cached)

        data = await self._gql(_DETAIL_QUERY, {"id": int(provider_id)})
        if not data or not data.get("Media"):
            return None

        raw = data["Media"]
        base = _map_media(raw)

        # Recommendations
        recs: list[AnimeBase] = []
        for node in (((raw.get("recommendations") or {}).get("nodes")) or []):
            if node.get("mediaRecommendation"):
                recs.append(_map_media(node["mediaRecommendation"]))

        # Relations
        relations: list[AnimeBase] = []
        for edge in (((raw.get("relations") or {}).get("edges")) or []):
            if edge.get("node"):
                relations.append(_map_media(edge["node"]))

        # Trailer
        trailer_url: Optional[str] = None
        trailer = raw.get("trailer") or {}
        if trailer.get("site") == "youtube" and trailer.get("id"):
            trailer_url = f"https://www.youtube.com/watch?v={trailer['id']}"

        # Next airing
        nae = raw.get("nextAiringEpisode") or {}
        next_ep = nae.get("episode")
        next_at_delta = nae.get("timeUntilAiring")
        next_at_ts: Optional[str] = None
        if next_at_delta is not None:
            import datetime
            at = datetime.datetime.utcnow() + datetime.timedelta(seconds=next_at_delta)
            next_at_ts = at.isoformat() + "Z"

        detail = AnimeDetail(
            **base.model_dump(),
            episodes=[],          # AniList has no playback — leave empty
            recommendations=recs,
            relations=relations,
            trailer_url=trailer_url,
            next_airing_episode=next_ep,
            next_airing_at=next_at_ts,
        )
        await cache_set(cache_key, detail.model_dump(), _settings.cache_ttl_details)
        return detail

    # ── Trending ──────────────────────────────────────────────────────

    async def get_trending(self, page: int = 1, per_page: int = 20) -> PaginatedResult:
        cache_key = make_cache_key("anilist", "trending", str(page), str(per_page))
        cached = await cache_get(cache_key)
        if cached:
            return PaginatedResult(**cached)

        data = await self._gql(_TRENDING_QUERY, {"page": page, "perPage": per_page})
        if not data:
            return PaginatedResult(page=page, per_page=per_page)

        page_data = data.get("Page") or {}
        page_info = page_data.get("pageInfo") or {}
        results = [_map_media(m) for m in (page_data.get("media") or [])]

        out = PaginatedResult(
            page=page, per_page=per_page,
            total=page_info.get("total"),
            has_next_page=page_info.get("hasNextPage", False),
            results=results,
        )
        await cache_set(cache_key, out.model_dump(), _settings.cache_ttl_trending)
        return out

    # ── Popular ───────────────────────────────────────────────────────

    async def get_popular(self, page: int = 1, per_page: int = 20) -> PaginatedResult:
        cache_key = make_cache_key("anilist", "popular", str(page), str(per_page))
        cached = await cache_get(cache_key)
        if cached:
            return PaginatedResult(**cached)

        data = await self._gql(_POPULAR_QUERY, {"page": page, "perPage": per_page})
        if not data:
            return PaginatedResult(page=page, per_page=per_page)

        page_data = data.get("Page") or {}
        page_info = page_data.get("pageInfo") or {}
        results = [_map_media(m) for m in (page_data.get("media") or [])]

        out = PaginatedResult(
            page=page, per_page=per_page,
            total=page_info.get("total"),
            has_next_page=page_info.get("hasNextPage", False),
            results=results,
        )
        await cache_set(cache_key, out.model_dump(), _settings.cache_ttl_trending)
        return out

    # ── Schedule ──────────────────────────────────────────────────────

    async def get_schedule(self) -> list[ScheduleEntry]:
        cache_key = make_cache_key("anilist", "schedule")
        cached = await cache_get(cache_key)
        if cached:
            return [ScheduleEntry(**e) for e in cached]

        entries: list[ScheduleEntry] = []
        page = 1
        while page <= 3:  # cap at 3 pages to stay within rate limits
            data = await self._gql(_SCHEDULE_QUERY, {"page": page, "notYetAired": True})
            if not data:
                break
            page_data = data.get("Page") or {}
            for item in (page_data.get("airingSchedules") or []):
                media = item.get("media") or {}
                t = media.get("title") or {}
                entries.append(ScheduleEntry(
                    canonical_id=media.get("id"),
                    title=Title(
                        romaji=t.get("romaji"),
                        english=t.get("english"),
                        native=t.get("native"),
                    ),
                    episode_number=item.get("episode", 0),
                    air_timestamp=item.get("airingAt", 0),
                    provider="anilist",
                ))
            if not (page_data.get("pageInfo") or {}).get("hasNextPage"):
                break
            page += 1

        await cache_set(cache_key, [e.model_dump() for e in entries], _settings.cache_ttl_schedule)
        return entries

    # ── Recommendations ───────────────────────────────────────────────

    async def get_recommendations(self, provider_id: str) -> list[AnimeBase]:
        detail = await self.get_anime(provider_id)
        return detail.recommendations if detail else []

    # ── Health ────────────────────────────────────────────────────────

    async def health_check(self) -> ProviderHealth:
        start = time.monotonic()
        data = await self._gql(
            "query { Media(id: 1, type: ANIME) { id } }",
            {},
        )
        latency = (time.monotonic() - start) * 1000

        if data and data.get("Media"):
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
            notes="Health check query returned unexpected result",
        )
