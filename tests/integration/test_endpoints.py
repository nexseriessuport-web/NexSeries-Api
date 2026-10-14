"""
Integration tests for all REST endpoints.
HTTP calls are intercepted with respx so no real network traffic occurs.
"""
from __future__ import annotations

import json

import pytest
import respx
import httpx
from fastapi.testclient import TestClient

from tests.conftest import (
    ANILIST_SEARCH_FIXTURE,
    ANILIST_DETAIL_FIXTURE,
    JIKAN_SEARCH_FIXTURE,
)


# ── Root ──────────────────────────────────────────────────────────────────

def test_root_serves_web_app(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "NEXSERIES" in resp.text
    assert "API explorer" in resp.text


# ── Provider list ─────────────────────────────────────────────────────────

def test_list_providers(client: TestClient):
    resp = client.get("/api/v1/providers")
    assert resp.status_code == 200
    body = resp.json()
    names = [p["name"] for p in body["providers"]]
    assert "anilist" in names
    assert "jikan" in names
    # Untested providers must not be enabled by default
    for untested in ("anikito", "miruro", "anivault", "yumezone"):
        assert untested not in names


# ── Search ────────────────────────────────────────────────────────────────

@respx.mock
def test_search_anilist(client: TestClient):
    respx.post("https://graphql.anilist.co").mock(
        return_value=httpx.Response(200, json=ANILIST_SEARCH_FIXTURE)
    )
    resp = client.get("/api/v1/search?q=cowboy+bebop&provider=anilist")
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"][0]["provider_id"] == "1"
    assert body["results"][0]["title"]["romaji"] == "Cowboy Bebop"
    assert body["results"][0]["source_provider"] == "anilist"


@respx.mock
def test_search_jikan(client: TestClient):
    respx.get("https://api.jikan.moe/v4/anime").mock(
        return_value=httpx.Response(200, json=JIKAN_SEARCH_FIXTURE)
    )
    resp = client.get("/api/v1/search?q=cowboy+bebop&provider=jikan")
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"][0]["mal_id"] == 1


@respx.mock
def test_search_fallback_to_jikan(client: TestClient):
    """When AniList returns empty results, fallback to Jikan."""
    empty_anilist = {
        "data": {"Page": {"pageInfo": {"total": 0, "hasNextPage": False}, "media": []}}
    }
    respx.post("https://graphql.anilist.co").mock(
        return_value=httpx.Response(200, json=empty_anilist)
    )
    respx.get("https://api.jikan.moe/v4/anime").mock(
        return_value=httpx.Response(200, json=JIKAN_SEARCH_FIXTURE)
    )
    resp = client.get("/api/v1/search?q=cowboy+bebop")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 1


def test_search_invalid_page(client: TestClient):
    resp = client.get("/api/v1/search?page=0")
    assert resp.status_code in (400, 422)


def test_search_per_page_too_large(client: TestClient):
    resp = client.get("/api/v1/search?per_page=999")
    assert resp.status_code == 422


def test_search_unknown_provider(client: TestClient):
    resp = client.get("/api/v1/search?provider=doesnotexist")
    assert resp.status_code == 404


# ── Anime details ─────────────────────────────────────────────────────────

@respx.mock
def test_anime_detail_anilist(client: TestClient):
    respx.post("https://graphql.anilist.co").mock(
        return_value=httpx.Response(200, json=ANILIST_DETAIL_FIXTURE)
    )
    resp = client.get("/api/v1/anime/anilist/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider_id"] == "1"
    assert body["title"]["romaji"] == "Cowboy Bebop"


@respx.mock
def test_anime_detail_not_found(client: TestClient):
    respx.post("https://graphql.anilist.co").mock(
        return_value=httpx.Response(200, json={"data": {"Media": None}})
    )
    resp = client.get("/api/v1/anime/anilist/999999")
    assert resp.status_code == 404


def test_anime_detail_bad_provider(client: TestClient):
    resp = client.get("/api/v1/anime/badprovider/1")
    assert resp.status_code == 404


def test_anime_detail_untested_provider(client: TestClient):
    """Untested providers are disabled — should return 404."""
    resp = client.get("/api/v1/anime/anikito/1")
    assert resp.status_code == 404


# ── Episodes ──────────────────────────────────────────────────────────────

@respx.mock
def test_episodes_jikan(client: TestClient):
    ep_fixture = {
        "data": [
            {"mal_id": 1, "episode_id": 1, "title": "Asteroid Blues", "aired": "1998-10-23",
             "filler": False, "recap": False},
        ],
        "pagination": {"has_next_page": False},
    }
    respx.get("https://api.jikan.moe/v4/anime/1/episodes").mock(
        return_value=httpx.Response(200, json=ep_fixture)
    )
    resp = client.get("/api/v1/anime/jikan/1/episodes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["episodes"][0]["title"] == "Asteroid Blues"
    assert body["episodes"][0]["episode_number"] == 1


def test_episodes_anilist_not_supported(client: TestClient):
    """AniList doesn't provide episodes — should return 501."""
    resp = client.get("/api/v1/anime/anilist/1/episodes")
    assert resp.status_code == 501


# ── Trending ──────────────────────────────────────────────────────────────

@respx.mock
def test_trending(client: TestClient):
    respx.post("https://graphql.anilist.co").mock(
        return_value=httpx.Response(200, json=ANILIST_SEARCH_FIXTURE)
    )
    resp = client.get("/api/v1/trending?provider=anilist")
    assert resp.status_code == 200


# ── Popular ───────────────────────────────────────────────────────────────

@respx.mock
def test_popular(client: TestClient):
    respx.post("https://graphql.anilist.co").mock(
        return_value=httpx.Response(200, json=ANILIST_SEARCH_FIXTURE)
    )
    resp = client.get("/api/v1/popular?provider=anilist")
    assert resp.status_code == 200


# ── Recent ────────────────────────────────────────────────────────────────

@respx.mock
def test_recent(client: TestClient):
    respx.get("https://api.jikan.moe/v4/anime").mock(
        return_value=httpx.Response(200, json=JIKAN_SEARCH_FIXTURE)
    )
    resp = client.get("/api/v1/recent?provider=jikan")
    assert resp.status_code == 200


# ── Schedule ──────────────────────────────────────────────────────────────

@respx.mock
def test_schedule_anilist(client: TestClient):
    schedule_fixture = {
        "data": {
            "Page": {
                "pageInfo": {"hasNextPage": False},
                "airingSchedules": [
                    {
                        "episode": 5,
                        "airingAt": 1700000000,
                        "media": {
                            "id": 42,
                            "idMal": 42,
                            "title": {"romaji": "Test Anime", "english": None, "native": None},
                        },
                    }
                ],
            }
        }
    }
    respx.post("https://graphql.anilist.co").mock(
        return_value=httpx.Response(200, json=schedule_fixture)
    )
    resp = client.get("/api/v1/schedule?provider=anilist")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert body[0]["episode_number"] == 5


# ── Recommendations ───────────────────────────────────────────────────────

@respx.mock
def test_recommendations(client: TestClient):
    respx.post("https://graphql.anilist.co").mock(
        return_value=httpx.Response(200, json=ANILIST_DETAIL_FIXTURE)
    )
    resp = client.get("/api/v1/anime/anilist/1/recommendations")
    assert resp.status_code == 200
    body = resp.json()
    assert "recommendations" in body


# ── Malformed input tests ─────────────────────────────────────────────────

def test_search_malformed_year(client: TestClient):
    resp = client.get("/api/v1/search?year=notayear")
    assert resp.status_code == 422


def test_search_year_out_of_range_low(client: TestClient):
    resp = client.get("/api/v1/search?year=1900")
    assert resp.status_code == 422


def test_search_year_out_of_range_high(client: TestClient):
    resp = client.get("/api/v1/search?year=2200")
    assert resp.status_code == 422


def test_search_invalid_season(client: TestClient):
    resp = client.get("/api/v1/search?season=MONSOON")
    assert resp.status_code == 422


def test_search_invalid_language(client: TestClient):
    resp = client.get("/api/v1/search?language=klingon")
    assert resp.status_code == 422


# ── Health ────────────────────────────────────────────────────────────────

@respx.mock
def test_health_all_providers(client: TestClient):
    # AniList health probe
    respx.post("https://graphql.anilist.co").mock(
        return_value=httpx.Response(200, json={"data": {"Media": {"id": 1}}})
    )
    # Jikan health probe
    respx.get("https://api.jikan.moe/v4/anime/1").mock(
        return_value=httpx.Response(200, json={"data": {"mal_id": 1}})
    )
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    provider_names = [p["provider"] for p in body]
    assert "anilist" in provider_names
    assert "jikan" in provider_names
    for p in body:
        assert p["status"] in ("verified", "degraded", "unsupported", "untested")


@respx.mock
def test_health_anilist_degraded(client: TestClient):
    """Simulate AniList returning an error — health should degrade, not crash."""
    respx.post("https://graphql.anilist.co").mock(
        return_value=httpx.Response(500)
    )
    respx.get("https://api.jikan.moe/v4/anime/1").mock(
        return_value=httpx.Response(200, json={"data": {"mal_id": 1}})
    )
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    anilist_health = next(p for p in body if p["provider"] == "anilist")
    assert anilist_health["status"] in ("degraded", "untested")
