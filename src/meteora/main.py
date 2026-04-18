"""Meteora weather API — production-grade FastAPI app.

Features:
  - 7 weather endpoints (current, forecast, hourly, historical, air-quality, bulk, geo)
  - API key auth (X-API-Key header OR ?key= query param)
  - Per-key daily rate limiting (SQLite-backed)
  - In-memory TTL caching of upstream calls
  - WMO weather codes translated to human-readable descriptions
  - Auto-generated OpenAPI docs at /docs
  - CORS enabled

Run locally:
    uvicorn meteora.main:app --reload --port 8787
Interactive docs: http://localhost:8787/docs
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Query, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import httpx

from . import __version__, db, cache
from .auth import require_key, attach_rate_headers
from .models import (
    AirQualityResponse, BulkCurrentResponse, BulkCurrentResult, BulkRequest,
    CurrentResponse, ForecastResponse, GeoSearchResponse, HealthResponse,
    HistoricalResponse, HourlyResponse, SignupRequest, SignupResponse,
    UsageResponse,
)
from .providers import (
    fetch_air_quality, fetch_current, fetch_forecast, fetch_historical,
    fetch_hourly, search_location,
)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="Meteora",
    description=(
        "A production weather API wrapping Open-Meteo with a clean, unified schema, "
        "API keys, rate limits, and in-memory caching. Built by Efe Biskin."
    ),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Used", "X-RateLimit-Remaining", "X-RateLimit-Tier"],
)


# ═════════════════════════════════════════════════════════════════════════════
# Landing / health / meta (no auth)
# ═════════════════════════════════════════════════════════════════════════════
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Meteora v{__version__}</title>
    <style>
      body{{font-family:ui-monospace,monospace;background:#0e0e0e;color:#f5f5f5;max-width:760px;margin:4rem auto;padding:2rem;line-height:1.75}}
      h1{{font-family:'Archivo',system-ui,sans-serif;font-weight:900;font-size:3rem;letter-spacing:-.02em;margin:0 0 .5rem}}
      em{{color:#aaa;font-style:italic}}
      code{{background:#1a1a1a;padding:.15rem .5rem;border-radius:3px;color:#ffd166}}
      a{{color:#ffd166}}
      hr{{border:0;border-top:1px solid #333;margin:2rem 0}}
      .pill{{display:inline-block;padding:.25rem .7rem;border:1px solid #444;border-radius:999px;font-size:.72rem;letter-spacing:.15em;margin-right:.4rem}}
    </style></head><body>
      <h1>Meteora</h1>
      <p><em>A production weather API for the modern age.</em></p>
      <p><span class="pill">v{__version__}</span><span class="pill">7 ENDPOINTS</span><span class="pill">API KEYS</span><span class="pill">RATE LIMITED</span><span class="pill">CACHED</span></p>
      <hr/>
      <p><strong>Get a free API key (200 req/day):</strong></p>
      <p><code>POST /v1/keys &#123;"email": "you@example.com"&#125;</code></p>
      <p><strong>Endpoints</strong> (all take <code>?key=mto_...</code> or <code>X-API-Key</code> header):</p>
      <ul>
        <li><code>GET /v1/weather/current</code></li>
        <li><code>GET /v1/weather/forecast</code></li>
        <li><code>GET /v1/weather/hourly</code></li>
        <li><code>GET /v1/weather/historical</code></li>
        <li><code>GET /v1/air-quality</code></li>
        <li><code>POST /v1/weather/bulk</code></li>
        <li><code>GET /v1/geo/search</code></li>
      </ul>
      <p>Interactive docs: <a href="/docs">/docs</a></p>
      <hr/>
      <p style="color:#888;font-size:.85rem">Built by Efe Biskin · <a href="https://github.com/efebiskin/meteora">github.com/efebiskin/meteora</a></p>
    </body></html>
    """


