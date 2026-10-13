"""
Streaming provider stub — shared skeleton for Anikito, Miruro, AniVault, YumeZone.

STATUS: UNTESTED for all four candidates.

Verification checklist before enabling any provider:
  1. Confirm the site publishes a public API or documented embed interface.
  2. Confirm terms of service permit automated access.
  3. Run the contract test suite (tests/contract/test_streaming_contract.py).
  4. Change the provider's status to VERIFIED or DEGRADED based on results.
  5. Set PROVIDER_<NAME>_ENABLED=true in .env.

Until those steps complete, every provider here returns:
  - status: UNTESTED
  - health: UNTESTED
  - All endpoints raise NotImplementedError

This file exists so the import chain is complete and the registry can report
unverified providers without silently omitting them.
"""
from __future__ import annotations

import time
from typing import Optional

from app.providers.base import BaseProvider
from app.schemas.anime import (
    AnimeDetail,
    PaginatedResult,
    ProviderHealth,
    ProviderStatus,
    SearchFilters,
)


class _UntestedStreamingProvider(BaseProvider):
    """Base for unverified streaming providers. Subclasses only set name/base_url."""

    status = ProviderStatus.UNTESTED
    capabilities: list[str] = []

    async def search(self, filters: SearchFilters) -> PaginatedResult:
        raise NotImplementedError(f"{self.name} is UNTESTED — enable after contract tests pass")

    async def get_anime(self, provider_id: str) -> Optional[AnimeDetail]:
        raise NotImplementedError(f"{self.name} is UNTESTED — enable after contract tests pass")

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            status=ProviderStatus.UNTESTED,
            latency_ms=None,
            capabilities=[],
            notes=(
                f"{self.name} has not been verified. "
                "Run contract tests and set PROVIDER_{NAME}_ENABLED=true to activate."
            ),
        )


class AnikitoPROVIDER(_UntestedStreamingProvider):
    name = "anikito"
    base_url = "https://anikito.net"    # subject to change — verify before use
    # Anikito appears to be a public-facing streaming site with no published API.
    # Direct scraping may violate ToS. Treat as UNTESTED until confirmed.


class MiruroPROVIDER(_UntestedStreamingProvider):
    name = "miruro"
    base_url = "https://www.miruro.tv"  # subject to change — verify before use
    # Miruro is a community player. Check if it exposes a documented embed/API.


class AniVaultPROVIDER(_UntestedStreamingProvider):
    name = "anivault"
    base_url = "https://anivault.net"   # verify current domain before use
    # AniVault Scraper API was broken as of NexSeries history — re-verify.


class YumeZonePROVIDER(_UntestedStreamingProvider):
    name = "yumezone"
    base_url = "https://yumezone.net"   # verify current domain before use
    # No documented public API found. Treat as UNTESTED.
