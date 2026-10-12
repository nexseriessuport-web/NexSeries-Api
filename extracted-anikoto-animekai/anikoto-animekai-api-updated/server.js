const express = require("express");
const path = require("path");

const app = express();
const PORT = Number(process.env.PORT || 3000);
const ANIKOTO_BASE = (process.env.ANIKOTO_API_BASE || "https://anikotoapi.site").replace(/\/+$/, "");
// Configure this only for an AnimeKai API deployment you are authorized to use.
// The historic public scraper implementations may be offline; this is not assumed live.
const ANIMEKAI_BASE = (process.env.ANIMEKAI_API_BASE || "").replace(/\/+$/, "");
const CACHE_TTL_MS = 60_000;
const cache = new Map();

app.disable("x-powered-by");
app.use(express.static(path.join(__dirname, "public")));

function cacheGet(key) {
  const item = cache.get(key);
  if (!item || Date.now() - item.time > CACHE_TTL_MS) {
    cache.delete(key);
    return undefined;
  }
  return item.data;
}
function cacheSet(key, data) {
  cache.set(key, { time: Date.now(), data });
}
function safeId(value) {
  return typeof value === "string" && /^[a-zA-Z0-9_-]{1,160}$/.test(value);
}
async function fetchJson(url, { timeoutMs = 10_000, retries = 2 } = {}) {
  const cached = cacheGet(url);
  if (cached !== undefined) return cached;

  let lastError;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetch(url, {
        headers: { Accept: "application/json", "User-Agent": "AnimeCatalogWrapper/1.1" },
        signal: AbortSignal.timeout(timeoutMs)
      });

      // Respect upstream throttling. Do not attempt to evade a 429 or access controls.
      if (response.status === 429) {
        const error = new Error("Upstream rate limit reached. Try again later.");
        error.status = 429;
        const retryAfter = response.headers.get("retry-after");
        error.retryAfter = retryAfter ? Math.min(60, Math.max(1, Number(retryAfter) || 5)) : 5;
        throw error;
      }

      if (!response.ok) {
        const error = new Error(`Upstream returned HTTP ${response.status}`);
        error.status = response.status;
        throw error;
      }
      const data = await response.json();
      cacheSet(url, data);
      return data;
    } catch (error) {
      lastError = error;
      if (error.status === 429 || (error.status && error.status < 500)) throw error;
      if (attempt < retries) {
        const delay = Math.min(4000, 400 * (2 ** attempt));
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }
  throw lastError || new Error("Upstream request failed");
}
function asyncRoute(handler) {
  return (req, res, next) => Promise.resolve(handler(req, res, next)).catch(next);
}
function queryUrl(base, route, params = {}) {
  const url = new URL(route, base + "/");
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  }
  return url.toString();
}

app.get("/api/health", (_req, res) => {
  res.json({
    ok: true,
    service: "multi-provider anime catalog wrapper",
    providers: {
      anikoto: { configured: Boolean(ANIKOTO_BASE), base: ANIKOTO_BASE },
      animekai: { configured: Boolean(ANIMEKAI_BASE), base: ANIMEKAI_BASE || null }
    }
  });
});

// Anikoto catalog routes
app.get("/api/anikoto/recent", asyncRoute(async (req, res) => {
  const page = Math.max(1, Math.min(1000, Number.parseInt(req.query.page || "1", 10) || 1));
  const perPage = Math.max(1, Math.min(50, Number.parseInt(req.query.per_page || "20", 10) || 20));
  res.json(await fetchJson(queryUrl(ANIKOTO_BASE, "recent-anime", { page, per_page: perPage })));
}));

app.get("/api/anikoto/series/:id", asyncRoute(async (req, res) => {
  if (!safeId(req.params.id)) return res.status(400).json({ error: "Invalid series ID." });
  res.json(await fetchJson(queryUrl(ANIKOTO_BASE, `series/${encodeURIComponent(req.params.id)}`)));
}));

