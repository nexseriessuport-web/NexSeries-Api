# NexSeries API Workspace

Node.js/Express anime metadata and configurable provider-adapter workspace.

## Routes

- `GET /` and `GET /watch` — search/watch frontend
- `GET /dashboard`, `/api-dashboard`, `/control-room` — API dashboard
- `GET /health` — server health
- `GET /api` — route overview
- `GET /api/providers` — provider configuration and supported operations
- `GET /api/catalog/search?q=title` — AniList metadata search only
- `GET /api/:provider/search?q=title` — provider search (metadata fallback when unconfigured)
- `GET /api/:provider/episodes?animeId=id` — provider episode list
- `GET /api/:provider/stream?episodeId=id` — provider playback-source lookup

## Important limitations

AniList supplies anime metadata and episode counts, not episode-by-episode records or streaming video URLs. The frontend no longer fabricates episode options from an episode count. Episode lists and playback are shown only when configured provider operations return real data.

Anikoto and AnimeKai are not automatically connected to a verified upstream API in this repository. HTTP 200 from search does not prove that episode lookup or playback works. Use only documented, authorized provider endpoints and test an actual browser-compatible media URL before claiming playback works.

## Configure documented provider endpoints

Set these in the hosting provider's environment settings (do not commit credentials or cookies):

```env
ANIKOTO_API_BASE=https://documented-api-host.example
ANIKOTO_SEARCH_PATH=/search
ANIKOTO_EPISODES_PATH=/anime/{animeId}/episodes
ANIKOTO_STREAM_PATH=/episode/{episodeId}/stream

ANIMEKAI_API_BASE=https://documented-api-host.example
ANIMEKAI_SEARCH_PATH=/search
ANIMEKAI_EPISODES_PATH=/anime/{animeId}/episodes
ANIMEKAI_STREAM_PATH=/episode/{episodeId}/stream
```

These paths are examples of the adapter's configurable shape, not real provider endpoints. Replace them only with paths from a legitimate API's documentation. Search automatically receives a `q` query parameter. Episode and stream path templates can use `{animeId}` and `{episodeId}`; IDs are URL-encoded before insertion. Each upstream operation must return JSON. The stream response should contain a direct HTTP(S) media URL under a common field such as `url`, `file`, `src`, or `streamUrl`.

Provider search, episode list, and stream lookup are independent settings. `/api/providers` reports which operations are configured. An unconfigured operation returns HTTP 503 with `operation_not_configured` instead of fabricating results.

## Run and test

Requires Node.js 20 or newer.

```bash
npm install
npm test
npm start
```

Tests should stub upstream network calls so they do not depend on third-party availability.

## Deployment verification

After deploying, check `/health`, `/api/providers`, provider search, episode lookup, and stream lookup. A healthy server is not proof of playback. Test with a real authorized media URL in a browser.

This project does not bypass DRM, ads, access controls, or anti-bot protections.
