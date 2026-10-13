"""
All anime API endpoints.

Base path: /api/v1
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import verify_api_key
from app.providers import registry
from app.schemas.anime import (
    AnimeDetail,
    Language,
    PaginatedResult,
    ProviderHealth,
    ProviderStatus,
    ScheduleEntry,
    SearchFilters,
    Season,
)

router = APIRouter(prefix="/api/v1", dependencies=[Depends(verify_api_key)])

Auth = Annotated[None, Depends(verify_api_key)]


# ── Helpers ───────────────────────────────────────────────────────────────

def _paginate(page: int, per_page: int) -> tuple[int, int]:
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be ≥ 1")
    if per_page < 1 or per_page > 50:
        raise HTTPException(status_code=400, detail="per_page must be 1–50")
    return page, per_page


# ── Search ────────────────────────────────────────────────────────────────

@router.get(
    "/search",
    response_model=PaginatedResult,
    summary="Search anime",
    description=(
        "Full-text search with optional filters. "
        "Falls back from AniList → Jikan if primary is unavailable. "
        "Language and server filters apply only to streaming providers."
    ),
)
async def search_anime(
    q: Optional[str] = Query(None, description="Search query"),
    genre: Optional[str] = Query(None),
    season: Optional[Season] = Query(None),
    year: Optional[int] = Query(None, ge=1960, le=2100),
    format: Optional[str] = Query(None, description="TV | MOVIE | OVA | ONA | SPECIAL"),
    status_: Optional[str] = Query(None, alias="status", description="RELEASING | FINISHED | NOT_YET_RELEASED"),
    language: Optional[Language] = Query(None),
    provider: Optional[str] = Query(None, description="Force specific provider"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
) -> PaginatedResult:
    filters = SearchFilters(
        query=q,
        genre=genre,
        season=season,
        year=year,
        format=format,
        status=status_,
        language=language,
        page=page,
        per_page=per_page,
    )

    if provider:
        p = registry.get_provider(provider)
        if not p:
            raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found or disabled")
        try:
            return await p.search(filters)
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc))

    # fallback chain
    for p in registry.metadata_providers():
        try:
            result = await p.search(filters)
            if result.results:
                return result
        except Exception:
            continue

    return PaginatedResult(page=page, per_page=per_page)


# ── Anime details ─────────────────────────────────────────────────────────

@router.get(
    "/anime/{provider}/{id}",
    response_model=AnimeDetail,
    summary="Anime details",
    description=(
        "Full anime details including metadata, relations, and (where available) episode list. "
        "Streaming sources are populated only by streaming providers."
    ),
)
async def get_anime(
    provider: str,
    id: str,
) -> AnimeDetail:
    p = registry.get_provider(provider)
    if not p:
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found or disabled")

    try:
        detail = await p.get_anime(id)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))

    if detail is None:
        raise HTTPException(status_code=404, detail=f"Anime '{id}' not found on {provider}")
    return detail


# ── Episodes ──────────────────────────────────────────────────────────────

@router.get(
    "/anime/{provider}/{id}/episodes",
    summary="Episode list",
    description="Returns episodes from the specified provider. Streaming providers may include server URLs.",
)
async def get_episodes(provider: str, id: str):
    p = registry.get_provider(provider)
    if not p:
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found or disabled")

    try:
        return {"provider": provider, "anime_id": id, "episodes": await p.get_episodes(id)}
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))


# ── Trending ──────────────────────────────────────────────────────────────

@router.get("/trending", response_model=PaginatedResult, summary="Trending anime")
async def get_trending(
    provider: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
) -> PaginatedResult:
    providers = [registry.get_provider(provider)] if provider else registry.metadata_providers()
    providers = [p for p in providers if p is not None]

    for p in providers:
        try:
            result = await p.get_trending(page=page, per_page=per_page)
            if result.results:
                return result
        except NotImplementedError:
            continue

    return PaginatedResult(page=page, per_page=per_page)


# ── Popular ───────────────────────────────────────────────────────────────

@router.get("/popular", response_model=PaginatedResult, summary="Popular anime")
async def get_popular(
    provider: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
) -> PaginatedResult:
    providers = [registry.get_provider(provider)] if provider else registry.metadata_providers()
    providers = [p for p in providers if p is not None]

    for p in providers:
        try:
            result = await p.get_popular(page=page, per_page=per_page)
            if result.results:
                return result
        except NotImplementedError:
            continue

    return PaginatedResult(page=page, per_page=per_page)


# ── Recent releases ───────────────────────────────────────────────────────

@router.get("/recent", response_model=PaginatedResult, summary="Recent releases / currently airing")
async def get_recent(
    provider: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
) -> PaginatedResult:
    providers = [registry.get_provider(provider)] if provider else registry.metadata_providers()
    providers = [p for p in providers if p is not None]

    for p in providers:
        try:
            result = await p.get_recent(page=page, per_page=per_page)
            if result.results:
                return result
        except NotImplementedError:
            continue

    return PaginatedResult(page=page, per_page=per_page)


# ── Schedule ──────────────────────────────────────────────────────────────

@router.get("/schedule", response_model=list[ScheduleEntry], summary="Airing schedule")
async def get_schedule(
    provider: Optional[str] = Query(default="anilist"),
) -> list[ScheduleEntry]:
    p = registry.get_provider(provider or "anilist")
    if not p:
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found or disabled")

    try:
        return await p.get_schedule()
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))


# ── Recommendations ───────────────────────────────────────────────────────

@router.get(
    "/anime/{provider}/{id}/recommendations",
    summary="Recommendations for an anime",
)
async def get_recommendations(provider: str, id: str):
    p = registry.get_provider(provider)
    if not p:
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found or disabled")

    try:
        recs = await p.get_recommendations(id)
        return {"provider": provider, "anime_id": id, "recommendations": recs}
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))


# ── Provider list ─────────────────────────────────────────────────────────

@router.get("/providers", summary="List all enabled providers")
async def list_providers():
    return {
        "providers": [
            {
                "name": p.name,
                "status": p.status,
                "capabilities": p.capabilities,
                "base_url": p.base_url,
            }
            for p in registry.list_providers()
        ]
    }


# ── Health ────────────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=list[ProviderHealth],
    summary="Provider health checks",
    description="Runs live health probes against all enabled providers.",
)
async def provider_health() -> list[ProviderHealth]:
    return await registry.all_health()
