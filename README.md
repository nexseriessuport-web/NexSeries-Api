# NexSeries API Workspace

A small Node.js API scaffold with health checks, provider discovery, configurable provider adapters, and regression tests.

## Routes

- `GET /` — service summary
- `GET /health` — health check
- `GET /api` — route overview
- `GET /api/providers` — adapter configuration status
- `GET /api/anikoto/search?q=title` — search adapter
- `GET /api/animekai/search?q=title` — search adapter

The provider search routes intentionally return `503 provider_not_configured` until a verified upstream API base URL and path are configured. This avoids inventing undocumented endpoints or claiming an integration works when it has not been tested.

## Run locally

Requires Node.js 20 or newer.

```bash
npm install
cp .env.example .env
npm run dev
```

Open `http://localhost:3000/health`.

## Test

```bash
npm test
```

## Configure a provider

For each provider, set its API base URL and a documented search path, for example:

```env
ANIKOTO_API_BASE=https://documented-api-host.example
ANIKOTO_SEARCH_PATH=/documented/search
```

Replace the example with a real, authorized endpoint and path from provider documentation. The adapter adds the search term as a `q` query parameter. If the provider uses another parameter name or a different response contract, adapt `src/providers/base-provider.js` accordingly.

## Deploy to Railway

1. Push this folder to a GitHub repository you control.
2. Create a Railway project and deploy that repository.
3. Set any verified provider environment variables in Railway.
4. Confirm the service health check passes at `/health`.

Do not put credentials, cookies, private tokens, or `.env` files into Git.
This scaffold does not bypass ads, sandbox controls, access restrictions, or anti-bot systems.
