# src/post_trip_summary/pipeline/ingest/google_maps.py
"""Parse Google Maps Timeline JSON export (from Google Takeout)."""
import json
from datetime import datetime, timezone
from pathlib import Path


def _parse_timestamp(ts_str: str) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _e7_to_degrees(e7_value: int | float) -> float:
    return e7_value / 1e7


def ingest_google_maps(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    timeline_objects = data.get("timelineObjects", [])
    place_visits = []
    activity_segments = []
    for obj in timeline_objects:
        if "placeVisit" in obj:
            pv = obj["placeVisit"]
            loc = pv.get("location", {})
            duration = pv.get("duration", {})
            place_visits.append({
                "name": loc.get("name", ""),
                "address": loc.get("address", ""),
                "lat": _e7_to_degrees(loc.get("latitudeE7", 0)),
                "lon": _e7_to_degrees(loc.get("longitudeE7", 0)),
                "start": _parse_timestamp(duration.get("startTimestamp", "")),
                "end": _parse_timestamp(duration.get("endTimestamp", "")),
                "source": "google_maps",
            })
        elif "activitySegment" in obj:
            seg = obj["activitySegment"]
            start_loc = seg.get("startLocation", {})
            end_loc = seg.get("endLocation", {})
            duration = seg.get("duration", {})
            activity_segments.append({
                "start_lat": _e7_to_degrees(start_loc.get("latitudeE7", 0)),
                "start_lon": _e7_to_degrees(start_loc.get("longitudeE7", 0)),
                "end_lat": _e7_to_degrees(end_loc.get("latitudeE7", 0)),
                "end_lon": _e7_to_degrees(end_loc.get("longitudeE7", 0)),
                "start": _parse_timestamp(duration.get("startTimestamp", "")),
                "end": _parse_timestamp(duration.get("endTimestamp", "")),
                "activity_type": seg.get("activityType", "UNKNOWN"),
                "source": "google_maps",
            })
    return {"place_visits": place_visits, "activity_segments": activity_segments}
