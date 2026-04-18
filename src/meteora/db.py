"""SQLite-backed API key + usage store.

Schema:
  keys(
    id INTEGER PRIMARY KEY,
    key_hash TEXT NOT NULL UNIQUE,      -- bcrypt hash of the raw key
    key_prefix TEXT NOT NULL,           -- first 8 chars for lookup UX ("mto_abc1...")
    email TEXT NOT NULL,
    tier TEXT NOT NULL DEFAULT 'free',  -- free | pro | enterprise
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    rate_limit INTEGER NOT NULL,        -- requests per day
    active INTEGER NOT NULL DEFAULT 1
  )
  usage(
    id INTEGER PRIMARY KEY,
    key_id INTEGER NOT NULL,
    day TEXT NOT NULL,                  -- YYYY-MM-DD UTC
    count INTEGER NOT NULL DEFAULT 0,
    UNIQUE(key_id, day)
  )

Keys are generated as 'mto_<32-char-random>' so they're visually identifiable
and the 'mto_' prefix + first 4 chars can be shown in logs safely.
"""
from __future__ import annotations

import os
import secrets
import sqlite3
import string
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Optional

DB_PATH = Path(os.environ.get("METEORA_DB", "meteora.db"))

TIER_LIMITS = {
    "free": 200,           # 200 requests per day
    "pro": 10_000,         # 10k requests per day
    "enterprise": 1_000_000,
}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables on first run."""
    with _connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_hash TEXT NOT NULL UNIQUE,
                key_prefix TEXT NOT NULL,
                email TEXT NOT NULL,
                tier TEXT NOT NULL DEFAULT 'free',
                created_at TEXT NOT NULL,
                last_used_at TEXT,
                rate_limit INTEGER NOT NULL DEFAULT 200,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_id INTEGER NOT NULL,
                day TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                UNIQUE(key_id, day),
                FOREIGN KEY (key_id) REFERENCES keys(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_keys_prefix ON keys(key_prefix);
            CREATE INDEX IF NOT EXISTS idx_usage_key_day ON usage(key_id, day);
        """)
        db.commit()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _hash_key(raw: str) -> str:
    """Hash a raw key with SHA-256. Not bcrypt — we want fast constant lookup on every request.
    API keys are high-entropy random tokens, SHA-256 is appropriate (this is how GitHub/Stripe do it)."""
    return sha256(raw.encode("utf-8")).hexdigest()


def _generate_raw_key() -> str:
    """Generate a 'mto_<32 random chars>' key. ~190 bits of entropy."""
    alphabet = string.ascii_letters + string.digits
    rand = "".join(secrets.choice(alphabet) for _ in range(32))
    return f"mto_{rand}"


def create_key(email: str, tier: str = "free") -> dict:
    """Generate a new key, store the HASH. Returns the RAW key once — caller must save it."""
    if tier not in TIER_LIMITS:
        raise ValueError(f"invalid tier: {tier}")
    raw = _generate_raw_key()
    key_hash = _hash_key(raw)
    prefix = raw[:8]
    rate_limit = TIER_LIMITS[tier]

    with _connect() as db:
        cur = db.execute(
            """INSERT INTO keys (key_hash, key_prefix, email, tier, created_at, rate_limit)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (key_hash, prefix, email, tier, _now_iso(), rate_limit),
        )
        key_id = cur.lastrowid
        db.commit()

    return {
        "id": key_id,
        "key": raw,          # shown ONCE, never stored in plaintext
        "prefix": prefix,
        "email": email,
        "tier": tier,
        "rate_limit": rate_limit,
    }


def verify_key(raw: str) -> Optional[dict]:
    """Return the key record if raw matches a stored hash and is active. Updates last_used_at."""
    key_hash = _hash_key(raw)
    with _connect() as db:
        row = db.execute(
            "SELECT * FROM keys WHERE key_hash = ? AND active = 1",
            (key_hash,),
        ).fetchone()
        if not row:
            return None
        # Don't update on every request — amortize: only update if last_used_at is from an earlier day
        # (keeps writes off the hot path for most requests)
        today = _today()
        last_used = row["last_used_at"] or ""
        if not last_used.startswith(today):
            db.execute("UPDATE keys SET last_used_at = ? WHERE id = ?", (_now_iso(), row["id"]))
            db.commit()
        return dict(row)


def increment_usage(key_id: int) -> int:
    """Bump today's request counter for a key. Returns the new count."""
    today = _today()
    with _connect() as db:
        db.execute(
            """INSERT INTO usage (key_id, day, count) VALUES (?, ?, 1)
               ON CONFLICT(key_id, day) DO UPDATE SET count = count + 1""",
            (key_id, today),
        )
        db.commit()
        row = db.execute(
            "SELECT count FROM usage WHERE key_id = ? AND day = ?",
            (key_id, today),
        ).fetchone()
    return int(row["count"]) if row else 0


def get_usage_today(key_id: int) -> int:
    today = _today()
    with _connect() as db:
        row = db.execute(
            "SELECT count FROM usage WHERE key_id = ? AND day = ?",
            (key_id, today),
        ).fetchone()
    return int(row["count"]) if row else 0


def get_usage_history(key_id: int, days: int = 30) -> list[dict]:
    with _connect() as db:
        rows = db.execute(
            "SELECT day, count FROM usage WHERE key_id = ? ORDER BY day DESC LIMIT ?",
            (key_id, days),
        ).fetchall()
    return [{"day": r["day"], "count": r["count"]} for r in rows]
