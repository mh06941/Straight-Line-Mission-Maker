"""Disk-backed provider cache and mission records; no fake geographical fallbacks."""

import json
import sqlite3
import time
from contextlib import contextmanager

from .config import DATA_DIR


@contextmanager
def connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA_DIR / "straightline.sqlite3", timeout=15)
    db.execute(
        "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, expires REAL, created REAL)"
    )
    db.execute("CREATE TABLE IF NOT EXISTS missions (id TEXT PRIMARY KEY, value TEXT, created REAL)")
    try:
        yield db
        db.commit()
    finally:
        db.close()


def cache_get(key):
    with connection() as db:
        row = db.execute(
            "SELECT value, created FROM cache WHERE key=? AND expires>?", (key, time.time())
        ).fetchone()
    return (json.loads(row[0]), row[1]) if row else None


def cache_put(key, value, ttl, *, created_at=None):
    now = time.time()
    created = now if created_at is None else created_at
    with connection() as db:
        db.execute(
            "INSERT OR REPLACE INTO cache VALUES (?,?,?,?)",
            (key, json.dumps(value), created + ttl, created),
        )
        db.execute("DELETE FROM cache WHERE expires<?", (now,))
    return created


def save_mission(mission):
    with connection() as db:
        db.execute(
            "INSERT OR REPLACE INTO missions VALUES (?,?,?)",
            (mission["id"], json.dumps(mission), time.time()),
        )


def load_mission(mission_id):
    with connection() as db:
        row = db.execute("SELECT value FROM missions WHERE id=?", (mission_id,)).fetchone()
    return json.loads(row[0]) if row else None
