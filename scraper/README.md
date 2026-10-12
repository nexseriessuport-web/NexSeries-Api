# Nex Series API Scraper

Fresh FastAPI service with a built-in mobile-friendly dashboard, Swagger API explorer, provider search, episode parsing, metadata lists, and a SQLite watchlist.

## Run locally
```bash
python -m pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```
Open `/` for the dashboard, `/docs` for interactive Swagger docs, and `/api/health` for health status.

## Railway
- Root directory: `/scraper`
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Healthcheck path: `/api/health`
- For persistent watchlist storage, attach a Railway volume mounted at `/data`. The app will use `/data/nex_series.db` when `/data` exists; otherwise it uses `nex_series.db` in the service directory.

## Routes
- `GET /` dashboard
- `GET /docs` interactive API explorer
- `GET /api/health`, `GET /api/providers`
- `GET /api/search?platform=animekai&q=Naruto`
- `GET /api/upcoming`, `/api/top-airing`, `/api/most-popular`, `/api/movies`
- `GET /api/schedule`, `/api/genres`, `/api/genre/{name}`
- `GET /api/anime/details?platform=...&url=...`
- `GET /api/episodes?platform=...&url=...`
- `GET /api/servers?platform=...&url=...`
- `GET /api/stream?platform=...&url=...`
- `GET /api/watchlist`, `POST /api/watchlist`, `DELETE /api/watchlist/{item_id}`

## Built-in providers
`animekai`, `anikoto`, `hianime`, and `anivault`. HTML layouts and provider availability can change. AniList is a metadata source, not a video host, and cannot provide playable episode URLs. The service returns empty results or a clear error when links are not found; it does not invent episodes or mirror servers.

Provider URL allowlisting is enabled to reduce server-side request forgery risk. Use only sources you are authorized to access. This service does not evade access controls, DRM, or anti-bot protections.
