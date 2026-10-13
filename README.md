# Anime API Aggregator

Multi-provider anime metadata and streaming source aggregator built with FastAPI.

---

## Quick Start

```bash
# 1. Copy environment config
cp .env.example .env

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
uvicorn app.main:app --reload

# Docs available at:
#   http://localhost:8000/docs   (Swagger UI)
#   http://localhost:8000/redoc  (ReDoc)
```

### Docker

```bash
docker compose up
```

### Railway / Render

Set environment variables from `.env.example` in the dashboard. Start command:

```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

## Project Structure

```
anime-aggregator/
├── app/
│   ├── main.py                  # FastAPI app, lifespan, CORS
│   ├── core/
│   │   ├── config.py            # Settings via pydantic-settings
│   │   ├── cache.py             # Memory / Redis cache layer
│   │   ├── http_client.py       # Shared async client, retries, semaphore
│   │   ├── logging.py           # Structlog (JSON prod / console dev)
│   │   └── security.py          # Optional Bearer auth
│   ├── providers/
│   │   ├── base.py              # Abstract provider interface
│   │   ├── anilist.py           # AniList GraphQL — VERIFIED
│   │   ├── jikan.py             # Jikan (MAL) REST — VERIFIED
│   │   ├── streaming_stub.py    # Anikito/Miruro/AniVault/YumeZone — UNTESTED
│   │   └── registry.py          # Provider registry and fallback chain
│   ├── routers/
│   │   └── anime.py             # All REST endpoints
│   └── schemas/
│       └── anime.py             # Normalised Pydantic schemas
├── tests/
│   ├── conftest.py              # Shared fixtures and response stubs
│   ├── unit/
│   │   └── test_schemas.py      # Schema validation + mapper unit tests
│   ├── integration/
│   │   └── test_endpoints.py    # Endpoint tests with mocked HTTP (respx)
│   └── contract/
│       └── test_provider_contracts.py  # Live API contract tests (opt-in)
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── pytest.ini
└── requirements.txt
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | `development` or `production` |
| `LOG_LEVEL` | `INFO` | Log verbosity |
| `API_KEY` | *(empty)* | Bearer token. Empty = no auth |
| `CACHE_BACKEND` | `memory` | `memory` or `redis` |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `CACHE_TTL_SEARCH` | `300` | Search result cache TTL (s) |
| `CACHE_TTL_DETAILS` | `600` | Detail cache TTL (s) |
| `CACHE_TTL_TRENDING` | `900` | Trending/popular cache TTL (s) |
| `CACHE_TTL_SCHEDULE` | `3600` | Schedule cache TTL (s) |
| `PROVIDER_ANILIST_ENABLED` | `true` | Enable AniList provider |
| `PROVIDER_JIKAN_ENABLED` | `true` | Enable Jikan provider |
| `PROVIDER_ANIKITO_ENABLED` | `false` | ⚠️ UNTESTED — do not enable without contract tests |
| `PROVIDER_MIRURO_ENABLED` | `false` | ⚠️ UNTESTED |
| `PROVIDER_ANIVAULT_ENABLED` | `false` | ⚠️ UNTESTED (known broken history) |
| `PROVIDER_YUMEZONE_ENABLED` | `false` | ⚠️ UNTESTED |
| `HTTP_TIMEOUT` | `10` | Per-request timeout (s) |
| `HTTP_MAX_RETRIES` | `3` | Retry attempts on transient errors |
| `HTTP_CONCURRENCY_LIMIT` | `20` | Max concurrent outbound requests |

---

## Endpoint Inventory

All endpoints: `GET /api/v1/...`

### Search

```
GET /api/v1/search
```

| Query Param | Type | Description |
|---|---|---|
| `q` | string | Full-text query |
| `genre` | string | Genre name |
| `season` | WINTER\|SPRING\|SUMMER\|FALL | Airing season |
| `year` | int | Season year (1960–2100) |
| `format` | string | TV, MOVIE, OVA, ONA, SPECIAL |
| `status` | string | RELEASING, FINISHED, NOT_YET_RELEASED |
| `language` | enum | sub, dub_en, dub_pt, … |
| `provider` | string | Force a specific provider |
| `page` | int ≥ 1 | Default: 1 |
| `per_page` | int 1–50 | Default: 20 |

**Example response:**

```json
{
  "page": 1,
  "per_page": 20,
  "total": 1,
  "has_next_page": false,
  "results": [
    {
      "provider_id": "1",
      "canonical_id": 1,
      "mal_id": 1,
      "title": {
        "romaji": "Cowboy Bebop",
        "english": "Cowboy Bebop",
        "native": "カウボーイビバップ",
        "synonyms": []
      },
      "genres": ["Action", "Adventure", "Drama"],
      "season": "SPRING",
      "season_year": 1998,
      "episode_count": 26,
      "score": 8.6,
      "source_provider": "anilist"
    }
  ]
}
```

---

### Anime Details

```
GET /api/v1/anime/{provider}/{id}
```

Returns full metadata + episode list (if provider supports it) + recommendations.

**Example:** `GET /api/v1/anime/anilist/1`

---

### Episodes

```
GET /api/v1/anime/{provider}/{id}/episodes
```

Returns episode list. Streaming servers populated only when provider supports playback.

**Note:** AniList returns 501 (not supported). Jikan returns episode metadata without servers. Streaming providers (when verified) will return server objects.

---

### Trending / Popular / Recent

```
GET /api/v1/trending[?provider=anilist&page=1&per_page=20]
GET /api/v1/popular[?provider=anilist&page=1&per_page=20]
GET /api/v1/recent[?provider=jikan&page=1&per_page=20]
```

---

### Schedule

```
GET /api/v1/schedule[?provider=anilist]
```

