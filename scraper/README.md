# Nex Series API Scraper (FastAPI)

Standalone Python scraper service for the NexSeries-Api repository.

## Run locally
```bash
python -m pip install -r requirements.txt
uvicorn nex_series_api:app --host 0.0.0.0 --port 8000
```

On Railway, set the service root directory to `/scraper` and start command to:
```bash
uvicorn nex_series_api:app --host 0.0.0.0 --port $PORT
```

Routes: `/`, `/api/health`, `/api/search`, `/api/upcoming`, `/api/top-airing`, `/api/most-popular`, `/api/movies`, `/api/schedule`, `/api/genres`, `/api/genre/{name}`, `/api/anime/details`, `/api/episodes`, `/api/servers`, `/api/stream`, and `/api/watchlist`.

Provider pages can change their HTML at any time, so selectors and stream availability need real-world verification. AniList endpoints return metadata, not episodes or media streams. This service uses ordinary HTTP requests and does not evade anti-bot protections, DRM, ad systems, or access controls. The watchlist uses local SQLite storage; for persistence across Railway redeploys, attach a persistent volume and set `DB_FILE` to a path on that volume.
