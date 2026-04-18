"""Meteora weather API — FastAPI app.

Phase 1: public endpoints (no auth) wrapping Open-Meteo with a clean schema.
Phase 2 will add API keys, usage tracking, and rate limiting.

Run locally:
    uvicorn meteora.main:app --reload --port 8787
Auto-generated interactive docs: http://localhost:8787/docs
"""
from __future__ import annotations

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
import httpx

from . import __version__
from .models import (
    CurrentResponse, ForecastResponse, GeoSearchResponse, HealthResponse,
)
from .providers import fetch_current, fetch_forecast, search_location


app = FastAPI(
    title="Meteora",
    description=(
        "A public weather API wrapping Open-Meteo with a clean, unified schema. "
        "Free to use for personal and commercial projects. Built by Efe Biskin."
    ),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow the demo web app + any third-party site to call us from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Landing + health
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    return """
    <!DOCTYPE html><html><head><meta charset="utf-8"><title>Meteora</title>
    <style>
      body{font-family:ui-monospace,monospace;background:#0e0e0e;color:#f5f5f5;max-width:720px;margin:4rem auto;padding:2rem;line-height:1.7}
      h1{font-family:'Archivo',system-ui,sans-serif;font-weight:900;font-size:3rem;letter-spacing:-.02em;margin:0 0 .5rem}
      em{color:#aaa;font-style:italic}
      code{background:#1a1a1a;padding:.15rem .5rem;border-radius:3px;color:#ffd166}
      a{color:#ffd166}
      hr{border:0;border-top:1px solid #333;margin:2rem 0}
      .pill{display:inline-block;padding:.25rem .7rem;border:1px solid #444;border-radius:999px;font-size:.72rem;letter-spacing:.15em;margin-right:.4rem}
    </style>
    </head><body>
      <h1>Meteora</h1>
      <p><em>A weather API for the modern age.</em></p>
      <p><span class="pill">v0.1.0</span><span class="pill">OPEN-METEO</span><span class="pill">FREE TIER</span></p>
      <hr/>
      <p>Three endpoints:</p>
      <ul>
        <li><code>GET /v1/weather/current?lat=34.17&amp;lon=-118.87</code></li>
        <li><code>GET /v1/weather/forecast?lat=34.17&amp;lon=-118.87&amp;days=7</code></li>
        <li><code>GET /v1/geo/search?q=Thousand+Oaks</code></li>
      </ul>
      <p>Interactive docs: <a href="/docs">/docs</a> · OpenAPI schema: <a href="/openapi.json">/openapi.json</a></p>
      <hr/>
      <p style="color:#888;font-size:.85rem">Built by Efe Biskin · <a href="https://github.com/efebiskin/meteora">github.com/efebiskin/meteora</a></p>
    </body></html>
    """


@app.get("/v1/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__, provider="open-meteo")


# -----------------------------------------------------------------------------
# Weather endpoints
# -----------------------------------------------------------------------------
@app.get(
    "/v1/weather/current",
    response_model=CurrentResponse,
    tags=["weather"],
    summary="Current conditions at a coordinate",
)
async def current(
    lat: float = Query(..., ge=-90, le=90, description="Latitude, -90 to 90"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude, -180 to 180"),
    timezone: str = Query("auto", description="IANA timezone or 'auto'"),
) -> CurrentResponse:
    try:
        return await fetch_current(lat, lon, timezone)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"upstream error: {e}") from e


@app.get(
    "/v1/weather/forecast",
    response_model=ForecastResponse,
    tags=["weather"],
    summary="Daily forecast for up to 16 days",
)
async def forecast(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    days: int = Query(7, ge=1, le=16, description="Forecast horizon, 1-16"),
    timezone: str = Query("auto"),
) -> ForecastResponse:
    try:
        return await fetch_forecast(lat, lon, days, timezone)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"upstream error: {e}") from e


# -----------------------------------------------------------------------------
# Geocoding
# -----------------------------------------------------------------------------
@app.get(
    "/v1/geo/search",
    response_model=GeoSearchResponse,
    tags=["geo"],
    summary="Search for a location by name",
)
async def geo_search(
    q: str = Query(..., min_length=2, description="Place name, e.g. 'Thousand Oaks'"),
    count: int = Query(5, ge=1, le=20),
) -> GeoSearchResponse:
    try:
        return await search_location(q, count)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"upstream error: {e}") from e
