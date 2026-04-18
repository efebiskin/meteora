"""Stock quote provider.

Tries Yahoo Finance v7 first (rich data: name, previous close, market state).
Falls back to Stooq CSV if Yahoo blocks us (cheaper/less rich but always up).

All calls are cached for 60s to avoid hammering upstreams — markets don't
move that fast at widget refresh rates anyway.
"""
from __future__ import annotations

import csv
import io
from typing import List, Tuple

import httpx

from .cache import cached
from .models import Quote, QuotesResponse

YAHOO_QUOTE = "https://query1.finance.yahoo.com/v7/finance/quote"
STOOQ_QUOTE = "https://stooq.com/q/l/"

UA = "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0"


async def _yahoo(symbols: List[str]) -> List[Quote]:
    params = {"symbols": ",".join(symbols)}
    headers = {
        "User-Agent": UA,
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with httpx.AsyncClient(timeout=8, headers=headers) as c:
        r = await c.get(YAHOO_QUOTE, params=params)
        r.raise_for_status()
        data = r.json()
    out: List[Quote] = []
    for q in (data.get("quoteResponse", {}).get("result", []) or []):
        price = q.get("regularMarketPrice") or 0.0
        out.append(Quote(
            symbol=q.get("symbol", ""),
            name=q.get("longName") or q.get("shortName") or q.get("symbol", ""),
            price=float(price),
            change=float(q.get("regularMarketChange") or 0.0),
            change_pct=float(q.get("regularMarketChangePercent") or 0.0),
            open=q.get("regularMarketOpen"),
            high=q.get("regularMarketDayHigh"),
            low=q.get("regularMarketDayLow"),
            previous_close=q.get("regularMarketPreviousClose"),
            volume=q.get("regularMarketVolume"),
            currency=q.get("currency", "USD"),
            exchange=q.get("fullExchangeName") or q.get("exchange"),
            market_state=q.get("marketState"),
        ))
    return out


async def _stooq(symbols: List[str]) -> List[Quote]:
    # Stooq wants lowercase with exchange suffix (.us for US stocks by default),
    # AND symbols must be joined with `+` not `,` — httpx would url-encode `,` so
    # we build the URL manually.
    stooq_syms = [s.lower() if "." in s else f"{s.lower()}.us" for s in symbols]
    url = f"{STOOQ_QUOTE}?s={'+'.join(stooq_syms)}&f=sd2t2ohlcv&h&e=csv"
    async with httpx.AsyncClient(timeout=8) as c:
        r = await c.get(url)
        r.raise_for_status()
        text = r.text

    out: List[Quote] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        sym_raw = row.get("Symbol", "")
        sym = sym_raw.split(".")[0].upper()
        try:
            o = float(row["Open"]); h = float(row["High"])
            lo = float(row["Low"]); c = float(row["Close"])
        except (ValueError, KeyError, TypeError):
            continue
        change = c - o
        change_pct = (change / o * 100.0) if o else 0.0
        vol = row.get("Volume", "0") or "0"
        try:
            vol_i = int(vol)
        except ValueError:
            vol_i = 0
        out.append(Quote(
            symbol=sym, name=sym, price=c, change=change, change_pct=change_pct,
            open=o, high=h, low=lo, previous_close=None,
            volume=vol_i, currency="USD", exchange="STOOQ", market_state=None,
        ))
    return out


@cached(ttl_seconds=60)
async def fetch_quotes(symbols: Tuple[str, ...]) -> QuotesResponse:
    """Return quotes for the given symbols. Cached 60s per symbol-set."""
    syms = [s.strip().upper() for s in symbols if s.strip()]
    if not syms:
        return QuotesResponse(count=0, source="none", quotes=[])

    # Yahoo first — richer data
    try:
        quotes = await _yahoo(syms)
        if quotes:
            return QuotesResponse(count=len(quotes), source="yahoo", quotes=quotes)
    except Exception:
        pass

    # Fallback: Stooq
    quotes = await _stooq(syms)
    return QuotesResponse(count=len(quotes), source="stooq", quotes=quotes)
