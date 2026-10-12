import { Router } from "express";

const SAFE_PROVIDER_ID = /^[a-z0-9-]+$/i;
const validId = value => typeof value === "string" && value.trim().length > 0 && value.length <= 300;

function getProvider(providers, rawId) {
  const id = String(rawId || "");
  return SAFE_PROVIDER_ID.test(id) ? providers[id.toLowerCase()] : undefined;
}

function sendProviderError(res, provider, error) {
  if (error?.code === "PROVIDER_NOT_CONFIGURED") {
    return res.status(503).json({
      error: "operation_not_configured",
      provider: provider.id,
      message: "This provider operation is not configured. Search metadata cannot supply episode records or video."
    });
  }
  const timeout = error?.code === "UPSTREAM_TIMEOUT";
  return res.status(timeout ? 504 : 502).json({
    error: timeout ? "upstream_timeout" : "upstream_error",
    provider: provider.id,
    message: "The upstream provider request failed."
  });
}

export function createProviderRouter(providers) {
  const router = Router();

  router.get("/:provider/search", async (req, res) => {
    const provider = getProvider(providers, req.params.provider);
    if (!provider) return res.status(404).json({ error: "unknown_provider", message: "Provider is not supported." });
    const q = typeof req.query.q === "string" ? req.query.q.trim() : "";
    if (!q || q.length > 160) return res.status(400).json({ error: "invalid_query", message: "Provide q (1–160 characters)." });

    if (!provider.isConfigured()) {
      try {
        const upstream = await fetch("https://graphql.anilist.co", {
          method: "POST",
          headers: { "content-type": "application/json", accept: "application/json" },
          body: JSON.stringify({
            query: "query ($search: String) { Page(page: 1, perPage: 20) { media(search: $search, type: ANIME, sort: SEARCH_MATCH) { id title { romaji english native } description(asHtml: false) episodes status format seasonYear coverImage { large } siteUrl } } }",
            variables: { search: q }
          }),
          signal: AbortSignal.timeout(10000)
        });
        if (!upstream.ok) return res.status(502).json({ error: "catalog_upstream_error", provider: provider.id, message: "Metadata service is temporarily unavailable." });
        const payload = await upstream.json();
        return res.json({
          provider: provider.id, query: q, configured: false,
          source: "AniList metadata fallback", streamsAvailable: false,
          data: payload?.data?.Page?.media ?? [],
          note: "Metadata only. Configure provider episode and stream operations for playback."
        });
      } catch {
        return res.status(502).json({ error: "catalog_unavailable", provider: provider.id, message: "Could not reach metadata service. Try again shortly." });
      }
    }

    try {
      return res.json({
        provider: provider.id, query: q, configured: true,
        supportedOperations: provider.supportedOperations,
        data: await provider.search(q)
      });
    } catch (error) {
      return sendProviderError(res, provider, error);
    }
  });

  router.get("/:provider/episodes", async (req, res) => {
    const provider = getProvider(providers, req.params.provider);
    if (!provider) return res.status(404).json({ error: "unknown_provider", message: "Provider is not supported." });
    const animeId = typeof req.query.animeId === "string" ? req.query.animeId.trim() : "";
    if (!validId(animeId)) return res.status(400).json({ error: "invalid_anime_id", message: "Provide animeId (1–300 characters)." });
    try {
      return res.json({ provider: provider.id, animeId, data: await provider.episodes(animeId) });
    } catch (error) {
      return sendProviderError(res, provider, error);
    }
  });

  router.get("/:provider/stream", async (req, res) => {
    const provider = getProvider(providers, req.params.provider);
    if (!provider) return res.status(404).json({ error: "unknown_provider", message: "Provider is not supported." });
    const episodeId = typeof req.query.episodeId === "string" ? req.query.episodeId.trim() : "";
    if (!validId(episodeId)) return res.status(400).json({ error: "invalid_episode_id", message: "Provide episodeId (1–300 characters)." });
    try {
      return res.json({ provider: provider.id, episodeId, data: await provider.stream(episodeId) });
    } catch (error) {
      return sendProviderError(res, provider, error);
    }
  });

  return router;
}
