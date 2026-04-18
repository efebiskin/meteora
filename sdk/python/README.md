# meteora-client

Python SDK for [Meteora](https://github.com/efebiskin/meteora) — a production weather API.

## Install

```bash
pip install meteora-client
```

## Quick start

```python
from meteora_client import Meteora

mt = Meteora(api_key="mto_xxx", base_url="https://api.example.com")

# current
cur = mt.current(lat=34.17, lon=-118.87)
print(cur["current"]["temperature_c"], cur["current"]["weather_description"])

# 7-day forecast
fc = mt.forecast(lat=34.17, lon=-118.87, days=7)
for day in fc["days"]:
    print(day["date"], day["temp_max_c"], day["weather_description"])

# hourly
hr = mt.hourly(lat=34.17, lon=-118.87, hours=24)

# historical
hist = mt.historical(lat=34.17, lon=-118.87, start="2023-01-01", end="2023-12-31")

# air quality
air = mt.air_quality(lat=34.17, lon=-118.87)

# bulk (up to 100 points, 1 request against quota)
bulk = mt.bulk_current([
    {"lat": 34.17, "lon": -118.87, "label": "Thousand Oaks"},
    {"lat": 40.73, "lon": -73.93, "label": "NYC"},
])

# geocoding
results = mt.geo_search("Istanbul", count=3)

# your usage stats
stats = mt.usage()
print(stats["used_today"], "/", stats["rate_limit_daily"])
```

## Context manager

```python
with Meteora(api_key="mto_xxx") as mt:
    print(mt.current(34.17, -118.87))
```

## Error handling

```python
from meteora_client import Meteora, MeteoraError

try:
    mt.current(lat=999, lon=999)
except MeteoraError as e:
    print(e.status)     # 422 (validation)
    print(e.detail)     # response body
```

## License

MIT. Built by [Efe Biskin](https://github.com/efebiskin).
