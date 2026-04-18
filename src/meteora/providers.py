"""Open-Meteo provider — the upstream data source.

Open-Meteo is free, doesn't require an API key, and has generous rate limits.
We wrap it here so callers of our API get a clean unified schema and we can
swap providers (or add more) later without touching the public endpoints.

Docs: https://open-meteo.com/en/docs
"""
from __future__ import annotations

import httpx
from typing import List, Optional

from .models import (
    CurrentResponse, CurrentWeather, ForecastDay, ForecastResponse,
    GeoResult, GeoSearchResponse, Location,
)

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_GEO = "https://geocoding-api.open-meteo.com/v1/search"

# WMO weather interpretation codes → human-readable
WMO_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def describe_code(code: int) -> str:
    return WMO_CODES.get(code, f"Unknown ({code})")


async def fetch_current(lat: float, lon: float, timezone: str = "auto") -> CurrentResponse:
    """Get current conditions at a point."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": (
            "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,"
            "wind_direction_10m,precipitation,cloud_cover,weather_code,is_day,surface_pressure"
        ),
        "timezone": timezone,
        "wind_speed_unit": "kmh",
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(OPEN_METEO, params=params)
        r.raise_for_status()
        data = r.json()

    c = data["current"]
    code = int(c["weather_code"])
    return CurrentResponse(
        location=Location(
            latitude=data["latitude"],
            longitude=data["longitude"],
            elevation_m=data.get("elevation"),
            timezone=data.get("timezone", timezone),
        ),
        current=CurrentWeather(
            time=c["time"],
            temperature_c=c["temperature_2m"],
            feels_like_c=c["apparent_temperature"],
            humidity_pct=int(c["relative_humidity_2m"]),
            wind_speed_kmh=c["wind_speed_10m"],
            wind_direction_deg=int(c["wind_direction_10m"]),
            precipitation_mm=c["precipitation"],
            cloud_cover_pct=int(c["cloud_cover"]),
            weather_code=code,
            weather_description=describe_code(code),
            is_day=bool(c["is_day"]),
            pressure_hpa=c["surface_pressure"],
        ),
    )


async def fetch_forecast(lat: float, lon: float, days: int = 7, timezone: str = "auto") -> ForecastResponse:
    """Get the N-day forecast at a point (max 16)."""
    days = max(1, min(16, days))
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": (
            "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,"
            "wind_speed_10m_max,sunrise,sunset,weather_code"
        ),
        "forecast_days": days,
        "timezone": timezone,
        "wind_speed_unit": "kmh",
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(OPEN_METEO, params=params)
        r.raise_for_status()
        data = r.json()

    d = data["daily"]
    out_days: List[ForecastDay] = []
    for i in range(len(d["time"])):
        code = int(d["weather_code"][i])
        out_days.append(ForecastDay(
            date=d["time"][i],
            temp_max_c=d["temperature_2m_max"][i],
            temp_min_c=d["temperature_2m_min"][i],
            precipitation_mm=d["precipitation_sum"][i] or 0.0,
            precipitation_chance_pct=int(d.get("precipitation_probability_max", [0] * len(d["time"]))[i] or 0),
            wind_max_kmh=d["wind_speed_10m_max"][i],
            sunrise=d["sunrise"][i],
            sunset=d["sunset"][i],
            weather_code=code,
            weather_description=describe_code(code),
        ))
    return ForecastResponse(
        location=Location(
            latitude=data["latitude"],
            longitude=data["longitude"],
            elevation_m=data.get("elevation"),
            timezone=data.get("timezone", timezone),
        ),
        days=out_days,
    )


async def search_location(query: str, count: int = 5) -> GeoSearchResponse:
    """Geocode a place-name query to lat/lon candidates."""
    params = {"name": query, "count": max(1, min(20, count)), "language": "en", "format": "json"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(OPEN_METEO_GEO, params=params)
        r.raise_for_status()
        data = r.json()

    results = []
    for item in data.get("results", []):
        results.append(GeoResult(
            name=item["name"],
            country=item.get("country", ""),
            country_code=item.get("country_code", ""),
            admin1=item.get("admin1"),
            latitude=item["latitude"],
            longitude=item["longitude"],
            population=item.get("population"),
        ))
    return GeoSearchResponse(results=results)
