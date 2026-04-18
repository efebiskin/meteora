"""Response schemas returned by the public API."""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class Location(BaseModel):
    latitude: float
    longitude: float
    elevation_m: Optional[float] = None
    timezone: str


class CurrentWeather(BaseModel):
    """Current conditions at a point in time."""
    time: str = Field(..., description="ISO-8601 local time at the coordinates")
    temperature_c: float
    feels_like_c: float
    humidity_pct: int
    wind_speed_kmh: float
    wind_direction_deg: int
    precipitation_mm: float
    cloud_cover_pct: int
    weather_code: int
    weather_description: str
    is_day: bool
    pressure_hpa: float


class ForecastDay(BaseModel):
    """One day in a forecast."""
    date: str
    temp_max_c: float
    temp_min_c: float
    precipitation_mm: float
    precipitation_chance_pct: int
    wind_max_kmh: float
    sunrise: str
    sunset: str
    weather_code: int
    weather_description: str


class CurrentResponse(BaseModel):
    location: Location
    current: CurrentWeather


class ForecastResponse(BaseModel):
    location: Location
    days: List[ForecastDay]


class GeoResult(BaseModel):
    name: str
    country: str
    country_code: str
    admin1: Optional[str] = None
    latitude: float
    longitude: float
    population: Optional[int] = None


class GeoSearchResponse(BaseModel):
    results: List[GeoResult]


class HealthResponse(BaseModel):
    status: str
    version: str
    provider: str
