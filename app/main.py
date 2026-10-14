"""
Anime API Aggregator — FastAPI application.

Startup order:
  1. Configure logging
  2. Initialise provider registry
  3. Mount routers
  4. Register lifespan (HTTP client cleanup)
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import get_settings
from app.core.http_client import close_client
from app.core.logging import configure_logging, get_logger
from app.providers import registry
from app.routers.anime import router as anime_router

configure_logging()
logger = get_logger(__name__)
_settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", env=_settings.app_env)
    registry.init_registry()
    yield
    await close_client()
    logger.info("shutdown_complete")


app = FastAPI(
    title="Anime API Aggregator",
    description=(
        "Multi-provider anime metadata API with a same-origin browser catalog and API explorer. "
        "Verified providers: AniList, Jikan. "
        "Streaming providers (Anikito, Miruro, AniVault, YumeZone) are UNTESTED "
        "and disabled by default pending contract-test verification."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ── CORS ──────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _settings.app_env == "development" else [],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Routers ───────────────────────────────────────────────────────────────
app.include_router(anime_router)


# ── Root ──────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    # Keep the browser client same-origin with the API so Railway needs no
    # separate frontend service or cross-origin configuration.
    index = Path(__file__).parent / "web" / "index.html"
    return FileResponse(index, media_type="text/html")


# ── Global error handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", path=str(request.url), error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": "internal_error", "message": "An unexpected error occurred"},
    )
