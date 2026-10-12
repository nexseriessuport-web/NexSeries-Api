# NexSeries API Workspace

Node.js/Express anime metadata and provider-adapter workspace with health checks and regression tests.

## Routes

- `GET /` — anime search/watch frontend
- `GET /watch` — anime search/watch frontend
- `GET /dashboard`, `/api-dashboard`, `/control-room` — API dashboard
- `GET /health` — health check
- `GET /api` — route overview
- `GET /api/providers` — adapter configuration status
- `GET /api/catalog/search?q=title` — AniList anime metadata search
- `GET /api/anikoto/search?q=title` — configured adapter search, or explicitly marked metadata fallback
- `GET /api/animekai/search?q=title` — configured adapter search, or explicitly marked metadata fallback

## Provider behavior (important)

The Anikoto and AnimeKai adapters are **not automatically connected to real provider APIs**. Each requires a verified, authorized API base URL and search path in Railway environment variables. When an adapter is not configured, its search route falls back to AniList metadata and returns `configured: false` and `streamsAvailable: false`. Those results are anime catalog entries, not provider episode streams or playable video URLs.

Do not treat HTTP 200 as proof that a provider integration or video playback works. Validate response fields and test a real, authorized stream URL in a browser before claiming playback is functional.

## Run locally

Requires Node.js 20 or newer.

```bash
npm install
npm run dev
```

Open `http://localhost:3000/health`.

## Tests

```bash
npm test
```

Tests should stub upstream network calls so they remain repeatable and do not depend on a third-party service being available.

## Configure a provider

Only use a documented, authorized endpoint:

```env
ANIKOTO_API_BASE=https://documented-api-host.example
ANIKOTO_SEARCH_PATH=/documented/search
```

The adapter currently adds the query as a `q` parameter and expects JSON. If the official API documents another query parameter or response schema, update the adapter and add tests for that schema. Do not commit credentials, cookies, private tokens, or `.env` files.

## Deployment

Railway deploys from the configured GitHub branch. Check the deployment status, runtime logs, and live HTTP responses after each change. The health check only confirms that the server is running; it does not verify upstream provider connectivity or video playback.

This project does not bypass DRM, ads, sandbox controls, access restrictions, or anti-bot systems.