// AnimeKai API adapter. Set ANIMEKAI_API_BASE to the base URL of a working API instance.
// These route shapes match commonly documented community wrappers; actual availability varies.
function animeKaiRequired(_req, res, next) {
  if (!ANIMEKAI_BASE) {
    return res.status(503).json({
      error: "AnimeKai provider is not configured.",
      message: "Set ANIMEKAI_API_BASE to a working API endpoint you are authorized to use. Historical community instances may be offline."
    });
  }
  next();
}
app.get("/api/animekai/home", animeKaiRequired, asyncRoute(async (_req, res) => {
  res.json(await fetchJson(queryUrl(ANIMEKAI_BASE, "api/home")));
}));
app.get("/api/animekai/search", animeKaiRequired, asyncRoute(async (req, res) => {
  const keyword = String(req.query.keyword || "").trim().slice(0, 120);
  if (!keyword) return res.status(400).json({ error: "keyword is required." });
  res.json(await fetchJson(queryUrl(ANIMEKAI_BASE, "api/search", { keyword })));
}));
app.get("/api/animekai/anime/:slug", animeKaiRequired, asyncRoute(async (req, res) => {
  if (!safeId(req.params.slug)) return res.status(400).json({ error: "Invalid anime slug." });
  res.json(await fetchJson(queryUrl(ANIMEKAI_BASE, `api/anime/${encodeURIComponent(req.params.slug)}`)));
}));
app.get("/api/animekai/episodes/:animeId", animeKaiRequired, asyncRoute(async (req, res) => {
  if (!safeId(req.params.animeId)) return res.status(400).json({ error: "Invalid anime ID." });
  res.json(await fetchJson(queryUrl(ANIMEKAI_BASE, `api/episodes/${encodeURIComponent(req.params.animeId)}`)));
}));
app.get("/api/animekai/servers/:episodeToken", animeKaiRequired, asyncRoute(async (req, res) => {
  if (!safeId(req.params.episodeToken)) return res.status(400).json({ error: "Invalid episode token." });
  res.json(await fetchJson(queryUrl(ANIMEKAI_BASE, `api/servers/${encodeURIComponent(req.params.episodeToken)}`)));
}));

// Uses an embed URL returned by the provider; does not scrape direct media URLs or bypass player controls.
app.get("/api/player/embed", (req, res) => {
  const raw = String(req.query.url || "");
  let parsed;
  try { parsed = new URL(raw); } catch { return res.status(400).json({ error: "A valid embed URL is required." }); }
  const allowedHosts = (process.env.ALLOWED_EMBED_HOSTS || "")
    .split(",").map(x => x.trim().toLowerCase()).filter(Boolean);
  if (parsed.protocol !== "https:" || !allowedHosts.includes(parsed.hostname.toLowerCase())) {
    return res.status(400).json({
      error: "Embed host is not allowlisted.",
      message: "Set ALLOWED_EMBED_HOSTS to the exact trusted video-provider hostnames."
    });
  }
  res.json({ embedUrl: parsed.toString() });
});

app.get("/api/routes", (_req, res) => {
  res.json({
    routes: [
      "GET /api/health",
      "GET /api/anikoto/recent?page=1&per_page=20",
      "GET /api/anikoto/series/:id",
      "GET /api/animekai/home",
      "GET /api/animekai/search?keyword=naruto",
      "GET /api/animekai/anime/:slug",
      "GET /api/animekai/episodes/:animeId",
      "GET /api/animekai/servers/:episodeToken",
      "GET /api/player/embed?url=<provider-embed-url>"
    ]
  });
});

app.get("*", (req, res, next) => {
  if (req.path.startsWith("/api/")) return res.status(404).json({ error: "API route not found." });
  res.sendFile(path.join(__dirname, "public", "index.html"), err => err && next(err));
});

app.use((err, _req, res, _next) => {
  if (err.status === 429) {
    if (err.retryAfter) res.set("Retry-After", String(err.retryAfter));
    return res.status(429).json({ error: err.message, retryAfterSeconds: err.retryAfter || 5 });
  }
  const status = Number.isInteger(err.status) ? err.status : 502;
  res.status(status).json({ error: "Request failed", message: err.message || "Upstream request failed." });
});

app.listen(PORT, "0.0.0.0", () => console.log(`Anime API wrapper listening on ${PORT}`));
