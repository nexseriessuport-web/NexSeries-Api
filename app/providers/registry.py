"""
Provider registry.

At startup, enabled providers are instantiated and stored here.
Routers call registry functions instead of importing providers directly.

Fallback order for metadata: AniList → Jikan
Streaming providers are queried independently.
"""
from __future__ import annotations

from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.base import BaseProvider
from app.providers.anilist import AniListProvider
from app.providers.jikan import JikanProvider
from app.providers.streaming_stub import (
    AnikitoPROVIDER,
    MiruroPROVIDER,
    AniVaultPROVIDER,
    YumeZonePROVIDER,
)
from app.schemas.anime import ProviderHealth

logger = get_logger(__name__)
_settings = get_settings()

# ── Singleton registry ────────────────────────────────────────────────────

_providers: dict[str, BaseProvider] = {}


def _build_registry() -> dict[str, BaseProvider]:
    registry: dict[str, BaseProvider] = {}

    if _settings.provider_anilist_enabled:
        registry["anilist"] = AniListProvider()
        logger.info("provider_loaded", name="anilist")

    if _settings.provider_jikan_enabled:
        registry["jikan"] = JikanProvider()
        logger.info("provider_loaded", name="jikan")

    if _settings.provider_anikito_enabled:
        registry["anikito"] = AnikitoPROVIDER()
        logger.warning("provider_loaded_untested", name="anikito")

    if _settings.provider_miruro_enabled:
        registry["miruro"] = MiruroPROVIDER()
        logger.warning("provider_loaded_untested", name="miruro")

    if _settings.provider_anivault_enabled:
        registry["anivault"] = AniVaultPROVIDER()
        logger.warning("provider_loaded_untested", name="anivault")

    if _settings.provider_yumezone_enabled:
        registry["yumezone"] = YumeZonePROVIDER()
        logger.warning("provider_loaded_untested", name="yumezone")

    return registry


def init_registry() -> None:
    global _providers
    _providers = _build_registry()


def get_provider(name: str) -> Optional[BaseProvider]:
    return _providers.get(name)


def list_providers() -> list[BaseProvider]:
    return list(_providers.values())


def metadata_providers() -> list[BaseProvider]:
    """Ordered list of metadata-capable providers for fallback."""
    order = ["anilist", "jikan"]
    return [_providers[n] for n in order if n in _providers]


async def all_health() -> list[ProviderHealth]:
    results = []
    for provider in _providers.values():
        try:
            health = await provider.health_check()
        except Exception as exc:
            from app.schemas.anime import ProviderStatus
            health = ProviderHealth(
                provider=provider.name,
                status=ProviderStatus.DEGRADED,
                notes=f"Health check threw: {exc}",
            )
        results.append(health)
    return results
