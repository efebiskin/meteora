"""Open-Meteo provider — upstream data source for current/forecast/hourly/historical/air-quality.

Each function is cached via @cached(ttl_seconds=...) to amortize upstream calls.
Docs: https://open-meteo.com/en/docs
"""
from __future__ import annotations

import httpx
from typing import List

from .cache import cached
from .models import (
    AirQuality, AirQualityResponse, CurrentResponse, CurrentWeather,
    ForecastDay, ForecastResponse, GeoResult, GeoSearchResponse,
    HistoricalDay, HistoricalResponse, HourlyEntry, HourlyResponse, Location,
)

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_GEO = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_AIR = "https://air-quality-api.open-meteo.com/v1/air-quality"

WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


def describe_code(code: int) -> str:
    return WMO_CODES.get(code, f"Unknown ({code})")


def _loc(data: dict, tz: str) -> Location:
    return Location(
        latitude=data["latitude"], longitude=data["longitude"],
        elevation_m=data.get("elevation"), timezone=data.get("timezone", tz),
    )


async def _get(url: str, params: dict) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()


@cached(ttl_seconds=300)
async def fetch_current(lat: float, lon: float, timezone: str = "auto") -> CurrentResponse:
    data = await _get(OPEN_METEO, {
        "latitude": lat, "longitude": lon,
        "current": ("temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,"
                    "wind_direction_10m,precipitation,cloud_cover,weather_code,is_day,surface_pressure"),
        "timezone": timezone,
        "wind_speed_unit": "kmh", "temperature_unit": "celsius", "precipitation_unit": "mm",
    })
    c = data["current"]
    code = int(c["weather_code"])
    return CurrentResponse(
        location=_loc(data, timezone),
        current=CurrentWeather(
            time=c["time"], temperature_c=c["temperature_2m"], feels_like_c=c["apparent_temperature"],
            humidity_pct=int(c["relative_humidity_2m"]), wind_speed_kmh=c["wind_speed_10m"],
            wind_direction_deg=int(c["wind_direction_10m"]), precipitation_mm=c["precipitation"],
            cloud_cover_pct=int(c["cloud_cover"]), weather_code=code,
            weather_description=describe_code(code), is_day=bool(c["is_day"]),
            pressure_hpa=c["surface_pressure"],
        ),
    )


@cached(ttl_seconds=600)
async def fetch_forecast(lat: float, lon: float, days: int = 7, timezone: str = "auto") -> ForecastResponse:
    days = max(1, min(16, days))
    data = await _get(OPEN_METEO, {
        "latitude": lat, "longitude": lon,
        "daily": ("temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,"
                  "wind_speed_10m_max,sunrise,sunset,weather_code,uv_index_max"),
        "forecast_days": days, "timezone": timezone,
        "wind_speed_unit": "kmh", "temperature_unit": "celsius", "precipitation_unit": "mm",
    })
    d = data["daily"]
    out: List[ForecastDay] = []
    for i in range(len(d["time"])):
        code = int(d["weather_code"][i])
        out.append(ForecastDay(
            date=d["time"][i], temp_max_c=d["temperature_2m_max"][i], temp_min_c=d["temperature_2m_min"][i],
            precipitation_mm=d["precipitation_sum"][i] or 0.0,
            precipitation_chance_pct=int((d.get("precipitation_probability_max") or [0]*len(d["time"]))[i] or 0),
            wind_max_kmh=d["wind_speed_10m_max"][i], sunrise=d["sunrise"][i], sunset=d["sunset"][i],
            weather_code=code, weather_description=describe_code(code),
            uv_index_max=d.get("uv_index_max", [None]*len(d["time"]))[i],
        ))
    return ForecastResponse(location=_loc(data, timezone), days=out)


@cached(ttl_seconds=600)
async def fetch_hourly(lat: float, lon: float, hours: int = 24, timezone: str = "auto") -> HourlyResponse:
    hours = max(1, min(168, hours))
    data = await _get(OPEN_METEO, {
        "latitude": lat, "longitude": lon,
        "hourly": ("temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,"
                   "precipitation,precipitation_probability,cloud_cover,weather_code"),
        "forecast_hours": hours, "timezone": timezone,
        "wind_speed_unit": "kmh", "temperature_unit": "celsius", "precipitation_unit": "mm",
    })
    h = data["hourly"]
    out: List[HourlyEntry] = []
    for i in range(len(h["time"])):
        code = int(h["weather_code"][i])
        out.append(HourlyEntry(
            time=h["time"][i], temperature_c=h["temperature_2m"][i], feels_like_c=h["apparent_temperature"][i],
            humidity_pct=int(h["relative_humidity_2m"][i]), wind_speed_kmh=h["wind_speed_10m"][i],
            precipitation_mm=h["precipitation"][i] or 0.0,
            precipitation_chance_pct=int((h.get("precipitation_probability") or [0]*len(h["time"]))[i] or 0),
            cloud_cover_pct=int(h["cloud_cover"][i]), weather_code=code,
            weather_description=describe_code(code),
        ))
    return HourlyResponse(location=_loc(data, timezone), hours=out)


@cached(ttl_seconds=86400)
async def fetch_historical(lat: float, lon: float, start: str, end: str, timezone: str = "auto") -> HistoricalResponse:
    data = await _get(OPEN_METEO_ARCHIVE, {
        "latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
        "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,wind_speed_10m_max",
        "timezone": timezone,
        "wind_speed_unit": "kmh", "temperature_unit": "celsius", "precipitation_unit": "mm",
    })
    d = data["daily"]
    out = [
        HistoricalDay(
            date=d["time"][i], temp_max_c=d["temperature_2m_max"][i],
            temp_min_c=d["temperature_2m_min"][i], temp_mean_c=d["temperature_2m_mean"][i],
            precipitation_mm=d["precipitation_sum"][i] or 0.0,
            wind_max_kmh=d["wind_speed_10m_max"][i],
        ) for i in range(len(d["time"]))
    ]
    return HistoricalResponse(location=_loc(data, timezone), start_date=start, end_date=end, days=out)


@cached(ttl_seconds=600)
async def fetch_air_quality(lat: float, lon: float, timezone: str = "auto") -> AirQualityResponse:
    data = await _get(OPEN_METEO_AIR, {
        "latitude": lat, "longitude": lon,
        "current": "pm10,pm2_5,ozone,nitrogen_dioxide,european_aqi,us_aqi",
        "timezone": timezone,
    })
    c = data["current"]
    return AirQualityResponse(
        location=_loc(data, timezone),
        current=AirQuality(
            time=c["time"], pm10_ug_m3=c.get("pm10"), pm2_5_ug_m3=c.get("pm2_5"),
            ozone_ug_m3=c.get("ozone"), nitrogen_dioxide_ug_m3=c.get("nitrogen_dioxide"),
            european_aqi=int(c["european_aqi"]) if c.get("european_aqi") is not None else None,
            us_aqi=int(c["us_aqi"]) if c.get("us_aqi") is not None else None,
        ),
    )


@cached(ttl_seconds=3600)
async def search_location(query: str, count: int = 5) -> GeoSearchResponse:
    data = await _get(OPEN_METEO_GEO, {
        "name": query, "count": max(1, min(20, count)), "language": "en", "format": "json",
    })
    results = []
    for item in data.get("results", []):
        results.append(GeoResult(
            name=item["name"], country=item.get("country", ""), country_code=item.get("country_code", ""),
            admin1=item.get("admin1"), latitude=item["latitude"], longitude=item["longitude"],
            population=item.get("population"),
        ))
    return GeoSearchResponse(results=results)
