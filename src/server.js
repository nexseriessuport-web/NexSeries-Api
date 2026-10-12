import express from "express";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import helmet from "helmet";
import { providers } from "./providers/index.js";
import { createProviderRouter } from "./routes/provider-router.js";

const app = express();
app.disable("x-powered-by");
app.use(helmet({ contentSecurityPolicy: false }));
app.use(express.json({ limit: "100kb" }));

app.get("/", async (_req, res, next) => {
  try {
    const html = await readFile(new URL("./public/watch.html", import.meta.url), "utf8");
    res.type("html").send(html);
  } catch (error) { next(error); }
});

app.get(["/dashboard", "/api-dashboard", "/control-room"], async (_req, res, next) => {
  try {
    const html = await readFile(new URL("./public/index.html", import.meta.url), "utf8");
    res.set("Cache-Control", "no-store").type("html").send(html);
  } catch (error) { next(error); }
});

app.get("/watch", async (_req, res, next) => {
  try {
    const html = await readFile(new URL("./public/watch.html", import.meta.url), "utf8");
    res.type("html").send(html);
  } catch (error) { next(error); }
});

app.get("/api/catalog/search", async (req, res) => {
  const q = typeof req.query.q === "string" ? req.query.q.trim() : "";
  if (!q || q.length > 160) return res.status(400).json({ error: "invalid_query", message: "Provide q (1–160 characters)." });
  try {
    const upstream = await fetch("https://graphql.anilist.co", {
      method: "POST", headers: { "content-type": "application/json", "accept": "application/json" },
      body: JSON.stringify({ query: "query ($search: String) { Page(page: 1, perPage: 20) { media(search: $search, type: ANIME, sort: SEARCH_MATCH) { id title { romaji english native } description(asHtml: false) episodes status format seasonYear coverImage { large } siteUrl } } }", variables: { search: q } }),
      signal: AbortSignal.timeout(10000)
    });
    if (!upstream.ok) return res.status(502).json({ error: "catalog_upstream_error", message: "Anime metadata service is temporarily unavailable." });
    const payload = await upstream.json();
    return res.json({ source: "AniList metadata (not video streams)", results: payload?.data?.Page?.media ?? [] });
  } catch (error) {
    return res.status(502).json({ error: "catalog_unavailable", message: "Could not reach anime metadata service. Try again shortly." });
  }
});

app.get("/health", (_req, res) => {
  res.status(200).json({ ok: true, service: "nexseries-api", timestamp: new Date().toISOString() });
});

app.get("/api", (_req, res) => {
  res.json({
    routes: [
      "GET /health",
      "GET /api/providers",
      "GET /api/catalog/search?q=title",
      "GET /api/:provider/search?q=title"
    ],
    note: "Catalog metadata search is available at /api/catalog/search?q=title. Provider-specific stream search requires a verified provider adapter; metadata is not a video stream."
  });
});

app.get("/api/providers", (_req, res) => {
  res.json({
    providers: Object.values(providers).map(p => ({
      id: p.id,
      configured: p.isConfigured(),
      supportedOperations: p.supportedOperations
    }))
  });
});

app.use("/api", createProviderRouter(providers));

app.use((req, res) => {
  res.status(404).json({ error: "not_found", message: `No route for ${req.method} ${req.path}` });
});

app.use((err, _req, res, _next) => {
  console.error("[api-error]", err?.message ?? err);
  res.status(500).json({ error: "internal_error", message: "An unexpected server error occurred." });
});

const port = Number(process.env.PORT || 3000);
if (process.env.NODE_ENV !== "test") {
  app.listen(port, "0.0.0.0", () => console.log(`NexSeries API listening on ${port}`));
}

export default app;