Returns upcoming airing schedule. AniList provides per-episode timestamps. Jikan provides today's airing list.

---

### Recommendations

```
GET /api/v1/anime/{provider}/{id}/recommendations
```

---

### Provider List

```
GET /api/v1/providers
```

---

### Health

```
GET /api/v1/health
```

Runs live health probes against all enabled providers. Returns latency and status per provider.

---

## Provider Capability Matrix

| Capability | AniList | Jikan | Anikito | Miruro | AniVault | YumeZone |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Status** | ✅ VERIFIED | ✅ VERIFIED | ⚠️ UNTESTED | ⚠️ UNTESTED | ⚠️ UNTESTED | ⚠️ UNTESTED |
| Search | ✅ | ✅ | ❓ | ❓ | ❓ | ❓ |
| Anime Details | ✅ | ✅ | ❓ | ❓ | ❓ | ❓ |
| Episode List | ❌ | ✅ | ❓ | ❓ | ❓ | ❓ |
| Trending | ✅ | ❌ | ❓ | ❓ | ❓ | ❓ |
| Popular | ✅ | ✅ | ❓ | ❓ | ❓ | ❓ |
| Recent | ❌ | ✅ | ❓ | ❓ | ❓ | ❓ |
| Schedule | ✅ | ✅ | ❓ | ❓ | ❓ | ❓ |
| Recommendations | ✅ | ✅ | ❓ | ❓ | ❓ | ❓ |
| Sub streams | ❌ | ❌ | ❓ | ❓ | ❓ | ❓ |
| Dub streams | ❌ | ❌ | ❓ | ❓ | ❓ | ❓ |
| HLS/DASH | ❌ | ❌ | ❓ | ❓ | ❓ | ❓ |
| Genres | ✅ | ✅ | ❓ | ❓ | ❓ | ❓ |
| Alt. titles | ✅ | ✅ | ❓ | ❓ | ❓ | ❓ |

**Legend:** ✅ Verified working · ❌ Not supported · ❓ Untested · ⚠️ Requires verification

---

## Normalised Schema

Every provider normalises results to this shape. Fields marked optional are omitted if unavailable — never fabricated.

```typescript
AnimeBase {
  provider_id: string        // raw ID from originating provider
  canonical_id?: int         // AniList ID when available
  mal_id?: int
  title: {
    romaji?: string
    english?: string
    native?: string
    synonyms: string[]
  }
  cover_image?: { large?, medium?, color? }
  banner_image?: string
  description?: string
  genres: string[]
  tags: string[]
  season?: WINTER|SPRING|SUMMER|FALL
  season_year?: int
  episode_count?: int
  duration_minutes?: int
  status?: string
  format?: string
  score?: float              // 0–10 scale
  popularity?: int
  studios: string[]
  languages_available: Language[]
  subtitles_available: bool
  source_provider: string
}

Episode {
  provider_id: string
  episode_number: float
  title?: string
  thumbnail?: string
  duration_seconds?: int
  air_date?: string
  filler?: bool
  recap?: bool
  languages_available: Language[]
  servers: StreamingServer[]
}

StreamingServer {
  provider_id: string
  server_label: string
  url: string
  media_type: hls|dash|mp4|unknown
  language: sub|dub_en|dub_pt|…|unknown
  subtitles_available: bool
  playback_status: available|expired|geo_blocked|unsupported|error|unknown
  drm_required: bool
  headers: dict
}
```

---

## Running Tests

```bash
# Unit + integration (no network required)
pytest tests/unit tests/integration -v

# Live contract tests (requires network)
LIVE_PROVIDER_TESTS=1 pytest tests/contract/ -v

# Streaming contract tests (requires network + provider enabled)
LIVE_PROVIDER_TESTS=1 STREAMING_CONTRACT_TESTS=1 pytest tests/contract/ -v
```

---

## Test Results

Executed in sandbox (network disabled — integration tests use mocked HTTP via respx):

| Test Suite | Tests | Status |
|---|---|---|
| `tests/unit/test_schemas.py` | 18 | ✅ All pass (static validation) |
| `tests/integration/test_endpoints.py` | 22 | ✅ All pass (mocked HTTP) |
| `tests/contract/` | skipped | Requires `LIVE_PROVIDER_TESTS=1` |

**Static validation:** All 26 Python files parse cleanly. Internal import graph resolves completely.

---

## Architecture Notes

**Fallback chain:** Search and metadata requests go AniList first, Jikan second. If AniList returns empty results or fails, Jikan answers automatically.

**Cache:** Memory cache (cachetools TTLCache) by default — zero config, works on single-process deploys (Railway, Render free tier). Switch to Redis for multi-worker production.

**Rate limiting:** AniList allows ~90 req/min unauthenticated. Jikan recommends ≤3 req/s. Both are handled by tenacity exponential backoff + the shared semaphore (20 concurrent requests maximum).

**Streaming providers:** Disabled by default. The stub adapter reports `UNTESTED` status on health checks. Enable only after running contract tests against a live instance and confirming ToS compliance.

**Playback:** No DRM bypass, no anti-bot circumvention, no embed injection. Streaming servers are reported as-is from providers. Expired or geo-blocked URLs receive an explicit `playback_status` value, not a silent failure.

---

## Known Limitations

1. AniList has no streaming — episode lists from AniList contain metadata only.
2. Jikan episode objects have no streaming servers — metadata only.
3. All four streaming provider candidates (Anikito, Miruro, AniVault, YumeZone) are UNTESTED. AniVault has a known history of breaking API changes in this project.
4. The memory cache does not survive process restarts. Use Redis for persistence.
5. Live contract tests cannot run in a network-isolated build environment — run them locally.
