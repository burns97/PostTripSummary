# src/post_trip_summary/pipeline/ingest/dayone.py
"""Parse Day One journal JSON export."""
import json
from datetime import datetime
from pathlib import Path


def _parse_timestamp(ts_str: str) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def ingest_dayone(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries_raw = data.get("entries", [])
    entries = []
    for entry in entries_raw:
        location = entry.get("location", {})
        photos = entry.get("photos", [])
        entries.append({
            "timestamp": _parse_timestamp(entry.get("creationDate", "")),
            "text": entry.get("text", ""),
            "lat": location.get("latitude") if location else None,
            "lon": location.get("longitude") if location else None,
            "place_name": location.get("placeName", "") if location else "",
            "photo_ids": [p.get("identifier", "") for p in photos],
            "source": "dayone",
        })
    return entries
