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
      return res.status(503).json({
        error: "provider_not_configured",
        provider: provider.id,
        message: "Configure a verified upstream API base URL and search path before using this route."
      });
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
