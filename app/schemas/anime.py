"""
Canonical response schemas.

Rules:
  - Every optional field is genuinely optional — providers must not fabricate values.
  - provider_id is always the raw ID from the originating provider.
  - canonical_id is the AniList MAL ID when available, else None.
  - Fields absent from a provider are omitted (None), never invented.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────

class ProviderStatus(str, Enum):
    VERIFIED = "verified"
    DEGRADED = "degraded"
    UNSUPPORTED = "unsupported"
    UNTESTED = "untested"


class MediaType(str, Enum):
    HLS = "hls"
    DASH = "dash"
    MP4 = "mp4"
    UNKNOWN = "unknown"


class PlaybackStatus(str, Enum):
    AVAILABLE = "available"
    EXPIRED = "expired"
    GEO_BLOCKED = "geo_blocked"
    UNSUPPORTED = "unsupported"
    ERROR = "error"
    UNKNOWN = "unknown"


class Language(str, Enum):
    SUB = "sub"
    DUB_EN = "dub_en"
    DUB_PT = "dub_pt"
    DUB_ES = "dub_es"
    DUB_FR = "dub_fr"
    DUB_DE = "dub_de"
    DUB_IT = "dub_it"
    DUB_JA = "dub_ja"
    MULTI = "multi"
    UNKNOWN = "unknown"


class Season(str, Enum):
    WINTER = "WINTER"
    SPRING = "SPRING"
    SUMMER = "SUMMER"
    FALL = "FALL"


# ── Building blocks ───────────────────────────────────────────────────────

class Title(BaseModel):
    romaji: Optional[str] = None
    english: Optional[str] = None
    native: Optional[str] = None
    synonyms: list[str] = Field(default_factory=list)


class CoverImage(BaseModel):
    large: Optional[str] = None
    medium: Optional[str] = None
    color: Optional[str] = None


class StreamingServer(BaseModel):
    provider_id: str
    server_label: str
    url: str
    media_type: MediaType = MediaType.UNKNOWN
    language: Language = Language.UNKNOWN
    subtitles_available: bool = False
    playback_status: PlaybackStatus = PlaybackStatus.UNKNOWN
    headers: dict[str, str] = Field(default_factory=dict)
    drm_required: bool = False
    notes: Optional[str] = None


class Episode(BaseModel):
    provider_id: str
    canonical_anime_id: Optional[int] = None
    episode_number: float
    title: Optional[str] = None
    thumbnail: Optional[str] = None
    duration_seconds: Optional[int] = None
    air_date: Optional[str] = None
    filler: Optional[bool] = None
    recap: Optional[bool] = None
    languages_available: list[Language] = Field(default_factory=list)
    servers: list[StreamingServer] = Field(default_factory=list)


class AnimeBase(BaseModel):
    provider_id: str
    canonical_id: Optional[int] = None          # AniList ID
    mal_id: Optional[int] = None
    title: Title
    cover_image: Optional[CoverImage] = None
    banner_image: Optional[str] = None
    description: Optional[str] = None
    genres: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    season: Optional[Season] = None
    season_year: Optional[int] = None
    episode_count: Optional[int] = None
    duration_minutes: Optional[int] = None
    status: Optional[str] = None               # RELEASING, FINISHED, etc.
    format: Optional[str] = None               # TV, MOVIE, OVA, ONA, etc.
    score: Optional[float] = None
    popularity: Optional[int] = None
    studios: list[str] = Field(default_factory=list)
    languages_available: list[Language] = Field(default_factory=list)
    subtitles_available: bool = False
    source_provider: str = "unknown"


class AnimeDetail(AnimeBase):
    episodes: list[Episode] = Field(default_factory=list)
    recommendations: list["AnimeBase"] = Field(default_factory=list)
    relations: list["AnimeBase"] = Field(default_factory=list)
    trailer_url: Optional[str] = None
    next_airing_episode: Optional[int] = None
    next_airing_at: Optional[str] = None


# ── API response wrappers ─────────────────────────────────────────────────

class PaginatedResult(BaseModel):
    page: int = 1
    per_page: int = 20
    total: Optional[int] = None
    has_next_page: bool = False
    results: list[AnimeBase] = Field(default_factory=list)


class ProviderHealth(BaseModel):
    provider: str
    status: ProviderStatus
    latency_ms: Optional[float] = None
    capabilities: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    provider: Optional[str] = None
    detail: Optional[str] = None


class ScheduleEntry(BaseModel):
    canonical_id: Optional[int] = None
    title: Title
    episode_number: int
    air_timestamp: int           # Unix UTC
    provider: str


class SearchFilters(BaseModel):
    query: Optional[str] = None
    genre: Optional[str] = None
    season: Optional[Season] = None
    year: Optional[int] = None
    format: Optional[str] = None
    status: Optional[str] = None
    language: Optional[Language] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=50)
