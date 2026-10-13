"""
Provider contract tests.

These tests make REAL HTTP calls to verify provider APIs behave as expected.
They are skipped in CI unless LIVE_PROVIDER_TESTS=1 is set.

Run locally:
    LIVE_PROVIDER_TESTS=1 pytest tests/contract/ -v

Streaming provider tests (Anikito, Miruro, AniVault, YumeZone) require
STREAMING_CONTRACT_TESTS=1 AND the respective provider to be enabled.
"""
from __future__ import annotations

import os
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("LIVE_PROVIDER_TESTS") != "1",
    reason="Set LIVE_PROVIDER_TESTS=1 to run live provider contract tests",
)


@pytest.fixture
def anilist_provider():
    from app.providers.anilist import AniListProvider
    return AniListProvider()


@pytest.fixture
def jikan_provider():
    from app.providers.jikan import JikanProvider
    return JikanProvider()


# ── AniList contracts ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_anilist_search_returns_results(anilist_provider):
    from app.schemas.anime import SearchFilters
    result = await anilist_provider.search(SearchFilters(query="Naruto"))
    assert len(result.results) > 0
    first = result.results[0]
    assert first.provider_id
    assert first.title.romaji or first.title.english
    assert first.source_provider == "anilist"


@pytest.mark.asyncio
async def test_anilist_detail_cowboy_bebop(anilist_provider):
    # AniList ID 1 = Cowboy Bebop
    detail = await anilist_provider.get_anime("1")
    assert detail is not None
    assert detail.canonical_id == 1
    assert detail.title.romaji is not None
    assert isinstance(detail.genres, list)
    assert isinstance(detail.recommendations, list)


@pytest.mark.asyncio
async def test_anilist_trending(anilist_provider):
    result = await anilist_provider.get_trending(page=1, per_page=10)
    assert len(result.results) > 0


@pytest.mark.asyncio
async def test_anilist_schedule(anilist_provider):
    schedule = await anilist_provider.get_schedule()
    assert isinstance(schedule, list)
    if schedule:
        assert schedule[0].air_timestamp > 0
        assert schedule[0].provider == "anilist"


@pytest.mark.asyncio
async def test_anilist_health(anilist_provider):
    health = await anilist_provider.health_check()
    assert health.status.value in ("verified", "degraded")
    assert health.latency_ms is not None
    assert health.latency_ms >= 0


# ── Jikan contracts ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jikan_search_returns_results(jikan_provider):
    from app.schemas.anime import SearchFilters
    result = await jikan_provider.search(SearchFilters(query="Cowboy Bebop"))
    assert len(result.results) > 0
    first = result.results[0]
    assert first.mal_id is not None
    assert first.source_provider == "jikan"


@pytest.mark.asyncio
async def test_jikan_detail(jikan_provider):
    # MAL ID 1 = Cowboy Bebop
    detail = await jikan_provider.get_anime("1")
    assert detail is not None
    assert detail.mal_id == 1


@pytest.mark.asyncio
async def test_jikan_episodes(jikan_provider):
    episodes = await jikan_provider.get_episodes("1")
    assert len(episodes) > 0
    ep1 = episodes[0]
    assert ep1.episode_number > 0
    # Jikan never provides streaming servers
    assert ep1.servers == []


@pytest.mark.asyncio
async def test_jikan_popular(jikan_provider):
    result = await jikan_provider.get_popular(page=1, per_page=10)
    assert len(result.results) > 0


@pytest.mark.asyncio
async def test_jikan_health(jikan_provider):
    health = await jikan_provider.health_check()
    assert health.status.value in ("verified", "degraded")


# ── Streaming provider contracts (opt-in) ─────────────────────────────────

streaming_mark = pytest.mark.skipif(
    os.environ.get("STREAMING_CONTRACT_TESTS") != "1",
    reason="Set STREAMING_CONTRACT_TESTS=1 to run streaming contract tests",
)


@streaming_mark
@pytest.mark.asyncio
async def test_streaming_provider_health_check():
    """
    Template: verify each streaming provider returns a health response.
    Fill in concrete assertions once the provider API is confirmed.
    """
    for provider_name in ("anikito", "miruro", "anivault", "yumezone"):
        from app.providers import registry
        p = registry.get_provider(provider_name)
        if p is None:
            pytest.skip(f"{provider_name} not enabled")
        health = await p.health_check()
        assert health.provider == provider_name
        # A UNTESTED provider must not lie about its status
        assert health.status.value == "untested"
