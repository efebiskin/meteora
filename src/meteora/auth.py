"""API key authentication + per-key rate limiting middleware."""
from __future__ import annotations

from fastapi import HTTPException, Request, Security
from fastapi.security.api_key import APIKeyHeader, APIKeyQuery

from . import db

# Accept either an Authorization-like header OR a ?key= query param for browser convenience.
_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
_query_scheme = APIKeyQuery(name="key", auto_error=False)


async def require_key(
    request: Request,
    header_key: str | None = Security(_header_scheme),
    query_key: str | None = Security(_query_scheme),
) -> dict:
    """FastAPI dependency — validates key + rate-limits + returns the key record."""
    raw = header_key or query_key
    if not raw:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "missing_key",
                "message": (
                    "An API key is required. Get one at POST /v1/keys, then pass it "
                    "in the 'X-API-Key' header or as '?key=...' query parameter."
                ),
            },
        )

    rec = db.verify_key(raw)
    if not rec:
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_key", "message": "Key not found or deactivated."},
        )

    count = db.increment_usage(rec["id"])
    if count > rec["rate_limit"]:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": (
                    f"Tier '{rec['tier']}' is limited to {rec['rate_limit']} requests per day. "
                    f"You've used {count}. Upgrade tiers via POST /v1/keys/upgrade."
                ),
                "limit": rec["rate_limit"],
                "used": count,
                "tier": rec["tier"],
            },
            headers={
                "X-RateLimit-Limit": str(rec["rate_limit"]),
                "X-RateLimit-Used": str(count),
                "X-RateLimit-Tier": rec["tier"],
            },
        )

    # stash counts on the request so handlers can surface in response headers
    request.state.key_record = rec
    request.state.usage_count = count
    return rec


def attach_rate_headers(response, rec: dict, count: int) -> None:
    response.headers["X-RateLimit-Limit"] = str(rec["rate_limit"])
    response.headers["X-RateLimit-Used"] = str(count)
    response.headers["X-RateLimit-Remaining"] = str(max(0, rec["rate_limit"] - count))
    response.headers["X-RateLimit-Tier"] = rec["tier"]
