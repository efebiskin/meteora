"""Response schemas returned by the public API."""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


# ─── Core / location ─────────────────────────────────────────────────────────
class Location(BaseModel):
    latitude: float
    longitude: float
    elevation_m: Optional[float] = None
    timezone: str


# ─── Current / forecast / hourly ─────────────────────────────────────────────
class CurrentWeather(BaseModel):
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
    uv_index_max: Optional[float] = None


class HourlyEntry(BaseModel):
    time: str
    temperature_c: float
    feels_like_c: float
    humidity_pct: int
    wind_speed_kmh: float
    precipitation_mm: float
    precipitation_chance_pct: int
    cloud_cover_pct: int
    weather_code: int
    weather_description: str


class CurrentResponse(BaseModel):
    location: Location
    current: CurrentWeather


class ForecastResponse(BaseModel):
    location: Location
    days: List[ForecastDay]


class HourlyResponse(BaseModel):
    location: Location
    hours: List[HourlyEntry]


class HistoricalDay(BaseModel):
    date: str
    temp_max_c: float
    temp_min_c: float
    temp_mean_c: float
    precipitation_mm: float
    wind_max_kmh: float


class HistoricalResponse(BaseModel):
    location: Location
    start_date: str
    end_date: str
    days: List[HistoricalDay]


class AirQuality(BaseModel):
    time: str
    pm10_ug_m3: Optional[float] = None
    pm2_5_ug_m3: Optional[float] = None
    ozone_ug_m3: Optional[float] = None
    nitrogen_dioxide_ug_m3: Optional[float] = None
    european_aqi: Optional[int] = None
    us_aqi: Optional[int] = None


class AirQualityResponse(BaseModel):
    location: Location
    current: AirQuality


class BulkPoint(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    label: Optional[str] = None


class BulkRequest(BaseModel):
    points: List[BulkPoint] = Field(..., min_length=1, max_length=100)


class BulkCurrentResult(BaseModel):
    label: Optional[str]
    location: Location
    current: CurrentWeather


class BulkCurrentResponse(BaseModel):
    count: int
    results: List[BulkCurrentResult]


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
    cache: Optional[dict] = None


class SignupRequest(BaseModel):
    email: EmailStr
    tier: str = Field("free", pattern=r"^(free|pro|enterprise)$")


class SignupResponse(BaseModel):
    id: int
    key: str = Field(..., description="Your new API key. Save it — it will not be shown again.")
    prefix: str
    email: str
    tier: str
    rate_limit: int
    docs: str = "https://github.com/efebiskin/meteora#readme"


class UsageResponse(BaseModel):
    key_prefix: str
    tier: str
    rate_limit_daily: int
    used_today: int
    remaining_today: int
    history: List[dict]


# ─── Stock quotes ────────────────────────────────────────────────────────────
class Quote(BaseModel):
    symbol: str
    name: str
    price: float
    change: float = Field(..., description="Day change in currency units")
    change_pct: float = Field(..., description="Day change as a percentage")
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    previous_close: Optional[float] = None
    volume: Optional[int] = None
    currency: str = "USD"
    exchange: Optional[str] = None
    market_state: Optional[str] = Field(None, description="PRE | REGULAR | POST | CLOSED")


class QuotesResponse(BaseModel):
    count: int
    source: str = Field(..., description="Upstream provider that served the data")
    quotes: List[Quote]
