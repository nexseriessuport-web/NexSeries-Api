import { Router } from "express";

const SAFE_PROVIDER_ID = /^[a-z0-9-]+$/i;

export function createProviderRouter(providers) {
  const router = Router();

  router.get("/:provider/search", async (req, res) => {
    const providerId = String(req.params.provider || "");
    const provider = SAFE_PROVIDER_ID.test(providerId) ? providers[providerId.toLowerCase()] : undefined;
    if (!provider) {
      return res.status(404).json({ error: "unknown_provider", message: "Provider is not supported." });
    }

    const q = typeof req.query.q === "string" ? req.query.q.trim() : "";
    if (!q) {
      return res.status(400).json({ error: "invalid_query", message: "Provide a non-empty q query parameter." });
    }
    if (q.length > 160) {
      return res.status(400).json({ error: "invalid_query", message: "Search query must be 160 characters or fewer." });
    }
    if (!provider.isConfigured()) {
      // Keep provider routes useful without inventing or scraping a stream source.
      // Return metadata from the catalog and explicitly mark that no provider stream was queried.
      try {
        const upstream = await fetch("https://graphql.anilist.co", {
          method: "POST", headers: { "content-type": "application/json", "accept": "application/json" },
          body: JSON.stringify({ query: "query ($search: String) { Page(page: 1, perPage: 20) { media(search: $search, type: ANIME, sort: SEARCH_MATCH) { id title { romaji english native } description(asHtml: false) episodes status format seasonYear coverImage { large } siteUrl } } }", variables: { search: q } }),
          signal: AbortSignal.timeout(10000)
        });
        if (!upstream.ok) return res.status(502).json({ error: "catalog_upstream_error", provider: provider.id, message: "Metadata service is temporarily unavailable." });
        const payload = await upstream.json();
        return res.json({ provider: provider.id, query: q, configured: false, source: "AniList metadata fallback", streamsAvailable: false, data: payload?.data?.Page?.media ?? [], note: "This fallback searches anime metadata only. Configure a legitimate provider API for stream results." });
      } catch {
        return res.status(502).json({ error: "catalog_unavailable", provider: provider.id, message: "Could not reach metadata service. Try again shortly." });
      }
    }

    try {
      const data = await provider.search(q);
      return res.json({ provider: provider.id, query: q, data });
    } catch (error) {
      const status = error?.code === "UPSTREAM_TIMEOUT" ? 504 : 502;
      return res.status(status).json({
        error: status === 504 ? "upstream_timeout" : "upstream_error",
        provider: provider.id,
        message: "The upstream provider request failed."
      });
    }
  });

  return router;
}
