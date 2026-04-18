"""Tiny in-memory TTL cache.

Meteora wraps Open-Meteo. Weather data doesn't change second-to-second, so
caching each (endpoint, params) key for ~5 minutes cuts upstream traffic by
~95% without meaningfully affecting data freshness. For a production
deployment you'd swap this for Redis — but for our scale a dict is fine
and has zero dependencies.

Usage:
    @cached(ttl_seconds=300)
    async def fetch_current(lat, lon): ...
"""
from __future__ import annotations

import asyncio
import time
from functools import wraps
from typing import Any, Callable

_store: dict[str, tuple[float, Any]] = {}
_lock = asyncio.Lock()


def cache_key(*args, **kwargs) -> str:
    parts = [repr(a) for a in args] + [f"{k}={v!r}" for k, v in sorted(kwargs.items())]
    return "|".join(parts)


def cached(ttl_seconds: int = 300) -> Callable:
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            k = f"{fn.__name__}::{cache_key(*args, **kwargs)}"
            now = time.time()
            async with _lock:
                hit = _store.get(k)
                if hit and hit[0] > now:
                    return hit[1]
            # miss — call the function outside the lock to avoid blocking
            val = await fn(*args, **kwargs)
            async with _lock:
                _store[k] = (now + ttl_seconds, val)
            return val
        return wrapper
    return decorator


def clear() -> int:
    """Clear all cached entries. Returns number of entries evicted."""
    n = len(_store)
    _store.clear()
    return n


def stats() -> dict:
    now = time.time()
    live = sum(1 for exp, _ in _store.values() if exp > now)
    return {"entries": len(_store), "live": live, "expired": len(_store) - live}
