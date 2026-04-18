"""meteora-client — a thin Python SDK for the Meteora weather API.

Install:
    pip install meteora-client

Usage:
    from meteora_client import Meteora
    mt = Meteora(api_key="mto_xxx", base_url="https://api.example.com")
    cur = mt.current(lat=34.17, lon=-118.87)
    print(cur["current"]["temperature_c"])
"""
from __future__ import annotations

import httpx
from typing import Any, Optional

__version__ = "0.1.0"


class MeteoraError(Exception):
    """Raised when the API returns a non-2xx response."""
    def __init__(self, status: int, detail: Any):
        self.status = status
        self.detail = detail
        super().__init__(f"Meteora {status}: {detail}")


class Meteora:
    """Synchronous client for the Meteora weather API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8787",
        timeout: float = 15.0,
    ):
        if not api_key:
            raise ValueError("api_key is required (get one at POST /v1/keys)")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={"X-API-Key": api_key, "User-Agent": f"meteora-client-py/{__version__}"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Meteora":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ─── internal ─────────────────────────────────────────────────────────
    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        r = self._client.get(path, params=params)
        if r.status_code >= 400:
            try:
                body = r.json()
            except Exception:
                body = r.text
            raise MeteoraError(r.status_code, body)
        return r.json()

    def _post(self, path: str, json: dict) -> dict:
        r = self._client.post(path, json=json)
        if r.status_code >= 400:
            try:
                body = r.json()
            except Exception:
                body = r.text
            raise MeteoraError(r.status_code, body)
        return r.json()

    # ─── endpoints ────────────────────────────────────────────────────────
    def health(self) -> dict:
        return self._get("/v1/health")

    def current(self, lat: float, lon: float, timezone: str = "auto") -> dict:
        return self._get("/v1/weather/current", {"lat": lat, "lon": lon, "timezone": timezone})

    def forecast(self, lat: float, lon: float, days: int = 7, timezone: str = "auto") -> dict:
        return self._get("/v1/weather/forecast", {"lat": lat, "lon": lon, "days": days, "timezone": timezone})

    def hourly(self, lat: float, lon: float, hours: int = 24, timezone: str = "auto") -> dict:
        return self._get("/v1/weather/hourly", {"lat": lat, "lon": lon, "hours": hours, "timezone": timezone})

    def historical(self, lat: float, lon: float, start: str, end: str, timezone: str = "auto") -> dict:
        return self._get("/v1/weather/historical",
                         {"lat": lat, "lon": lon, "start": start, "end": end, "timezone": timezone})

    def air_quality(self, lat: float, lon: float, timezone: str = "auto") -> dict:
        return self._get("/v1/air-quality", {"lat": lat, "lon": lon, "timezone": timezone})

    def bulk_current(self, points: list[dict]) -> dict:
        return self._post("/v1/weather/bulk", {"points": points})

    def geo_search(self, q: str, count: int = 5) -> dict:
        return self._get("/v1/geo/search", {"q": q, "count": count})

    def usage(self) -> dict:
        return self._get("/v1/keys/usage")


__all__ = ["Meteora", "MeteoraError", "__version__"]
