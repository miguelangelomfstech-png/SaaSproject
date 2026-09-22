"""
main.py
-------
FastAPI application factory.

Startup sequence:
  1. init_db()  — create tables if they don't exist
  2. Mount routers: webhook, api, admin
  3. Attach slowapi rate-limit error handler

Environment requirements: see .env.example
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.database import init_db
from app.dependencies import limiter
from app.routers import admin, api, webhook
from app.schemas import HealthResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan: runs on startup and shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure the data directory exists (for SQLite)
    os.makedirs("data", exist_ok=True)
    logger.info("Initialising database …")
    await init_db()
    logger.info("RankLens API is ready 🚀")
    yield
    logger.info("RankLens API shutting down.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RankLens API",
    description=(
        "## AI-Powered SEO Intelligence API\n\n"
        "Get keyword difficulty scores, SERP analysis, competitor gap insights, "
        "and AI-generated strategy recommendations — all via a simple REST API.\n\n"
        "### Authentication\n"
        "All `/api/v1/*` endpoints require an `X-API-Key` header.\n\n"
        "### Plans\n"
        "| Plan | Daily Limit | Endpoints |\n"
        "|------|------------|----------|\n"
        "| Starter ($9/mo) | 100 req/day | `/analyze` |\n"
        "| Pro ($29/mo) | 1,000 req/day | + `/competitor-gap` |\n"
        "| Agency ($79/mo) | 10,000 req/day | + `/bulk` |\n\n"
        "Purchase at [ranklens.dev](https://ranklens.dev)."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    contact={"name": "RankLens Support", "email": "support@ranklens.dev"},
    license_info={"name": "Commercial", "url": "https://ranklens.dev/terms"},
)

# --- Rate limiting -----------------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS -------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten this in production if needed
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --- Routers ----------------------------------------------------------------
app.include_router(webhook.router)
app.include_router(api.router)
app.include_router(admin.router)


# ---------------------------------------------------------------------------
# Root & health endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/",
    response_model=HealthResponse,
    tags=["Health"],
    summary="API Root",
    include_in_schema=False,
)
async def root() -> dict:
    return {"status": "ok", "version": "1.0.0"}


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health Check",
    description="Used by Render / Docker health checks.",
)
async def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}