@app.get("/v1/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__, provider="open-meteo", cache=cache.stats())


# ═════════════════════════════════════════════════════════════════════════════
# API keys
# ═════════════════════════════════════════════════════════════════════════════
@app.post("/v1/keys", response_model=SignupResponse, tags=["keys"])
async def signup(body: SignupRequest) -> SignupResponse:
    """Create a new API key. Free tier = 200 req/day."""
    rec = db.create_key(body.email, body.tier)
    return SignupResponse(**rec)


@app.get("/v1/keys/usage", response_model=UsageResponse, tags=["keys"])
async def usage(response: Response, rec=Depends(require_key)) -> UsageResponse:
    """Check your key's usage + quota. Counts toward the rate limit itself."""
    used = db.get_usage_today(rec["id"])
    history = db.get_usage_history(rec["id"], days=30)
    attach_rate_headers(response, rec, used)
    return UsageResponse(
        key_prefix=rec["key_prefix"], tier=rec["tier"],
        rate_limit_daily=rec["rate_limit"], used_today=used,
        remaining_today=max(0, rec["rate_limit"] - used), history=history,
    )


# ═════════════════════════════════════════════════════════════════════════════
# Weather
# ═════════════════════════════════════════════════════════════════════════════
async def _err(coro):
    try:
        return await coro
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"upstream error: {e}") from e


@app.get("/v1/weather/current", response_model=CurrentResponse, tags=["weather"])
async def current(
    request: Request, response: Response,
    lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180),
    timezone: str = Query("auto"), rec=Depends(require_key),
) -> CurrentResponse:
    result = await _err(fetch_current(lat, lon, timezone))
    attach_rate_headers(response, rec, request.state.usage_count)
    return result


@app.get("/v1/weather/forecast", response_model=ForecastResponse, tags=["weather"])
async def forecast(
    request: Request, response: Response,
    lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180),
    days: int = Query(7, ge=1, le=16), timezone: str = Query("auto"),
    rec=Depends(require_key),
) -> ForecastResponse:
    result = await _err(fetch_forecast(lat, lon, days, timezone))
    attach_rate_headers(response, rec, request.state.usage_count)
    return result


@app.get("/v1/weather/hourly", response_model=HourlyResponse, tags=["weather"])
async def hourly(
    request: Request, response: Response,
    lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180),
    hours: int = Query(24, ge=1, le=168), timezone: str = Query("auto"),
    rec=Depends(require_key),
) -> HourlyResponse:
    result = await _err(fetch_hourly(lat, lon, hours, timezone))
    attach_rate_headers(response, rec, request.state.usage_count)
    return result


@app.get("/v1/weather/historical", response_model=HistoricalResponse, tags=["weather"])
async def historical(
    request: Request, response: Response,
    lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180),
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    timezone: str = Query("auto"), rec=Depends(require_key),
) -> HistoricalResponse:
    result = await _err(fetch_historical(lat, lon, start, end, timezone))
    attach_rate_headers(response, rec, request.state.usage_count)
    return result


@app.post("/v1/weather/bulk", response_model=BulkCurrentResponse, tags=["weather"])
async def bulk_current(
    request: Request, response: Response,
    body: BulkRequest, rec=Depends(require_key),
) -> BulkCurrentResponse:
    """Current weather for up to 100 coordinates in parallel. One request against your quota."""
    tasks = [fetch_current(p.lat, p.lon) for p in body.points]
    raw = await asyncio.gather(*tasks, return_exceptions=True)
    out = [
        BulkCurrentResult(label=p.label, location=r.location, current=r.current)
        for p, r in zip(body.points, raw) if not isinstance(r, Exception)
    ]
    attach_rate_headers(response, rec, request.state.usage_count)
    return BulkCurrentResponse(count=len(out), results=out)


# ═════════════════════════════════════════════════════════════════════════════
# Air quality
# ═════════════════════════════════════════════════════════════════════════════
@app.get("/v1/air-quality", response_model=AirQualityResponse, tags=["air-quality"])
async def air_quality(
    request: Request, response: Response,
    lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180),
    timezone: str = Query("auto"), rec=Depends(require_key),
) -> AirQualityResponse:
    result = await _err(fetch_air_quality(lat, lon, timezone))
    attach_rate_headers(response, rec, request.state.usage_count)
    return result


# ═════════════════════════════════════════════════════════════════════════════
# Geocoding
# ═════════════════════════════════════════════════════════════════════════════
@app.get("/v1/geo/search", response_model=GeoSearchResponse, tags=["geo"])
async def geo_search(
    request: Request, response: Response,
    q: str = Query(..., min_length=2), count: int = Query(5, ge=1, le=20),
    rec=Depends(require_key),
) -> GeoSearchResponse:
    result = await _err(search_location(q, count))
    attach_rate_headers(response, rec, request.state.usage_count)
    return result
