# Nex Anime API Wrapper

Node.js + Express wrapper with separate Anikoto and AnimeKai route namespaces.

## Run
Requires Node.js 18+.

```sh
npm install
npm start
```

Open `http://localhost:3000`. API route index: `/api/routes`.

## Routes
- `GET /api/health`
- `GET /api/anikoto/recent?page=1&per_page=20`
- `GET /api/anikoto/series/:id`
- `GET /api/animekai/home`
- `GET /api/animekai/search?keyword=naruto`
- `GET /api/animekai/anime/:slug`
- `GET /api/animekai/episodes/:animeId`
- `GET /api/animekai/servers/:episodeToken`
- `GET /api/player/embed?url=<provider-embed-url>`

## Configure AnimeKai
Set `ANIMEKAI_API_BASE` to a live API instance you are authorized to use. Community AnimeKai API projects have reported shutdowns, so a historical endpoint is not assumed to work. This wrapper cannot make an unavailable upstream service live.

If using `/api/player/embed`, set `ALLOWED_EMBED_HOSTS` to exact trusted HTTPS hostnames. The app uses provider-supplied embed URLs; it does not extract direct video segments or evade anti-bot systems.

## Rate limits and resilience
Successful JSON responses are cached for 60 seconds. Transient upstream failures receive a small bounded retry with exponential delay. HTTP 429 responses are passed through with `Retry-After`; the wrapper does not rotate identities, defeat CAPTCHAs, spoof clients, or bypass provider throttles. Respect the upstream service's published limits and terms.

\n## Embedded playback and pop-up limits
The web UI includes an embed player that accepts only HTTPS URLs whose exact hostname is listed in `ALLOWED_EMBED_HOSTS`. The iframe sandbox blocks popups and top-level navigation while allowing scripts and presentation needed by many players. Some providers may require a different supported embed configuration. Cross-origin ads rendered inside a provider's own frame cannot be reliably removed by the wrapper; this change blocks pop-ups, not all ads. It does not bypass CAPTCHAs, anti-bot checks, or sandbox security restrictions.
