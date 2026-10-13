"""Shared pytest fixtures."""
from __future__ import annotations

import pytest
import respx
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.providers import registry


@pytest.fixture(autouse=True)
def reset_registry():
    """Re-initialise the registry before every test."""
    registry.init_registry()
    yield


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


# ── Canonical AniList fixture ─────────────────────────────────────────────

ANILIST_SEARCH_FIXTURE = {
    "data": {
        "Page": {
            "pageInfo": {"total": 1, "hasNextPage": False},
            "media": [
                {
                    "id": 1,
                    "idMal": 1,
                    "title": {
                        "romaji": "Cowboy Bebop",
                        "english": "Cowboy Bebop",
                        "native": "カウボーイビバップ",
                        "synonyms": [],
                    },
                    "coverImage": {
                        "large": "https://example.com/large.jpg",
                        "medium": "https://example.com/med.jpg",
                        "color": "#1a1a1a",
                    },
                    "bannerImage": None,
                    "description": "A jazz-infused space western.",
                    "genres": ["Action", "Adventure", "Drama"],
                    "tags": [{"name": "Space"}],
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
            ],
        }
    }
}

ANILIST_DETAIL_FIXTURE = {
    "data": {
        "Media": {
            **ANILIST_SEARCH_FIXTURE["data"]["Page"]["media"][0],
            "recommendations": {"nodes": []},
            "relations": {"edges": []},
        }
    }
}

JIKAN_SEARCH_FIXTURE = {
    "data": [
        {
            "mal_id": 1,
            "title": "Cowboy Bebop",
            "titles": [
                {"type": "Default", "title": "Cowboy Bebop"},
                {"type": "English", "title": "Cowboy Bebop"},
                {"type": "Japanese", "title": "カウボーイビバップ"},
            ],
            "images": {
                "jpg": {
                    "image_url": "https://example.com/med.jpg",
                    "large_image_url": "https://example.com/large.jpg",
                }
            },
            "synopsis": "A jazz-infused space western.",
            "genres": [{"name": "Action"}],
            "themes": [],
            "studios": [{"name": "Sunrise"}],
            "season": "spring",
            "year": 1998,
            "episodes": 26,
            "status": "Finished Airing",
            "type": "TV",
            "score": 8.6,
            "popularity": 50,
        }
    ],
    "pagination": {"has_next_page": False, "items": {"total": 1}},
}
