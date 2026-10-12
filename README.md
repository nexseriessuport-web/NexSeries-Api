# NexSeries API

Node.js/Express API scaffold for anime provider adapters.

## Endpoints
- `GET /` — service info
- `GET /health` — health check
- `GET /api` — API overview
- `GET /api/providers` — configured providers
- `GET /api/anikoto/search?q=title` — Anikoto search adapter
- `GET /api/animekai/search?q=title` — AnimeKai search adapter

Provider upstream URLs and paths must be configured through environment variables. The adapters return a clear unavailable response until valid endpoints are configured; this repository does not claim working upstream playback until verified.

## Local development
1. Install Node.js 20 or newer.
2. Run `npm install`.
3. Copy `.env.example` to `.env` and configure provider endpoints.
4. Run `npm start`.
5. Run tests with `npm test`.

## Deploy
A `Dockerfile` and `railway.toml` are included for deployment configuration.
