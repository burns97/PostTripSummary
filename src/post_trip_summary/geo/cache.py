"""Persistent SQLite geocache for reverse geocoding results."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from post_trip_summary.settings import SETTINGS_DIR

DEFAULT_DB_PATH = SETTINGS_DIR / "geocache.db"


class GeoCache:
    """Simple key-value cache backed by SQLite, keyed on (lat, lon)."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS geocache (
                lat        REAL NOT NULL,
                lon        REAL NOT NULL,
                result     TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (lat, lon)
            )
            """
        )
        self._conn.commit()

    def get(self, lat: float, lon: float) -> dict | None:
        """Look up a cached geocode result. Returns parsed dict or None."""
        row = self._conn.execute(
            "SELECT result FROM geocache WHERE lat = ? AND lon = ?",
            (lat, lon),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def put(self, lat: float, lon: float, result: dict) -> None:
        """Insert or replace a geocode result."""
        self._conn.execute(
            "INSERT OR REPLACE INTO geocache (lat, lon, result, created_at) VALUES (?, ?, ?, ?)",
            (lat, lon, json.dumps(result), datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def clear(self) -> None:
        """Delete all cached entries."""
        self._conn.execute("DELETE FROM geocache")
        self._conn.commit()

    def __len__(self) -> int:
        """Return the number of cached entries."""
        row = self._conn.execute("SELECT COUNT(*) FROM geocache").fetchone()
        return row[0]
