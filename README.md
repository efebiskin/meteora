# Meteora

> A public weather API wrapping Open-Meteo with a clean, unified schema. Zero runtime dependencies beyond FastAPI + httpx. Free for personal and commercial use.

![tests](https://img.shields.io/badge/status-beta-orange)
![python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)
![fastapi](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi&logoColor=white)
![license: MIT](https://img.shields.io/badge/license-MIT-green.svg)

A small, clean weather API you can run locally or deploy anywhere. Three endpoints, real typed responses, auto-generated Swagger docs, and a demo frontend that uses it as its first customer.

```
GET /v1/weather/current?lat=34.17&lon=-118.87
GET /v1/weather/forecast?lat=34.17&lon=-118.87&days=7
GET /v1/geo/search?q=Thousand+Oaks
```

---

## Why Meteora?

Open-Meteo is excellent but its raw response schema is verbose and inconsistent across endpoints. Meteora wraps it into:

- **Unified schema** — every response has a predictable `location` block + a typed payload
- **WMO codes translated** — `weather_code: 3` becomes `weather_description: "Overcast"`
- **Clean units** — °C, km/h, mm, hPa, everywhere
- **Auto Swagger UI** at `/docs` thanks to FastAPI
- **CORS enabled** so browsers can hit it directly
- **Async + fast** — uses `httpx.AsyncClient` under the hood

Think of it as *Open-Meteo, but with the corners filed down.*

---

## Run locally

```bash
git clone https://github.com/efebiskin/meteora
cd meteora
pip install -e .
uvicorn meteora.main:app --reload --port 8787
```

Then:
- API: http://localhost:8787
- Interactive docs (Swagger UI): http://localhost:8787/docs
- Alternative docs (ReDoc): http://localhost:8787/redoc
- Demo web app: open `web/index.html` in a browser, or serve it:
  ```bash
  python -m http.server 5555 -d web
  # then open http://localhost:5555
  ```

---

## Try it (curl)

```bash
# Health
curl http://localhost:8787/v1/health

# Current weather at a coordinate
curl "http://localhost:8787/v1/weather/current?lat=34.17&lon=-118.87"

# 7-day forecast
curl "http://localhost:8787/v1/weather/forecast?lat=34.17&lon=-118.87&days=7"

# Geocode a place-name
curl "http://localhost:8787/v1/geo/search?q=Istanbul&count=3"
```

### Example response

```json
{
  "location": {
    "latitude": 34.17,
    "longitude": -118.87,
    "elevation_m": 310.0,
    "timezone": "America/Los_Angeles"
  },
  "current": {
    "time": "2026-04-18T11:15",
    "temperature_c": 25.0,
    "feels_like_c": 23.4,
    "humidity_pct": 11,
    "wind_speed_kmh": 5.6,
    "wind_direction_deg": 130,
    "precipitation_mm": 0.0,
    "cloud_cover_pct": 80,
    "weather_code": 3,
    "weather_description": "Overcast",
    "is_day": true,
    "pressure_hpa": 979.4
  }
}
```

---

## Use it from JavaScript

```javascript
const r = await fetch(
  "http://localhost:8787/v1/weather/current?lat=34.17&lon=-118.87"
);
const { current } = await r.json();
console.log(`${current.temperature_c}°C, ${current.weather_description}`);
```

## Use it from Python

```python
import httpx

r = httpx.get("http://localhost:8787/v1/weather/current",
              params={"lat": 34.17, "lon": -118.87})
r.raise_for_status()
cur = r.json()["current"]
print(f"{cur['temperature_c']}°C, {cur['weather_description']}")
```

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/health` | Version + provider check |
| `GET` | `/v1/weather/current` | Current conditions at `lat,lon` |
| `GET` | `/v1/weather/forecast` | Daily forecast, 1-16 days |
| `GET` | `/v1/geo/search` | Place-name → lat/lon candidates |

Full typed schema: [/docs](http://localhost:8787/docs) after start.

---

## Attribution

Data sourced from [Open-Meteo](https://open-meteo.com/) (CC-BY 4.0). Meteora is a thin wrapper that normalizes their response shape — please consider supporting Open-Meteo if you rely on their data.

## Roadmap

- [x] Phase 1 — FastAPI server + 3 endpoints + demo frontend
- [ ] Phase 2 — API key system with SQLite-backed usage tracking
- [ ] Phase 3 — Deploy to Railway / Fly.io at `api.efebiskin.com/v1`
- [ ] Phase 4 — In-memory cache to cut Open-Meteo round-trips
- [ ] Phase 5 — Historical endpoint (`/v1/weather/historical`)

## License

MIT — see [LICENSE](LICENSE).

Built by [Efe Biskin](https://github.com/efebiskin).
