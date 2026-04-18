"""Integration tests for the Meteora API.

Uses FastAPI's TestClient, so the whole app boots in-process — no need to
spin up a server. A fresh temp SQLite file is used per test session so real
keys aren't affected.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Point the key store at a temp file BEFORE importing meteora so db.DB_PATH picks it up.
TMP_DB = Path(tempfile.gettempdir()) / "meteora_test.db"
if TMP_DB.exists():
    TMP_DB.unlink()
os.environ["METEORA_DB"] = str(TMP_DB)

from fastapi.testclient import TestClient  # noqa: E402
from meteora.main import app  # noqa: E402
from meteora import db         # noqa: E402

client = TestClient(app)
db.init_db()


# ──────────────────────────── Fixtures ────────────────────────────
@pytest.fixture(scope="session")
def api_key():
    """Create a free-tier key once per session."""
    r = client.post("/v1/keys", json={"email": "tester@example.com", "tier": "free"})
    assert r.status_code == 200, r.text
    return r.json()["key"]


# ─────────────────────────── Meta tests ───────────────────────────
def test_root_html():
    r = client.get("/")
    assert r.status_code == 200
    assert "Meteora" in r.text


def test_health_no_auth():
    r = client.get("/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["provider"] == "open-meteo"


def test_docs_reachable():
    r = client.get("/docs")
    assert r.status_code == 200


# ─────────────────────────── Keys tests ───────────────────────────
def test_signup_creates_key():
    r = client.post("/v1/keys", json={"email": "alice@example.com"})
    assert r.status_code == 200
    body = r.json()
    assert body["key"].startswith("mto_")
    assert body["tier"] == "free"
    assert body["rate_limit"] == 200


def test_signup_invalid_email():
    r = client.post("/v1/keys", json={"email": "not-an-email"})
    assert r.status_code == 422


def test_missing_key_gives_401():
    r = client.get("/v1/weather/current?lat=34.17&lon=-118.87")
    assert r.status_code == 401
    assert r.json()["detail"]["error"] == "missing_key"


def test_invalid_key_gives_401():
    r = client.get("/v1/weather/current?lat=34.17&lon=-118.87&key=mto_fake")
    assert r.status_code == 401
    assert r.json()["detail"]["error"] == "invalid_key"


# ─────────────────────────── Validation ───────────────────────────
def test_invalid_lat_gives_422(api_key):
    r = client.get(f"/v1/weather/current?lat=999&lon=0&key={api_key}")
    assert r.status_code == 422


def test_invalid_lon_gives_422(api_key):
    r = client.get(f"/v1/weather/current?lat=0&lon=999&key={api_key}")
    assert r.status_code == 422


def test_forecast_days_clamped(api_key):
    # days=100 should be rejected (1-16)
    r = client.get(f"/v1/weather/forecast?lat=34.17&lon=-118.87&days=100&key={api_key}")
    assert r.status_code == 422


# ─────────────────────────── Live weather ─────────────────────────
# These hit real Open-Meteo. If network is flaky, skip.
def _skip_if_offline(r):
    if r.status_code == 502:
        pytest.skip("upstream Open-Meteo unreachable")


def test_current_returns_real_data(api_key):
    r = client.get(f"/v1/weather/current?lat=34.17&lon=-118.87&key={api_key}")
    _skip_if_offline(r)
    assert r.status_code == 200
    body = r.json()
    assert "current" in body
    assert isinstance(body["current"]["temperature_c"], (int, float))
    assert body["current"]["weather_description"]
    # rate limit headers set
    assert "x-ratelimit-limit" in r.headers
    assert int(r.headers["x-ratelimit-limit"]) == 200


def test_forecast_returns_7_days(api_key):
    r = client.get(f"/v1/weather/forecast?lat=34.17&lon=-118.87&days=7&key={api_key}")
    _skip_if_offline(r)
    assert r.status_code == 200
    body = r.json()
    assert len(body["days"]) == 7
    for d in body["days"]:
        assert d["date"]
        assert isinstance(d["temp_max_c"], (int, float))


def test_hourly_returns_hours(api_key):
    r = client.get(f"/v1/weather/hourly?lat=34.17&lon=-118.87&hours=24&key={api_key}")
    _skip_if_offline(r)
    assert r.status_code == 200
    body = r.json()
    assert len(body["hours"]) == 24


def test_geo_search_finds_cities(api_key):
    r = client.get(f"/v1/geo/search?q=Thousand+Oaks&key={api_key}")
    _skip_if_offline(r)
    assert r.status_code == 200
    body = r.json()
    assert len(body["results"]) >= 1
    assert "Thousand Oaks" in body["results"][0]["name"]


def test_bulk_current(api_key):
    r = client.post(
        f"/v1/weather/bulk?key={api_key}",
        json={"points": [
            {"lat": 34.17, "lon": -118.87, "label": "Thousand Oaks"},
            {"lat": 40.73, "lon": -73.93, "label": "NYC"},
        ]},
    )
    _skip_if_offline(r)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1


def test_usage_endpoint(api_key):
    r = client.get(f"/v1/keys/usage?key={api_key}")
    assert r.status_code == 200
    body = r.json()
    assert body["rate_limit_daily"] == 200
    assert body["used_today"] >= 1         # this request itself counts
    assert body["remaining_today"] <= 199
