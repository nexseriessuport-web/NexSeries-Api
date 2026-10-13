"""Unit tests for schema validation and provider mapping helpers."""
from __future__ import annotations

import pytest

from app.schemas.anime import (
    AnimeBase,
    AnimeDetail,
    Episode,
    Language,
    MediaType,
    PaginatedResult,
    PlaybackStatus,
    ProviderStatus,
    Season,
    StreamingServer,
    Title,
)
from app.providers.anilist import _map_media
from app.providers.jikan import _map_anime


# ── Schema construction ───────────────────────────────────────────────────

def test_title_all_optional():
    t = Title()
    assert t.romaji is None
    assert t.english is None
    assert t.native is None
    assert t.synonyms == []


def test_streaming_server_defaults():
    s = StreamingServer(
        provider_id="p1",
        server_label="sub",
        url="https://example.com/stream.m3u8",
    )
    assert s.media_type == MediaType.UNKNOWN
    assert s.language == Language.UNKNOWN
    assert s.playback_status == PlaybackStatus.UNKNOWN
    assert s.drm_required is False
    assert s.subtitles_available is False


def test_episode_defaults():
    e = Episode(provider_id="ep1", episode_number=1)
    assert e.servers == []
    assert e.languages_available == []


def test_paginated_result_defaults():
    r = PaginatedResult()
    assert r.page == 1
    assert r.per_page == 20
    assert r.results == []
    assert r.has_next_page is False


def test_anime_base_requires_provider_id_and_title():
    a = AnimeBase(
        provider_id="1",
        title=Title(romaji="Test"),
    )
    assert a.provider_id == "1"
    assert a.title.romaji == "Test"
    assert a.canonical_id is None
    assert a.languages_available == []


# ── AniList mapper ────────────────────────────────────────────────────────

def _raw_anilist():
    return {
        "id": 1,
        "idMal": 1,
        "title": {
            "romaji": "Cowboy Bebop",
            "english": "Cowboy Bebop",
            "native": "カウボーイビバップ",
            "synonyms": ["CB"],
        },
        "coverImage": {"large": "https://ex.com/l.jpg", "medium": "https://ex.com/m.jpg", "color": "#fff"},
        "bannerImage": None,
        "description": "Space western.",
        "genres": ["Action", "Drama"],
        "tags": [{"name": "Space"}, {"name": "Music"}],
        "season": "SPRING",
        "seasonYear": 1998,
        "episodes": 26,
        "duration": 24,
        "status": "FINISHED",
        "format": "TV",
        "averageScore": 86,
        "popularity": 230000,
        "studios": {"nodes": [{"name": "Sunrise"}]},
        "nextAiringEpisode": None,
        "trailer": None,
    }


def test_anilist_map_basic():
    anime = _map_media(_raw_anilist())
    assert anime.provider_id == "1"
    assert anime.canonical_id == 1
    assert anime.mal_id == 1
    assert anime.title.romaji == "Cowboy Bebop"
    assert anime.title.native == "カウボーイビバップ"
    assert "CB" in anime.title.synonyms
    assert anime.season == Season.SPRING
    assert anime.season_year == 1998
    assert anime.score == pytest.approx(8.6)
    assert "Sunrise" in anime.studios
    assert anime.source_provider == "anilist"


def test_anilist_map_unknown_season():
    raw = _raw_anilist()
    raw["season"] = "MONKEYSEASON"
    anime = _map_media(raw)
    assert anime.season is None


def test_anilist_map_no_score():
    raw = _raw_anilist()
    raw["averageScore"] = None
    anime = _map_media(raw)
    assert anime.score is None


def test_anilist_map_empty_genres():
    raw = _raw_anilist()
    raw["genres"] = None
    anime = _map_media(raw)
    assert anime.genres == []


def test_anilist_youtube_trailer():
    raw = _raw_anilist()
    raw["trailer"] = {"site": "youtube", "id": "abc123"}
    # _map_media returns AnimeBase not detail, so we just verify no crash
    anime = _map_media(raw)
    assert anime.source_provider == "anilist"


# ── Jikan mapper ──────────────────────────────────────────────────────────

def _raw_jikan():
    return {
        "mal_id": 1,
        "title": "Cowboy Bebop",
        "titles": [
            {"type": "Default", "title": "Cowboy Bebop"},
            {"type": "English", "title": "Cowboy Bebop"},
            {"type": "Japanese", "title": "カウボーイビバップ"},
            {"type": "Synonym", "title": "CB"},
        ],
        "images": {
            "jpg": {
                "image_url": "https://ex.com/m.jpg",
                "large_image_url": "https://ex.com/l.jpg",
            }
        },
        "synopsis": "Space western.",
        "genres": [{"name": "Action"}],
        "themes": [{"name": "Music"}],
        "studios": [{"name": "Sunrise"}],
        "season": "spring",
        "year": 1998,
        "episodes": 26,
        "status": "Finished Airing",
        "type": "TV",
        "score": 8.6,
        "popularity": 50,
    }


def test_jikan_map_basic():
    anime = _map_anime(_raw_jikan())
    assert anime.provider_id == "1"
    assert anime.mal_id == 1
    assert anime.title.romaji == "Cowboy Bebop"
    assert anime.title.english == "Cowboy Bebop"
    assert anime.title.native == "カウボーイビバップ"
    assert "CB" in anime.title.synonyms
    assert anime.season == Season.SPRING
    assert anime.score == pytest.approx(8.6)
    assert anime.source_provider == "jikan"


def test_jikan_map_no_score():
    raw = _raw_jikan()
    raw["score"] = None
    anime = _map_anime(raw)
    assert anime.score is None


def test_jikan_invalid_season():
    raw = _raw_jikan()
    raw["season"] = "monsoon"
    anime = _map_anime(raw)
    assert anime.season is None


# ── Provider status enum ──────────────────────────────────────────────────

def test_provider_status_values():
    assert ProviderStatus.VERIFIED == "verified"
    assert ProviderStatus.UNTESTED == "untested"
