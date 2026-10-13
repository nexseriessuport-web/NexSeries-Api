"""
Abstract base every provider adapter must implement.

Providers that don't support a capability should raise NotImplementedError
so the registry can fall back or mark the feature unsupported.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.schemas.anime import (
    AnimeBase,
    AnimeDetail,
    Episode,
    PaginatedResult,
    ProviderHealth,
    ProviderStatus,
    ScheduleEntry,
    SearchFilters,
)


class BaseProvider(ABC):
    # Subclasses must set these
    name: str = "unknown"
    base_url: str = ""
    status: ProviderStatus = ProviderStatus.UNTESTED
    capabilities: list[str] = []

    # ── Metadata endpoints ────────────────────────────────────────────

    @abstractmethod
    async def search(self, filters: SearchFilters) -> PaginatedResult:
        ...

    @abstractmethod
    async def get_anime(self, provider_id: str) -> Optional[AnimeDetail]:
        ...

    async def get_trending(self, page: int = 1, per_page: int = 20) -> PaginatedResult:
        raise NotImplementedError(f"{self.name} does not support trending")

    async def get_popular(self, page: int = 1, per_page: int = 20) -> PaginatedResult:
        raise NotImplementedError(f"{self.name} does not support popular")

    async def get_recent(self, page: int = 1, per_page: int = 20) -> PaginatedResult:
        raise NotImplementedError(f"{self.name} does not support recent releases")

    async def get_schedule(self) -> list[ScheduleEntry]:
        raise NotImplementedError(f"{self.name} does not support schedule")

    async def get_recommendations(self, provider_id: str) -> list[AnimeBase]:
        raise NotImplementedError(f"{self.name} does not support recommendations")

    async def get_episodes(self, provider_id: str) -> list[Episode]:
        raise NotImplementedError(f"{self.name} does not support episode lists")

    # ── Health ────────────────────────────────────────────────────────

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        ...
